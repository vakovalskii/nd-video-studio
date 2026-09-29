#!/usr/bin/env python3
"""Timings from the actual voice-over: line and scene starts in narration.json from real raw clip lengths.

Use it when the script was written by a model (nd_script.py) and there is no composition yet: TTS pace
can't be guessed from text, so voice first, then starts, then HTML. Edge silence of a clip is not
counted (trimmed as in fit_narration.py); pauses between lines and at scene changes are configurable.
If the composition is already laid out to the starts, use fit_narration.py instead.

  python3 scripts/nd_retime.py projects/x/narration.json projects/x/audio/raw
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import clip_name  # noqa: E402
from fit_narration import TRIM  # noqa: E402


def spoken(path):
    """Speech length without edge silence, seconds."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", TRIM, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    t = [x for x in out.split() if x.startswith("time=")][-1][5:]
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("narration")
    ap.add_argument("raw_dir")
    ap.add_argument("--pause", type=float, default=0.5)
    ap.add_argument("--scene-pause", type=float, default=1.2)
    ap.add_argument("--tail", type=float, default=2.5, help="tail after the last line (outro)")
    a = ap.parse_args()

    n = json.load(open(a.narration))
    t, prev_scene = 0.5, None
    for i, ln in enumerate(n["lines"]):
        sc = ln.get("scene")
        if i and sc != prev_scene:
            t += a.scene_pause
        if sc is not None and sc != prev_scene and n.get("scenes"):
            n["scenes"][sc]["start"] = round(t, 2)
        ln["start"] = round(t, 2)
        d = spoken(os.path.join(a.raw_dir, clip_name(i)))
        print(f"[{i:02d}] {ln['start']:6.2f}  {d:5.2f}s | {ln['text'][:60]}")
        t += d + a.pause
        prev_scene = sc
    n["duration"] = round(t + a.tail)
    json.dump(n, open(a.narration, "w"), ensure_ascii=False, indent=1)
    print(f"video length {n['duration']} s → {a.narration}")


if __name__ == "__main__":
    main()
