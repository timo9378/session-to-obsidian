"""steps + 分群結果 → Obsidian:依主題分區的 .md(頂部 TOC)+ 主題分組彩色 Canvas + 截圖。

硬規則(得來不易,勿動):
- 助手敘述裡的 ATX 標題會污染 Obsidian Outline → demote 成粗體(fence 內的 `# 註解` 保留)。
- Copilot 抓的 code block 常被工具呼叫打斷、缺收尾 ``` → 每步 fence 強制配對,免 Obsidian 全域 parity 錯亂吞後文。
"""
from __future__ import annotations
import json
import os
import re

from . import i18n
from .parse import Step, oneline

PCOLORS = ["1", "2", "3", "4", "5", "6"]  # 紅橙黃綠青紫,循環
GX, STEPW, IMGW = 40, 460, 300
_PHASE_RE = re.compile(r"^(第 ?\d+ ?段|Phase \d+)")


def _dwidth(s: str) -> int:
    """顯示寬度:CJK/全形算 2,半形算 1(canvas 高度估算才不會低估溢出)。"""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


def demote_headings(t: str) -> str:
    out, fence = [], None  # fence = 開啟的圍欄字串(``` 或 ~~~),None=不在 fence 內
    for ln in t.split("\n"):
        st = ln.lstrip()
        mark = "```" if st.startswith("```") else ("~~~" if st.startswith("~~~") else None)
        if mark:
            if fence is None:
                fence = mark
            elif fence == mark:        # 只被同型圍欄關閉(混用 ```/~~~ 不誤判)
                fence = None
            out.append(ln)
            continue
        if fence is None:
            m = re.match(r"\s*#{1,6}\s+(.*\S)\s*$", ln)
            if m:
                out.append(f"**{m.group(1)}**")
                continue
        out.append(ln)
    if fence is not None:
        out.append(fence)
    return "\n".join(out)


def _heading(gi: int, name: str, lab: dict) -> str:
    return name if _PHASE_RE.match(name) else f"{lab['topic']} {gi + 1} · {name}"


def _write_images(steps, groups_idx, attach_abs, noimg):
    if noimg:
        return {}, 0
    os.makedirs(attach_abs, exist_ok=True)
    out, k = {}, 0
    for i in sorted({i for idxs in groups_idx for i in idxs}):
        for im in steps[i].imgs:
            fn = f"shot_{k:03d}.{im['ext']}"
            try:
                with open(os.path.join(attach_abs, fn), "wb") as f:
                    f.write(im["data"])
                out.setdefault(i, []).append(fn)
                k += 1
            except Exception:
                pass
    return out, k


def render(steps: list[Step], clustering: dict, out_dir: str, slug: str,
           attach_abs: str, attach_rel: str, noimg: bool = True,
           origin_id: str = "", source: str = "", lang: str = i18n.DEFAULT_LANG) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    lab = i18n.L(lang)
    title = clustering.get("title") or slug
    groups = [{"name": t["name"], "idxs": [s - 1 for s in t["steps"]]}
              for t in clustering.get("topics", [])]
    imgmap, img_n = _write_images(steps, [g["idxs"] for g in groups], attach_abs, noimg)
    headings = [_heading(gi, g["name"], lab) for gi, g in enumerate(groups)]

    # ── Canvas:每組一彩色 group 框,框內步驟直排,截圖掛右側 ──
    nodes, edges, Y, prev = [], [], 0, None
    for gi, g in enumerate(groups):
        y = Y + 50
        maxx = GX + STEPW
        for i in g["idxs"]:
            s = steps[i]
            intent = oneline(s.intent)
            intent = (intent[:64] + "…") if len(intent) > 64 else intent
            exc = s.excerpt or lab["tool_only"]
            toolset = sorted(set(s.tools))
            foot = (f"\n\n🔧 {', '.join(toolset[:5])}" if toolset else "") + \
                   (f" · 📄{len(s.files)}" if s.files else "")
            txt = f"**#{i + 1}. {intent}**\n\n{exc}{'…' if len(s.excerpt) >= 300 else ''}{foot}"
            h = max(120, (_dwidth(txt) // 40 + txt.count(chr(10)) + 2) * 26)
            nid = f"step{i}"
            nodes.append({"id": nid, "type": "text", "x": GX, "y": y, "width": STEPW,
                          "height": h, "color": PCOLORS[gi % 6], "text": txt})
            if prev:
                edges.append({"id": f"e{i}", "fromNode": prev, "toNode": nid,
                              "fromSide": "bottom", "toSide": "top"})
            ix = GX + STEPW + 50
            for j, fn in enumerate(imgmap.get(i, [])):
                nodes.append({"id": f"img{i}_{j}", "type": "file",
                              "file": f"{attach_rel}/{slug}/{fn}", "x": ix, "y": y,
                              "width": IMGW, "height": 200})
                ix += IMGW + 30
            maxx = max(maxx, ix)
            y += max(h, 220 if imgmap.get(i) else 0) + 40
            prev = nid
        nodes.insert(0, {"id": f"grp{gi}", "type": "group", "x": 0, "y": Y, "width": maxx + 40,
                         "height": (y - Y) + 30,
                         "label": f"{headings[gi]} · {len(g['idxs'])} {lab['steps']}",
                         "color": PCOLORS[gi % 6]})
        Y = y + 90
    with open(os.path.join(out_dir, f"{slug}.canvas"), "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "edges": edges}, f, ensure_ascii=False)

    # ── 回顧筆記:frontmatter(供去重/溯源,值一律 escape 防注入)+ TOC + 主題分區 ──
    L = []
    if origin_id:
        oid = json.dumps(origin_id.replace("\n", " ").replace("\r", " "), ensure_ascii=False)
        src = json.dumps(source or "unknown", ensure_ascii=False)
        L += ["---", f"originSessionId: {oid}", f"source: {src}", "---", ""]
    L += [f"# {title}\n",
          f"> {len(steps)} {lab['steps']} · {len(groups)} {lab['topics']} · {img_n} {lab['images']}"
          f" · {lab['canvas']} [[{slug}.canvas]]\n",
          f"## {lab['contents']}\n"]
    for gi, g in enumerate(groups):
        nums = " ".join(f"#{i + 1}" for i in g["idxs"])
        L.append(f"- [[#{headings[gi]}|{g['name']}]] · {len(g['idxs'])} {lab['steps']} `{nums}`")
    L.append("\n---\n")
    for gi, g in enumerate(groups):
        L.append(f"\n# {headings[gi]}\n")
        for i in g["idxs"]:
            s = steps[i]
            L.append(f"## #{i + 1} · {oneline(s.intent)[:100]}")
            L.append(f"> **{lab['asked']}**:{oneline(s.intent)}\n")
            L.append(demote_headings(s.prose) if s.prose else f"_{lab['tool_only']}_")
            meta = []
            if s.tools:
                meta.append(f"🔧 {', '.join(sorted(set(s.tools)))}")
            if s.files:
                fl = sorted(s.files)
                meta.append("📄 " + ", ".join("`" + os.path.basename(f) + "`" for f in fl[:10]) +
                            (" …" if len(fl) > 10 else ""))
            if meta:
                L.append("\n" + " · ".join(meta))
            for fn in imgmap.get(i, []):
                L.append(f"\n![[{attach_rel}/{slug}/{fn}]]")
            L.append("\n---")
    with open(os.path.join(out_dir, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return {"steps": len(steps), "topics": len(groups), "images": img_n}
