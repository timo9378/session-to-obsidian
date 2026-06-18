"""標題 → 跨平台安全的檔名 slug(vault 走 Syncthing 到 Windows/Android,要嚴格 sanitize)。"""
from __future__ import annotations
import re

# Windows/Android/Linux 共同禁用 + Obsidian 連結不安全
_FORBID = re.compile(r'[\\/:*?"<>|\n\r\t#\[\]]')


def title_slug(title: str, width: int = 48) -> str:
    """按【顯示寬度】截長(CJK=2、半形=1),en 標題較長也不被切太短。"""
    s = _FORBID.sub("", title or "")
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    w, cut, truncated = 0, len(s), False
    for i, c in enumerate(s):
        w += 2 if ord(c) > 0x2E80 else 1
        if w > width:
            cut, truncated = i, True
            break
    s = s[:cut]
    if truncated:
        s = re.sub(r"[A-Za-z0-9]+$", "", s).strip()  # 別切在半個英文字中間
    return s.strip(" .、·-+,")


def session_slug(date: str, source: str, title: str) -> str:
    """date 取 YYYY-MM-DD(或來源給的前綴);→ <date>-<source>-<標題slug>。"""
    d = ""
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", date or "")
    if m:
        d = f"{m.group(1)}-{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
    ts = title_slug(title) or "session"
    parts = [p for p in (d, source, ts) if p]
    return "-".join(parts)
