"""jsonl(Claude Code 格式)→ 結構化步驟。無 LLM。

一個「步驟」= 一次使用者提問 + 其後助手的完整敘述 + 用到的工具/檔案/截圖。
抽圖只存原始 bytes 在 Step 上,實際寫檔交給 render(解耦輸出)。
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field

NOISE = re.compile(
    r"<(system-reminder|ide_opened_file|ide_selection|command-name|command-message"
    r"|command-args|local-command-stdout|local-command-stderr|local-command-caveat"
    r"|task-notification)[\s\S]*?</\1>",
    re.I,
)


def clean(t: str) -> str:
    return NOISE.sub("", t or "").strip()


def blocks(c):
    if isinstance(c, list):
        return c
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return []


def oneline(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def epoch(ts: str):
    try:
        from datetime import datetime
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


@dataclass
class Step:
    intent: str
    asst: list = field(default_factory=list)      # 助手文字片段
    tools: list = field(default_factory=list)
    files: set = field(default_factory=set)
    imgs: list = field(default_factory=list)       # [{"ext":, "data": bytes}]
    ts: float | None = None

    @property
    def prose(self) -> str:
        return "\n\n".join(self.asst).strip()

    @property
    def excerpt(self) -> str:
        return oneline(self.prose)[:300]


def parse_records(records, *, with_images: bool = False) -> list[Step]:
    """records = 可疊代的 Claude 格式訊息(dict,含 message.role/content、timestamp)。"""
    steps: list[Step] = []
    cur: Step | None = None
    for rec in records:
        if not isinstance(rec, dict):
            continue
        msg = rec.get("message") or {}
        role = msg.get("role") or rec.get("type")
        bs = blocks(msg.get("content"))
        if role == "user":
            text = " ".join(
                clean(b.get("text", ""))
                for b in bs
                if isinstance(b, dict) and b.get("type") == "text"
            ).strip()
            imgs_here = [b for b in bs if isinstance(b, dict) and b.get("type") == "image"]
            if text and len(text) > 1:
                cur = Step(intent=text, ts=epoch(rec.get("timestamp", "")))
                steps.append(cur)
            if cur is not None and with_images:
                import base64
                for im in imgs_here:
                    src = im.get("source") or {}
                    data = src.get("data")
                    if not data:
                        continue
                    ext = src.get("media_type", "image/png").split("/")[-1].replace("jpeg", "jpg")
                    try:
                        cur.imgs.append({"ext": ext, "data": base64.b64decode(data)})
                    except Exception:
                        pass
        elif role == "assistant" and cur is not None:
            for b in bs:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    t = clean(b.get("text", ""))
                    if t:
                        cur.asst.append(t)
                elif b.get("type") == "tool_use":
                    cur.tools.append(b.get("name", "?"))
                    inp = b.get("input") or {}
                    fp = inp.get("file_path") or inp.get("path") or inp.get("notebook_path")
                    if fp:
                        cur.files.add(fp)
    return steps


def read_jsonl(path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def dump_intents(steps: list[Step]) -> list[dict]:
    """給分群 agent 的精簡輸入:提問 + 該步檔名(basename)+ 助手首句 gist。
    純提問在 context-dependent 步驟(「這是連結」)會誤判 → files/gist 是便宜的消歧訊號。"""
    import os
    out = []
    for i, s in enumerate(steps):
        files = sorted({os.path.basename(f) for f in s.files})[:6]
        gist = oneline(s.prose)[:160]
        d = {"i": i + 1, "intent": oneline(s.intent)}
        if files:
            d["files"] = files
        if gist:
            d["gist"] = gist
        out.append(d)
    return out
