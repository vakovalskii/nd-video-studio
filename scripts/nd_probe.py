#!/usr/bin/env python3
"""Hub availability check: every model and endpoint the pipeline depends on.

The model list comes from /v1/models, each chat model gets a short ping. Then a chain:
TTS → whisper check of the same line, FLUX image → vision model describes it, web and tg search.
Key from env or from .env in the repo root (never printed).

  python3 scripts/nd_probe.py              # everything
  python3 scripts/nd_probe.py --no-images  # skip image generation (saves quota)
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPE = {  # what the pipeline calls by default
    "chat": ["qwen3.8-27b-noreason", "kimi-k2.6", "gemma-4-31b-noreason"],
    "vision": "qwen3.6-35b-a3b-noreason",
    "tts": "qwen3-tts",
    "stt": "whisper-1",
}
PHRASE = "Key value cache keeps attention fast."


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            k, _, v = line.strip().partition("=")
            if k and v and not k.startswith("#"):
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))


load_env()
from ndv_common import http, nd_auth, nd_base, nd_chat, nd_json, nd_multipart  # noqa: E402

rows = []


def check(name, fn):
    t0 = time.time()
    try:
        note = fn() or ""
        ok = True
    except urllib.error.HTTPError as e:
        ok, note = False, f"HTTP {e.code} {e.read()[:160].decode(errors='replace')}"
    except Exception as e:  # noqa: BLE001
        ok, note = False, f"{type(e).__name__}: {str(e)[:160]}"
    rows.append((name, ok, time.time() - t0, str(note).replace("\n", " ")[:90]))
    print(f"{'OK  ' if ok else 'FAIL'} {name:<40} {time.time() - t0:6.1f}s  {rows[-1][3]}", flush=True)
    return ok


def ping(model):
    def fn():
        text = nd_chat([{"role": "user", "content": "Reply with one word: pong"}], model=model,
                       max_tokens=16, temperature=0, timeout=120)
        if not text.strip():
            raise RuntimeError("empty content")
        return text.strip()
    return fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    tmp = os.path.join(ROOT, "music", ".probe")  # music/ is in .gitignore
    os.makedirs(tmp, exist_ok=True)

    models = []

    def list_models():
        models.extend(m["id"] for m in nd_json("/v1/models")["data"])
        missing = [m for m in [*PIPE["chat"], PIPE["vision"]] if m not in models]
        return f"{len(models)} models" + (f", missing from list: {missing}" if missing else "")
    check("GET /v1/models", list_models)

    skip = ("tts", "whisper", "embed", "rerank", "flux", "image", "speech", "audio", "bge", "e5")
    chat = sorted({m for m in models if not any(s in m.lower() for s in skip)} | set(PIPE["chat"]))
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda m: check(f"chat {m}", ping(m)), chat))

    wav = os.path.join(tmp, "probe.wav")

    def tts():
        body = {"input": PHRASE, "voice": "ryan", "language": "English", "response_format": "wav"}
        with http(f"{nd_base()}/v1/audio/speech", body, {**nd_auth(), "Content-Type": "application/json"}) as r:
            data = r.read()
        if len(data) < 10000:
            raise RuntimeError(f"suspiciously short response {len(data)} bytes")
        open(wav, "wb").write(data)
        return f"{len(data)} bytes"
    if check("tts qwen3-tts (ryan)", tts):
        def stt():
            res = nd_multipart("/v1/audio/transcriptions", {"model": PIPE["stt"]},
                               {"file": ("probe.wav", open(wav, "rb").read(), "audio/wav")})
            return f"«{res.get('text', '').strip()}»"
        check("stt whisper-1 (line check)", stt)

    png = os.path.join(tmp, "probe.png")
    if not a.no_images:
        def image():
            sub = nd_json("/v1/images/generate", {"prompt": "a red apple on a white table", "translate": False})
            t0 = time.time()
            while time.time() - t0 < 300:
                st = str(nd_json(f"/v1/images/tasks/{sub['task_uid']}").get("status", "")).lower()
                if st in ("done", "completed", "success", "succeeded", "finished"):
                    with http(f"{nd_base()}/v1/images/tasks/{sub['task_uid']}/result", headers=nd_auth()) as r:
                        open(png, "wb").write(r.read())
                    return f"{os.path.getsize(png)} bytes"
                if st in ("failed", "error", "cancelled"):
                    raise RuntimeError(f"task failed: {st}")
                time.sleep(3)
            raise TimeoutError("300 s")
        if check("images FLUX generate", image):
            def vision():
                b64 = base64.b64encode(open(png, "rb").read()).decode()
                return nd_chat([{"role": "user", "content": [
                    {"type": "text", "text": "What fruit is in the picture? One word."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
                    model=PIPE["vision"], max_tokens=16, temperature=0)
            check(f"vision {PIPE['vision']}", vision)
    check("images quota", lambda: json.dumps(nd_json("/v1/images/quota"), ensure_ascii=False)[:90])
    check("search web", lambda: f"{len(nd_json('/v1/search/web', {'query': 'KV cache', 'limit': 3}).get('results', []))} results")
    check("search tg", lambda: f"{len(nd_json('/v1/search/tg?q=KV%20cache&limit=3').get('results', []))} results")

    bad = [r for r in rows if not r[1]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} OK" + ("" if not bad else ": failing " + ", ".join(r[0] for r in bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
