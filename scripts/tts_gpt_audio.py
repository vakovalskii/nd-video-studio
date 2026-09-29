#!/usr/bin/env python3
"""Voice narration.json via openai/gpt-audio (OpenRouter).

OpenRouter blocks RU IPs (403 "Access denied by security policy"): run it where
it's reachable (FI box), or point OPENROUTER_API_BASE at your own egress proxy.

The model tends to answer like an assistant ("Understood, here is…") and read out service
tags. Hence: system = "you are a TTS engine", user = bare text, and each line
is checked against the transcript (delta.audio.transcript) with retries.

  OPENROUTER_API_KEY=... python3 scripts/tts_gpt_audio.py projects/x/narration.json projects/x/audio/raw
"""

import argparse
import base64
import json
import os
import re
import sys
import wave

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, env_key, http, load_narration  # noqa: E402

SYS = (
    "You are a text-to-speech engine, not an assistant. Your ONLY output is the exact words of the "
    "user message, spoken aloud. Never acknowledge, never add intros like Understood or Here is, "
    "never add anything after. Voice style: {style}"
)
DEFAULT_STYLE = "energetic movie-trailer narrator, punchy, confident, dynamic, crisp emphasis, fast pace."
RATE = 24000  # pcm16 mono 24 kHz


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def speak(base, key, voice, style, text, tries):
    body = {
        "model": "openai/gpt-audio",
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "pcm16"},
        "stream": True,  # OpenRouter audio output is stream-only
        "messages": [{"role": "system", "content": SYS.format(style=style)}, {"role": "user", "content": text}],
    }
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in range(1, tries + 1):
        pcm, transcript, cost = b"", [], 0
        with http(f"{base}/chat/completions", body, hdr, timeout=300) as r:
            for raw in r:
                line = raw.decode().strip()
                if not line.startswith("data:") or line.endswith("[DONE]"):
                    continue
                try:
                    d = json.loads(line[5:])
                except json.JSONDecodeError:
                    continue
                if d.get("usage"):
                    cost = d["usage"].get("cost") or 0
                for c in d.get("choices", []):
                    a = (c.get("delta") or {}).get("audio") or {}
                    if a.get("data"):
                        pcm += base64.b64decode(a["data"])
                    if a.get("transcript"):
                        transcript.append(a["transcript"])
        said = "".join(transcript)
        ok = norm(said) == norm(text)
        print(f"  try {attempt}: {'ok' if ok else 'MISMATCH'} {len(pcm) / 2 / RATE:.2f}s ${cost:.4f} | {said[:70]}")
        if ok:
            return pcm
    raise SystemExit(f"failed to voice verbatim: {text!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("out_dir")
    ap.add_argument("--voice", help="onyx, ash, verse, ballad, echo… (default from narration.json)")
    ap.add_argument("--only", type=int, nargs="*", help="line numbers to re-voice")
    ap.add_argument("--tries", type=int, default=4)
    a = ap.parse_args()

    n = load_narration(a.narration)
    v = n.get("voice", {})
    voice = a.voice or v.get("voice", "ash")
    style = v.get("style", DEFAULT_STYLE)
    key = env_key("OPENROUTER_API_KEY")
    base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    os.makedirs(a.out_dir, exist_ok=True)
    for i, ln in enumerate(n["lines"]):
        if a.only and i not in a.only:
            continue
        print(f"[{i}] {voice}: {ln['text'][:60]}")
        pcm = speak(base, key, voice, style, ln["text"], a.tries)
        with wave.open(os.path.join(a.out_dir, clip_name(i)), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(pcm)


if __name__ == "__main__":
    main()
