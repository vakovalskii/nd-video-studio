#!/usr/bin/env python3
"""Frame images via the hub Image API (FLUX): prompts → assets/*.png.

Generation is async: submit → poll /v1/images/tasks/{uid} → binary result.
Optionally remove the background (for cut-out objects over a scene) or upscale.
Each operation = 1 unit of image quota.

  ND_API_KEY=sk-... python3 scripts/nd_images.py projects/x/assets "hero:isometric glowing chip on dark wafer" \
      "bg:dark blue circuit board macro, shallow depth of field" --remove-bg hero
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import http, nd_auth, nd_base, nd_json, nd_multipart  # noqa: E402


def wait(uid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = nd_json(f"/v1/images/tasks/{uid}")
        status = str(st.get("status", "")).lower()
        if status in ("done", "completed", "success", "succeeded", "finished"):
            return st
        if status in ("failed", "error", "cancelled"):
            raise SystemExit(f"task {uid} failed: {st}")
        time.sleep(3)
    raise SystemExit(f"task {uid} timed out after {timeout} s")


def fetch(uid, path):
    with http(f"{nd_base()}/v1/images/tasks/{uid}/result", headers=nd_auth()) as r, open(path, "wb") as f:
        f.write(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("items", nargs="+", help="name:prompt")
    ap.add_argument("--remove-bg", nargs="*", default=[], help="names to remove the background from")
    ap.add_argument("--upscale", nargs="*", default=[], help="names to upscale ×4")
    ap.add_argument("--no-translate", action="store_true", help="don't translate RU prompts to EN")
    ap.add_argument("--options", default="{}", help='generation options JSON, e.g. {"width":1920,"height":1080}')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    for item in a.items:
        name, prompt = item.split(":", 1)
        body = {"prompt": prompt, "translate": not a.no_translate}
        opts = json.loads(a.options)
        if opts:
            body["options"] = opts
        sub = nd_json("/v1/images/generate", body)
        wait(sub["task_uid"])
        path = os.path.join(a.out_dir, f"{name}.png")
        fetch(sub["task_uid"], path)
        print(f"{name}: {path} | {sub.get('prompt_used', prompt)[:80]}")
        for flag, endpoint in ((a.remove_bg, "/v1/images/background/remove"), (a.upscale, "/v1/images/upscale")):
            if name not in flag:
                continue
            with open(path, "rb") as f:
                sub2 = nd_multipart(endpoint, {}, {"image": (os.path.basename(path), f.read(), "image/png")})
            wait(sub2["task_uid"])
            fetch(sub2["task_uid"], path)
            print(f"  {name}: {endpoint.rsplit('/', 1)[-1]} ok")
    q = nd_json("/v1/images/quota")
    print("quota:", json.dumps(q, ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
