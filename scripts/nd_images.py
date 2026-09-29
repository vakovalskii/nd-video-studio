#!/usr/bin/env python3
"""Картинки для кадров через Image API хаба (FLUX): промпты → assets/*.png.

Генерация асинхронная: submit → опрос /v1/images/tasks/{uid} → результат бинарём.
Опционально сразу снять фон (для вырезанных объектов поверх сцены) или сделать апскейл.
Каждая операция = 1 единица квоты картинок.

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
            raise SystemExit(f"задача {uid} упала: {st}")
        time.sleep(3)
    raise SystemExit(f"задача {uid} не успела за {timeout} с")


def fetch(uid, path):
    with http(f"{nd_base()}/v1/images/tasks/{uid}/result", headers=nd_auth()) as r, open(path, "wb") as f:
        f.write(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("items", nargs="+", help="имя:промпт")
    ap.add_argument("--remove-bg", nargs="*", default=[], help="имена, которым снять фон")
    ap.add_argument("--upscale", nargs="*", default=[], help="имена для апскейла ×4")
    ap.add_argument("--no-translate", action="store_true", help="не переводить RU-промпт на EN")
    ap.add_argument("--options", default="{}", help='JSON опций генерации, например {"width":1920,"height":1080}')
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
    print("квота:", json.dumps(q, ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
