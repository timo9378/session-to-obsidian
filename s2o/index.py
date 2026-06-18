"""掃 sessions/*/*.md → INDEX.md(一頁總覽 + Claude compact 後的 recall 地圖)。
只認帶 s2o frontmatter(originSessionId)的筆記,避免把使用者自己的 .md 誤列入。
"""
from __future__ import annotations
import glob
import os
import re

from . import i18n

_STATS_TAIL = re.compile(r"·\s*[^·]*\[\[.*$")  # 去掉 stats 尾端「· <canvas標籤> [[x.canvas]]」


def _has_frontmatter_id(lines) -> bool:
    if not lines or lines[0].strip() != "---":
        return False
    for ln in lines[1:25]:
        if ln.strip() == "---":
            return False
        if ln.startswith("originSessionId:"):
            return True
    return False


def build_index(sessions_dir: str, lang: str = i18n.DEFAULT_LANG) -> dict:
    lab = i18n.L(lang)
    rows = []
    for md in glob.glob(os.path.join(sessions_dir, "*", "*.md")):
        slug = os.path.basename(md)[:-3]
        if slug == "INDEX":
            continue
        try:
            lines = open(md, encoding="utf-8").read().split("\n")
        except Exception:
            continue
        if not _has_frontmatter_id(lines):     # 只認 s2o 產生的 session
            continue
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        body = lines[end + 1:]
        title = next((l[2:].strip() for l in body if l.startswith("# ")), slug)
        stats = next((_STATS_TAIL.sub("", l[2:]).strip()
                      for l in body if l.startswith("> ") and ("步" in l or "step" in l)), "")
        topics = [m.group(1) for l in body if l.startswith("- [[#")
                  for m in [re.search(r"\|([^\]]+)\]\]", l)] if m]
        m = re.match(r"(\d{4})-(\d{2})", slug)
        ym = f"{m.group(1)}-{m.group(2)}" if m else "其他"
        rows.append({"slug": slug, "title": title, "stats": stats, "topics": topics, "ym": ym})

    rows.sort(key=lambda r: r["slug"])
    L = [f"# {lab['idx_title']}\n",
         f"> {lab['idx_auto']} · {len(rows)} {lab['idx_sessions']}\n",
         f"> {lab['idx_recall']}\n",
         "---\n"]
    cur = None
    for r in sorted(rows, key=lambda r: r["ym"]):
        if r["ym"] != cur:
            cur = r["ym"]
            L.append(f"\n## {cur}\n")
        L.append(f"- [[{r['slug']}|{r['title']}]] — {r['stats']}")
        if r["topics"]:
            L.append(f"  - {lab['idx_topics']}:{' · '.join(r['topics'])}")
    with open(os.path.join(sessions_dir, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return {"sessions": len(rows), "topics": sum(len(r["topics"]) for r in rows)}
