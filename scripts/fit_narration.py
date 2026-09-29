#!/usr/bin/env python3
"""Fit narration to the timeline: every line must fit its window.

Trims edge silence; if a line is too long, speeds it up with atempo (timbre
is preserved). Going above --max-tempo is audible. Such lines are
flagged TOO LONG: shorten them in narration.json and re-voice.

  python3 scripts/fit_narration.py projects/x/narration.json projects/x/audio/raw projects/x/audio/fit
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name, duration, ffmpeg, load_narration  # noqa: E402

TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("raw_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--max-tempo", type=float, default=1.12)
    a = ap.parse_args()

    n = load_narration(a.narration)
    os.makedirs(a.out_dir, exist_ok=True)
    report, bad = [], 0
    for i, ln in enumerate(n["lines"]):
        src = os.path.join(a.raw_dir, clip_name(i))
        tmp = os.path.join(a.out_dir, f"trim_{i:02d}.wav")
        ffmpeg("-i", src, "-af", TRIM, "-ar", "48000", tmp)
        d = duration(tmp)
        tempo = max(1.0, d / ln["window"])
        dst = os.path.join(a.out_dir, clip_name(i))
        ffmpeg("-i", tmp, "-af", f"atempo={tempo:.4f}", dst)
        os.remove(tmp)
        status = "ok" if tempo <= a.max_tempo else "TOO LONG"
        bad += status != "ok"
        report.append({"line": i, "start": ln["start"], "window": ln["window"], "raw": round(d, 2),
                       "tempo": round(tempo, 3), "final": round(duration(dst), 2), "status": status})
        print(f"[{i:2}] start {ln['start']:6.1f}  raw {d:5.2f}s  window {ln['window']:5.2f}s  tempo ×{tempo:.3f}  {status}")
    with open(os.path.join(a.out_dir, "fit_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    if bad:
        raise SystemExit(f"{bad} line(s) don't fit even at ×{a.max_tempo}: shorten the text and re-voice (--only)")


if __name__ == "__main__":
    main()
