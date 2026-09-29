#!/usr/bin/env python3
"""Озвучка narration.json через TTS хаба (api.neuraldeep.ru/v1/audio/speech, Qwen3-TTS).

Голоса: vivian, serena, ono_anna, sohee, dylan, ryan, aiden, uncle_fu. Стиль — свободным
текстом в instructions, скорость — speed. Русский идёт через ESpeech + RUAccent.

  ND_API_KEY=sk-... python3 scripts/tts_hub.py projects/x/narration.json projects/x/audio/raw --voice ryan
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, env_key, http, load_narration  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("out_dir")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--language", help="English, Russian, ...; по умолчанию из narration.json")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--only", type=int, nargs="*")
    a = ap.parse_args()

    n = load_narration(a.narration)
    v = n.get("voice", {})
    voice = a.voice or v.get("voice", "ryan")
    language = a.language or {"en": "English", "ru": "Russian"}.get(n.get("language", "en"), "Auto")
    style = v.get("style", "Energetic tech trailer narrator. Punchy, confident, crisp emphasis.")
    key = env_key("ND_API_KEY")
    base = os.environ.get("ND_API_BASE", "https://api.neuraldeep.ru")
    os.makedirs(a.out_dir, exist_ok=True)
    for i, ln in enumerate(n["lines"]):
        if a.only and i not in a.only:
            continue
        body = {"input": ln["text"], "voice": voice, "language": language, "instructions": style,
                "response_format": "wav", "speed": a.speed, "seed": 7}
        with http(f"{base}/v1/audio/speech", body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}) as r:
            data = r.read()
        with open(os.path.join(a.out_dir, clip_name(i)), "wb") as f:
            f.write(data)
        print(f"[{i}] {voice} {len(data)} bytes | {ln['text'][:60]}")


if __name__ == "__main__":
    main()
