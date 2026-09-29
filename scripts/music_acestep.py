#!/usr/bin/env python3
"""Музыка через свой ACE-Step 1.5 (MIT) по его REST API: /release_task → /query_result → /v1/audio.

Сервер поднимается контейнером на GPU-боксе (см. docs/acestep.md) и слушает только
127.0.0.1, поэтому ходить через ssh-туннель:
  ssh -N -L 8001:127.0.0.1:8001 <gpu-box> &
  python3 scripts/music_acestep.py "minimal electronic, pulsing synth arpeggio, no vocals" out.mp3 --duration 120 --bpm 110
"""

import argparse
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import http  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--bpm", type=int)
    ap.add_argument("--lyrics", default="[Instrumental]")
    ap.add_argument("--model", help="например acestep-v15-xl-turbo")
    ap.add_argument("--steps", type=int, default=8, help="turbo: 8, sft/base: 50")
    ap.add_argument("--thinking", action="store_true", help="LM планирует трек (лучше, но дольше и больше VRAM)")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--base", default=os.environ.get("ACESTEP_API", "http://127.0.0.1:8001"))
    a = ap.parse_args()

    hdr = {"Content-Type": "application/json"}
    if os.environ.get("ACESTEP_API_KEY"):
        hdr["Authorization"] = f"Bearer {os.environ['ACESTEP_API_KEY']}"
    body = {"prompt": a.prompt, "lyrics": a.lyrics, "audio_duration": a.duration, "thinking": a.thinking,
            "inference_steps": a.steps, "audio_format": "mp3", "seed": a.seed}
    if a.bpm:
        body["bpm"] = a.bpm
    if a.model:
        body["model"] = a.model
    t0 = time.time()
    with http(f"{a.base}/release_task", body, hdr) as r:
        resp = json.load(r)
    task = (resp.get("data") or resp).get("task_id")
    print("task", task)
    while True:
        time.sleep(3)
        with http(f"{a.base}/query_result", {"task_id_list": [task]}, hdr) as r:
            q = json.load(r)
        item = (q.get("data") or q)[0]
        if item.get("status") == 2:
            raise SystemExit(f"генерация упала: {item}")
        if item.get("status") == 1:
            res = json.loads(item["result"])[0] if isinstance(item["result"], str) else item["result"][0]
            break
    url = res["file"] if res["file"].startswith("http") else a.base + res["file"]
    with http(url, headers=hdr) as r, open(a.out, "wb") as f:
        f.write(r.read())
    print(f"{a.out} за {time.time() - t0:.1f}s, metas={res.get('metas')}, dit={res.get('dit_model')}")


if __name__ == "__main__":
    main()
