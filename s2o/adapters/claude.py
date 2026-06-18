"""Claude Code 原生 session(jsonl)— 本來就是 Claude 格式,讀進來即可。"""
from __future__ import annotations
from ..parse import read_jsonl


def load(src_path):
    """→ (records, meta)。meta.date = 第一筆 timestamp;title 留空(交給分群產總標題)。"""
    records = read_jsonl(src_path)
    date = ""
    for r in records:
        ts = r.get("timestamp")
        if ts:
            date = ts
            break
    return records, {"date": date, "title": ""}
