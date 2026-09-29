#!/usr/bin/env python3
"""Frame review by a hub vision model: contact sheet from `hyperframes snapshot` → notes.

HyperFrames does --describe only via Gemini; this does the same on our own model. The model
looks at what the linter can't see: overlapping text, too small for a phone, empty
frame, captions covering the key visual, unclear scene.

  ND_API_KEY=sk-... python3 scripts/nd_review.py projects/x/snapshots/contact-sheet-*.jpg --brief "vertical Shorts"
"""

import argparse
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import nd_chat  # noqa: E402

ASK = """You review frames of an explainer video (grid of timestamped stills). {brief}
For every frame with a problem write one line: "<timestamp>: <problem> → <fix>".
Check: overlapping or clipped text, text too small to read on a phone, empty or confusing frames,
captions covering the key visual, low contrast, elements outside safe margins.
Skip frames without problems. End with one line: VERDICT: ok | fix needed."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--brief", default="")
    ap.add_argument("--model", default=os.environ.get("ND_VISION_MODEL", "qwen3.6-35b-a3b-noreason"))
    a = ap.parse_args()
    for path in a.images:
        mime = "image/png" if path.endswith(".png") else "image/jpeg"
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        content = [{"type": "text", "text": ASK.format(brief=a.brief)},
                   {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]
        print(f"== {path}\n" + nd_chat([{"role": "user", "content": content}], model=a.model, temperature=0.2).strip())


if __name__ == "__main__":
    main()
