#!/usr/bin/env python3
"""Video script from a hub model: brief (+ sources.md) → narration.json with scenes and timings.

The model splits the idea into scenes (question heading, 2-4 narrator lines, key idea), while
timings are computed by the script, not the model: line start = previous end + pause, duration from
speech rate (EN ~2.1 words/s, RU ~12 chars/s for the hub TTS). This is a draft: after voicing,
nd_retime.py sets starts from the real line lengths.

  ND_API_KEY=sk-... python3 scripts/nd_script.py brief.md projects/x/narration.json \
      --sources projects/x/sources.md --lang en --seconds 90
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import extract_json, nd_chat  # noqa: E402

SYSTEM = """You write narration for short explainer videos rendered from HTML.
Rules:
- One idea per scene. Each scene: a heading phrased as a question, 2-4 narrator lines, one short key idea.
- Narrator lines are short spoken sentences, max ~22 words, no lists, no markdown, no emoji.
- Use ONLY facts from the sources given. If something is an estimate, say so in the line ("likely", "estimated").
- Total speaking time must fit the target duration.
Return ONLY JSON: {"title": str, "scenes": [{"heading": str, "key_idea": str, "lines": [str, ...]}]}"""


def speak_seconds(text, lang):
    return len(text.split()) / 2.1 if lang == "en" else len(text) / 12.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("out")
    ap.add_argument("--sources")
    ap.add_argument("--lang", default="en", choices=["en", "ru"])
    ap.add_argument("--seconds", type=float, default=90)
    ap.add_argument("--model", help="default ND_CHAT_MODEL or qwen3.8-27b-noreason")
    ap.add_argument("--pause", type=float, default=0.6, help="pause between lines")
    ap.add_argument("--scene-pause", type=float, default=1.4, help="pause at scene change")
    a = ap.parse_args()

    brief = open(a.brief).read()
    src = open(a.sources).read()[:60000] if a.sources else "(no sources given: keep claims generic)"
    lang = "English" if a.lang == "en" else "Russian"
    user = (f"Language: {lang}. Target duration: {a.seconds:.0f} seconds of narration.\n\n"
            f"BRIEF:\n{brief}\n\nSOURCES:\n{src}")
    plan = extract_json(nd_chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                                model=a.model, temperature=0.4))

    t, lines, scenes = 0.5, [], []
    for si, sc in enumerate(plan["scenes"]):
        if si:
            t += a.scene_pause
        scenes.append({"start": round(t, 1), "heading": sc["heading"], "key_idea": sc.get("key_idea", "")})
        for text in sc["lines"]:
            lines.append({"start": round(t, 1), "text": text.strip(), "scene": si})
            t += speak_seconds(text, a.lang) + a.pause
    out = {"title": plan.get("title", ""), "duration": round(t + 2.5), "language": a.lang,
           "voice": {"provider": "nd-tts", "voice": "ryan" if a.lang == "en" else "aiden",
                     "style": "Energetic tech explainer narrator. Confident, crisp emphasis."},
           "music": {"provider": "acestep",
                     "prompt": "Instrumental minimal electronic, 110 BPM, pulsing synth arpeggio, soft sub bass, airy pads, no vocals"},
           "scenes": scenes, "lines": lines}
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{len(scenes)} scenes, {len(lines)} lines, ~{out['duration']} s → {a.out}")
    if out["duration"] > a.seconds * 1.15:
        print(f"⚠️ over target by {out['duration'] - a.seconds:.0f} s: shorten the brief or rerun")


if __name__ == "__main__":
    main()
