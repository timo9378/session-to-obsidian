"""Claude Code 原生 session(jsonl)— 本來就是 Claude 格式,讀進來即可。"""
from __future__ import annotations
from ..parse import read_jsonl, session_id


def load(src_path):
    """→ (records, meta)。meta.date = 第一筆 timestamp;session_id 供去重;title 留空。"""
    records = read_jsonl(src_path)
    date = ""
    for r in records:
        ts = r.get("timestamp")
        if ts:
            date = ts
            break
    return records, {"date": date, "title": "", "session_id": session_id(records)}
