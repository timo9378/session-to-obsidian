"""來源偵測 + 載入。回傳 (records[Claude格式], meta{date,title})。"""
from __future__ import annotations
import json
from . import claude, copilot


def detect(src_path) -> str:
    """嗅第一行:Copilot append-log 首行有 kind 鍵;Claude 原生是 message/type 訊息。"""
    with open(src_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                return "claude"
            return "copilot" if "kind" in o else "claude"
    return "claude"


def load(src_path, source: str = "auto"):
    if source == "auto":
        source = detect(src_path)
    mod = {"claude": claude, "copilot": copilot}.get(source)
    if mod is None:
        raise ValueError(f"未知來源:{source}(支援 claude / copilot / auto)")
    records, meta = mod.load(src_path)
    meta["source"] = source
    return records, meta
