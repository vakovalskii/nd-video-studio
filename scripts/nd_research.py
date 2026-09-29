#!/usr/bin/env python3
"""Ресёрч под ролик через Search API хаба: запросы → выдержки с источниками в sources.md.

Сценарий потом пишется только по этим выдержкам, и в кадре видно, что подтверждено, а что оценка.
Поиск тратит квоту Search API (web дороже tg).

  ND_API_KEY=sk-... python3 scripts/nd_research.py projects/x/sources.md "Jev TypeSafe AI architecture" "Jev pricing latency"
  ... --tg "Jev модель"          # ещё и поиск по Telegram-каналам
"""

import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from ndv_common import nd_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("queries", nargs="+")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--tg", nargs="*", default=[], help="запросы по Telegram-каналам")
    ap.add_argument("--chars", type=int, default=1500, help="сколько знаков выдержки на источник")
    a = ap.parse_args()

    parts, seen = [], set()
    for q in a.queries:
        res = nd_json("/v1/search/web", {"query": q, "limit": a.limit})
        parts.append(f"## web: {q}\n")
        for r in res.get("results", []):
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            parts.append(f"### {r.get('title', '').strip()}\n{r['url']} {r.get('date') or ''}\n\n"
                         f"{(r.get('content') or '').strip()[:a.chars]}\n")
        print(f"web «{q}»: {len(res.get('results', []))}")
    for q in a.tg:
        res = nd_json(f"/v1/search/tg?q={urllib.parse.quote(q)}&limit={a.limit}")
        parts.append(f"## tg: {q}\n")
        for r in res.get("results", []):
            parts.append(f"### {r.get('title', '').strip()}\n{r.get('url', '')} {r.get('date') or ''}\n\n"
                         f"{(r.get('content') or '').strip()[:a.chars]}\n")
        print(f"tg «{q}»: {len(res.get('results', []))}")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        f.write("# Источники\n\n" + "\n".join(parts))
    print("→", a.out)


if __name__ == "__main__":
    main()
