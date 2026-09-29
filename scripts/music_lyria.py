#!/usr/bin/env python3
"""Music via Google Lyria 3 (OpenRouter): pro = full track $0.08, clip = 30 s $0.04.

stream: true only; the track arrives as one base64 chunk in delta.audio.data (mp3).
A prompt mentioning AI/video/a product gets blocked by Google as PROHIBITED_CONTENT (no
charge): describe music only: genre, BPM, instruments, mood, no vocals.
Like gpt-audio, OpenRouter returns 403 from RU IPs.

  OPENROUTER_API_KEY=... python3 scripts/music_lyria.py "Instrumental minimal electronic, 110 BPM, ..." music.mp3
"""

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import env_key, http  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--model", default="google/lyria-3-pro-preview", choices=["google/lyria-3-pro-preview", "google/lyria-3-clip-preview"])
    a = ap.parse_args()

    key = env_key("OPENROUTER_API_KEY")
    base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    body = {"model": a.model, "modalities": ["text", "audio"], "stream": True, "audio": {"format": "mp3"},
            "messages": [{"role": "user", "content": a.prompt}]}
    chunks, err, cost = [], None, None
    with http(f"{base}/chat/completions", body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=600) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:") or line.endswith("[DONE]"):
                continue
            try:
                d = json.loads(line[5:])
            except json.JSONDecodeError:
                continue
            err = d.get("error") or err
            if d.get("usage"):
                cost = d["usage"].get("cost")
            for c in d.get("choices", []):
                au = (c.get("delta") or {}).get("audio") or {}
                if au.get("data"):
                    chunks.append(au["data"])
    if not chunks:
        raise SystemExit(f"no audio returned: {err}. PROHIBITED_CONTENT = strip everything but music from the prompt")
    data = b"".join(base64.b64decode(c) for c in chunks)
    with open(a.out, "wb") as f:
        f.write(data)
    print(f"{a.out}: {len(data)} bytes, cost ${cost}")


if __name__ == "__main__":
    main()
