#!/usr/bin/env python3
"""Voice narration.json via ElevenLabs (text-to-speech, eleven_multilingual_v2 / eleven_v3).

ElevenLabs may refuse Russian IPs: run it from a box outside Russia (FI box), as with OpenRouter.

  ELEVENLABS_API_KEY=... python3 scripts/tts_elevenlabs.py voices [--lang ru]     # list voices
  ELEVENLABS_API_KEY=... python3 scripts/tts_elevenlabs.py speak projects/x/narration.json projects/x/audio/raw \
      --voice <voice_id> [--model eleven_multilingual_v2] [--only 0 3]

Output is line_NN.wav (44.1 kHz mono), the same layout as the other TTS scripts. The API returns mp3
(pcm output and library voices need a paid plan), ffmpeg turns it into wav.
Settings come from narration.json "voice": {"voice": id, "model": ..., "stability": ..., "style": ..., "speed": ...}.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, env_key, http, load_narration  # noqa: E402

BASE = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io")
RATE = 44100


def call(path, key, body=None):
    hdr = {"xi-api-key": key, "Content-Type": "application/json"}
    for attempt in range(4):
        try:
            with http(f"{BASE}{path}", body, hdr, timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if attempt == 3 or not (e.code == 429 or e.code >= 500):
                raise SystemExit(f"HTTP {e.code}: {e.read()[:300]!r}")
            time.sleep(3 * (attempt + 1))


def voices(key, lang):
    data = json.loads(call("/v1/voices", key))
    for v in data.get("voices", []):
        labels = v.get("labels") or {}
        langs = [x.get("language") for x in (v.get("verified_languages") or [])]
        if lang and lang not in langs and labels.get("language") != lang:
            continue
        print(f"{v['voice_id']}  {v['name']:<28} {labels.get('gender', ''):<7} {labels.get('age', ''):<12} "
              f"{labels.get('accent', '')} {labels.get('use_case', '') or labels.get('description', '')}")


def speak(key, narration, out_dir, voice, model, only):
    n = load_narration(narration)
    v = n.get("voice", {})
    voice = voice or v.get("voice")
    model = model or v.get("model", "eleven_multilingual_v2")
    if not voice:
        raise SystemExit("no voice id: --voice or narration.json voice.voice")
    settings = {"stability": v.get("stability", 0.45), "similarity_boost": v.get("similarity_boost", 0.8),
                "style": v.get("style_exaggeration", 0.25), "use_speaker_boost": True, "speed": v.get("speed", 1.05)}
    os.makedirs(out_dir, exist_ok=True)
    lines = n["lines"]
    for i, ln in enumerate(lines):
        if only and i not in only:
            continue
        body = {"text": ln["text"], "model_id": model, "voice_settings": settings,
                "language_code": {"ru": "ru", "en": "en"}.get(n.get("language", ""), None)}
        # neighbouring lines keep the intonation continuous across separate requests
        if i > 0:
            body["previous_text"] = lines[i - 1]["text"]
        if i + 1 < len(lines):
            body["next_text"] = lines[i + 1]["text"]
        body = {k: x for k, x in body.items() if x is not None}
        mp3 = call(f"/v1/text-to-speech/{voice}?output_format=mp3_44100_128", key, body)
        wav = os.path.join(out_dir, clip_name(i))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "mp3", "-i", "pipe:0", "-ac", "1", "-ar", str(RATE), wav],
                       input=mp3, check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                   capture_output=True, text=True).stdout)
        print(f"[{i}] {dur:.2f}s | {ln['text'][:70]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("voices")
    a1.add_argument("--lang", default="")
    a2 = sub.add_parser("speak")
    a2.add_argument("narration")
    a2.add_argument("out_dir")
    a2.add_argument("--voice")
    a2.add_argument("--model")
    a2.add_argument("--only", type=int, nargs="*")
    a = ap.parse_args()
    key = env_key("ELEVENLABS_API_KEY")
    if a.cmd == "voices":
        voices(key, a.lang)
    else:
        speak(key, a.narration, a.out_dir, a.voice, a.model, a.only)


if __name__ == "__main__":
    main()
