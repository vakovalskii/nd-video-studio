#!/usr/bin/env python3
"""Сверка озвучки и пословные тайминги через whisper-1 хаба.

Что делает для каждой line_NN.wav:
- распознаёт и сравнивает с текстом из narration.json: TTS иногда глотает, переставляет или
  добавляет слова, и на слух это легко пропустить. Похожесть ниже порога = переозвучить (--only N);
- кладёт слова с временами (уже со сдвигом на start фразы) в words.json. Из него композиция
  подсвечивает слово в субтитрах ровно тогда, когда оно звучит.

  ND_API_KEY=sk-... python3 scripts/nd_align.py projects/x/narration.json projects/x/audio/fit projects/x/words.json
"""

import argparse
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, load_narration, nd_multipart  # noqa: E402


def norm(s):
    return re.sub(r"[^\w ]+", " ", s.lower()).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("audio_dir", help="обычно audio/fit (после подгонки темпа)")
    ap.add_argument("out")
    ap.add_argument("--model", default="whisper-1")
    ap.add_argument("--min-sim", type=float, default=0.85)
    a = ap.parse_args()

    n = load_narration(a.narration)
    lang = {"en": "en", "ru": "ru"}.get(n.get("language", "en"), None)
    out, bad = [], []
    for i, ln in enumerate(n["lines"]):
        path = os.path.join(a.audio_dir, clip_name(i))
        with open(path, "rb") as f:
            fields = {"model": a.model, "response_format": "verbose_json"}
            if lang:
                fields["language"] = lang
            res = nd_multipart("/v1/audio/transcriptions", fields, {"file": (clip_name(i), f.read(), "audio/wav")})
        heard = res.get("text", "")
        sim = difflib.SequenceMatcher(None, norm(ln["text"]), norm(heard)).ratio()
        words = [{"w": w["word"].strip(), "t0": round(ln["start"] + w["start"], 3), "t1": round(ln["start"] + w["end"], 3)}
                 for seg in res.get("segments", []) for w in (seg.get("words") or [])
                 if w.get("start") is not None and w.get("end") is not None]
        out.append({"line": i, "text": ln["text"], "heard": heard.strip(), "sim": round(sim, 3), "words": words})
        flag = "OK " if sim >= a.min_sim else "BAD"
        if sim < a.min_sim:
            bad.append(i)
        print(f"[{i:02d}] {flag} {sim:.2f} | {heard.strip()[:70]}")
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("→", a.out)
    if bad:
        print(f"⚠️ переозвучить: --only {' '.join(map(str, bad))}")
        sys.exit(2)


if __name__ == "__main__":
    main()
