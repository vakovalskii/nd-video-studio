#!/usr/bin/env python3
"""Local music studio: a browser page on top of your own ACE-Step 1.5.

Stdlib-only server: serves tools/music-studio.html, proxies tasks to
ACE-Step (via ssh tunnel, the box API listens on 127.0.0.1 only), stores finished tracks
in music/ with history in music/history.json, and can drop a track into a project as audio/music.mp3.

  ssh -N -L 18001:127.0.0.1:8001 <gpu-box> &
  python3 scripts/music_studio.py            # → http://127.0.0.1:8765
"""

import argparse
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import http  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "tools", "music-studio.html")
MUSIC = os.path.join(ROOT, "music")
HIST = os.path.join(MUSIC, "history.json")
LOCK = threading.Lock()
JOBS = {}          # task_id → {"params", "t0", "status", "files", "error"}

ALLOWED = {"prompt", "lyrics", "audio_duration", "bpm", "key_scale", "time_signature", "vocal_language",
           "inference_steps", "guidance_scale", "seed", "use_random_seed", "batch_size", "thinking",
           "use_format", "model"}


def api(path, body=None):
    hdr = {"Content-Type": "application/json"}
    if os.environ.get("ACESTEP_API_KEY"):
        hdr["Authorization"] = f"Bearer {os.environ['ACESTEP_API_KEY']}"
    with http(f"{BASE}{path}", body, hdr, timeout=60) as r:
        return json.load(r)


def history():
    try:
        return json.load(open(HIST))
    except (OSError, ValueError):
        return []


def save_history(h):
    json.dump(h, open(HIST, "w"), ensure_ascii=False, indent=1)


def slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:40] or "track"


def poll(task_id):
    """Background task polling: finished files are downloaded to music/ and added to history."""
    job = JOBS[task_id]
    while True:
        time.sleep(2)
        try:
            q = api("/query_result", {"task_id_list": [task_id]})
        except Exception as e:  # tunnel blinked, keep trying
            job["note"] = f"poll: {type(e).__name__}"
            continue
        item = (q.get("data") or q)[0]
        st = item.get("status")
        if st == 2:
            job.update(status="error", error=str(item.get("result") or item)[:500])
            return
        if st != 1:
            continue
        res = json.loads(item["result"]) if isinstance(item["result"], str) else item["result"]
        stamp = time.strftime("%Y%m%d-%H%M%S")
        files = []
        for k, r in enumerate(res):
            url = r["file"] if r["file"].startswith("http") else BASE + r["file"]
            name = f"{stamp}_{slug(job['params'].get('prompt', ''))}_{k + 1}.mp3"
            with http(url, timeout=120) as resp, open(os.path.join(MUSIC, name), "wb") as f:
                f.write(resp.read())
            files.append({"file": name, "metas": r.get("metas") or {}, "seed": r.get("seed_value") or r.get("seed")})
        took = round(time.time() - job["t0"], 1)
        with LOCK:
            h = history()
            for fi in files:
                h.insert(0, {**fi, "params": job["params"], "took": took, "at": stamp, "fav": False})
            save_history(h)
        job.update(status="done", files=[f["file"] for f in files], took=took)
        return


SONG_SYSTEM = """You are a songwriter for a text-to-music model (ACE-Step).
From the user's idea write an original song and a music description.
Rules:
- Lyrics in {lang_name}, singable, with rhyme and rhythm, no clichés, concrete images.
- Structure tags on their own lines: [Verse], [Chorus], [Bridge], [Outro]. Size the song to ~{seconds:.0f} seconds
  (roughly: 60 s = verse + chorus; 120 s = 2 verses + 2 choruses; 180 s+ adds a bridge and final chorus).
- caption: English, comma-separated: genre, mood, instruments, vocal type (e.g. "male vocals"). Never "instrumental" or "no vocals".
- bpm: integer that fits the genre.
Return ONLY JSON: {{"title": str, "caption": str, "bpm": int, "lyrics": str}}"""


def write_song(idea, lang, seconds, style):
    """Lyrics and track caption from a hub model: the LM inside ACE-Step writes poor Russian."""
    from ndv_common import extract_json, nd_chat
    if not idea.strip():
        raise ValueError("empty idea")
    names = {"ru": "Russian", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "zh": "Chinese", "ja": "Japanese"}
    user = f"Idea: {idea}" + (f"\nStyle wishes: {style}" if style.strip() else "")
    out = extract_json(nd_chat([{"role": "system", "content": SONG_SYSTEM.format(lang_name=names.get(lang, "Russian"), seconds=seconds)},
                                {"role": "user", "content": user}], temperature=0.9, timeout=180))
    return {"title": out.get("title", ""), "caption": out.get("caption", ""), "bpm": int(out.get("bpm") or 0) or None,
            "lyrics": out.get("lyrics", "").strip()}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_audio(self, path):
        """Range-aware serving: without 206 and Accept-Ranges the browser won't let the player seek."""
        data = open(path, "rb").read()
        size = len(data)
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if not m:
            self.send_response(200)
            start, end = 0, size - 1
        else:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:  # bytes=-N: last N bytes
                start, end = max(0, size - int(m.group(2))), size - 1
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        try:
            self.wfile.write(data[start:end + 1])
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser aborted the request on seek, that's fine

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self.send(200, open(PAGE, "rb").read(), "text/html; charset=utf-8")
        if u.path == "/api/health":
            try:
                return self.send(200, api("/health").get("data", {}))
            except Exception as e:
                return self.send(503, {"error": f"ACE-Step unavailable ({BASE}): {type(e).__name__}. Is the tunnel up?"})
        if u.path == "/api/history":
            return self.send(200, history())
        if u.path == "/api/jobs":
            return self.send(200, [{"id": k, **{x: v.get(x) for x in ("status", "files", "error", "took", "note")},
                                    "elapsed": round(time.time() - v["t0"]), "prompt": v["params"].get("prompt", "")}
                                   for k, v in JOBS.items()])
        if u.path == "/api/projects":
            p = os.path.join(ROOT, "projects")
            return self.send(200, sorted(d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))))
        if u.path.startswith("/music/"):
            path = os.path.join(MUSIC, os.path.basename(urllib.parse.unquote(u.path)))
            if not os.path.isfile(path):
                return self.send(404, {"error": "no such file"})
            return self.send_audio(path)
        self.send(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        b = self.body()
        if u.path == "/api/generate":
            params = {k: v for k, v in b.items() if k in ALLOWED and v not in (None, "")}
            params.setdefault("lyrics", "[Instrumental]")
            params["audio_format"] = "mp3"
            try:
                resp = api("/release_task", params)
            except Exception as e:
                return self.send(503, {"error": f"ACE-Step unavailable: {type(e).__name__}: {e}"})
            task = (resp.get("data") or resp).get("task_id")
            if not task:
                return self.send(502, {"error": f"no task_id: {resp}"})
            JOBS[task] = {"params": params, "t0": time.time(), "status": "running"}
            threading.Thread(target=poll, args=(task,), daemon=True).start()
            return self.send(200, {"task_id": task})
        if u.path == "/api/lyrics":
            try:
                return self.send(200, write_song(b.get("idea", ""), b.get("lang") or "ru",
                                                 float(b.get("duration") or 90), b.get("style") or ""))
            except SystemExit as e:  # env_key with no key
                return self.send(400, {"error": f"{e}. Start the studio with ND_API_KEY"})
            except Exception as e:
                return self.send(502, {"error": f"failed to write song: {type(e).__name__}: {e}"})
        if u.path == "/api/fav":
            with LOCK:
                h = history()
                for x in h:
                    if x["file"] == b.get("file"):
                        x["fav"] = not x.get("fav")
                save_history(h)
            return self.send(200, {"ok": True})
        if u.path == "/api/use":
            src = os.path.join(MUSIC, os.path.basename(b.get("file", "")))
            proj = os.path.join(ROOT, "projects", os.path.basename(b.get("project", "")))
            if not os.path.isfile(src) or not os.path.isdir(proj):
                return self.send(400, {"error": "missing track or project"})
            os.makedirs(os.path.join(proj, "audio"), exist_ok=True)
            dst = os.path.join(proj, "audio", "music.mp3")
            if os.path.exists(dst):  # keep the previous track
                shutil.copy2(dst, os.path.join(proj, "audio", f"music.prev-{time.strftime('%Y%m%d-%H%M%S')}.mp3"))
            shutil.copy2(src, dst)
            return self.send(200, {"ok": True, "path": os.path.relpath(dst, ROOT)})
        self.send(404, {"error": "not found"})


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--api", default=os.environ.get("ACESTEP_API", "http://127.0.0.1:18001"))
    a = ap.parse_args()
    BASE = a.api.rstrip("/")
    os.makedirs(MUSIC, exist_ok=True)
    print(f"Music Studio: http://127.0.0.1:{a.port}  (ACE-Step {BASE}, tracks in {MUSIC})")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
