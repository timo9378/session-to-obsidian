"""掃 sessions/*/*.md → INDEX.md(一頁總覽 + Claude compact 後的 recall 地圖)。
自帶不依賴中間檔:標題從 H1、主題清單從 TOC 解析。
"""
from __future__ import annotations
import glob
import os
import re


def build_index(sessions_dir: str) -> dict:
    rows = []
    for md in glob.glob(os.path.join(sessions_dir, "*", "*.md")):
        slug = os.path.basename(md)[:-3]
        if slug == "INDEX":
            continue
        lines = open(md, encoding="utf-8").read().split("\n")
        if lines and lines[0].strip() == "---":            # 跳過 YAML frontmatter
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
            lines = lines[end + 1:]
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), slug)
        stats = next((re.split(r"·\s*節點圖", l[2:])[0].strip()
                      for l in lines if l.startswith("> ") and "步" in l), "")
        topics = [m.group(1) for l in lines if l.startswith("- [[#")
                  for m in [re.search(r"\|([^\]]+)\]\]", l)] if m]
        m = re.match(r"(\d{4})-(\d{2})", slug)
        ym = f"{m.group(1)}-{m.group(2)}" if m else "其他"
        rows.append({"slug": slug, "title": title, "stats": stats, "topics": topics, "ym": ym})

    rows.sort(key=lambda r: r["slug"])
    L = ["# Session 索引\n",
         f"> 自動產生(`s2o index`,別手改)· {len(rows)} 場\n",
         "> **recall 用法**:在這裡找到相關 session → 開該筆記 → Outline 跳主題(或用 Obsidian 搜尋)。\n",
         "---\n"]
    cur = None
    for r in sorted(rows, key=lambda r: r["ym"]):
        if r["ym"] != cur:
            cur = r["ym"]
            L.append(f"\n## {cur}\n")
        L.append(f"- [[{r['slug']}|{r['title']}]] — {r['stats']}")
        if r["topics"]:
            L.append(f"  - 主題:{' · '.join(r['topics'])}")
    with open(os.path.join(sessions_dir, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return {"sessions": len(rows), "topics": sum(len(r["topics"]) for r in rows)}
