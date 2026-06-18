"""VS Code Copilot Chat session(append-log jsonl)→ Claude Code 格式 records。

VS Code chat 格式:首行 kind=0 = 初始狀態快照;其後 kind=1 = 在路徑 k 設值(replace),
kind=2 = 對 k 指向的陣列 append/splice(i=起始索引,None=接尾端,v 可能為 None=截斷需 guard)。
串流重放後得最終 requests[];每個 request:message.text=提問,response[]=value(助手文字)
+ inlineReference(行內檔名)+ toolInvocationSerialized(工具)。
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone


def _iso(ms):
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# 工具動詞正規化(Copilot invocationMessage → 類 Claude 工具名)
_VERB = {
    "Reading": "Read", "Read": "Read", "Creating": "Write", "Created": "Write",
    "Replacing": "Edit", "Replaced": "Edit", "Editing": "Edit", "Edited": "Edit",
    "Running": "Bash", "Ran": "Bash", "Searching": "Grep", "Searched": "Grep",
    "Fetching": "WebFetch", "Fetched": "WebFetch", "Using": "Tool", "Completed": "Task",
}


def _toolname(label):
    w = (label or "").strip().split()
    if not w:
        return "Tool"
    return _VERB.get(w[0], (w[0][:18] or "Tool"))


def _filepath(part):
    m = re.search(r'file:///([^)#"\\\s]+)', json.dumps(part, ensure_ascii=False))
    return "/" + m.group(1) if m else None


def _replay(src_path) -> dict:
    """串流重放 append-log → 最終 state(dict)。"""
    state = None
    with open(src_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if state is None:
                if o.get("kind") == 0:
                    state = o.get("v") or {}
                continue
            k = o.get("k")
            kind = o.get("kind")
            v = o.get("v")
            i = o.get("i")
            if not k:
                continue
            cur = state
            ok = True
            for key in k[:-1]:
                try:
                    cur = cur[key]
                except Exception:
                    ok = False
                    break
            if not ok:
                continue
            last = k[-1]
            if kind == 1:
                try:
                    cur[last] = v
                except Exception:
                    pass
            elif kind == 2:
                if not isinstance(v, list):
                    continue
                try:
                    arr = cur[last]
                    if not isinstance(arr, list):
                        arr = []
                        cur[last] = arr
                except Exception:
                    arr = []
                    try:
                        cur[last] = arr
                    except Exception:
                        continue
                if i is None:
                    arr.extend(v)
                else:
                    for j, it in enumerate(v):
                        pos = i + j
                        if pos < len(arr):
                            arr[pos] = it
                        else:
                            arr.append(it)
    if state is None:
        raise ValueError("找不到 kind=0 標頭,不是 VS Code Copilot chat append-log")
    return state


def load(src_path):
    """→ (records, meta)。records = Claude 格式訊息 list;meta = {date, title}。"""
    state = _replay(src_path)
    reqs = state.get("requests") or []
    records = []
    first_user = ""
    for r in reqs:
        if not isinstance(r, dict):
            continue
        msg = r.get("message") or {}
        prompt = (msg.get("text") if isinstance(msg, dict) else "") or ""
        prompt = prompt.strip()
        ts = _iso(r.get("timestamp"))
        if prompt:
            if not first_user:
                first_user = prompt
            records.append({"timestamp": ts, "message": {"role": "user", "content": prompt}})
        prose, content = [], []
        for part in (r.get("response") or []):
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("value"), str):
                prose.append(part["value"])
            elif part.get("kind") == "inlineReference":
                ref = part.get("inlineReference") or {}
                nm = ref.get("name") or (os.path.basename(ref["path"]) if ref.get("path") else "")
                if nm:
                    prose.append(f"`{nm}`")
            elif part.get("kind") == "toolInvocationSerialized":
                im = part.get("invocationMessage")
                pm = part.get("pastTenseMessage")
                label = (pm.get("value") if isinstance(pm, dict) else pm) or \
                        (im.get("value") if isinstance(im, dict) else im) or ""
                tu = {"type": "tool_use", "name": _toolname(label), "input": {}}
                fp = _filepath(part)
                if fp:
                    tu["input"]["file_path"] = fp
                content.append(tu)
        text = "".join(prose).strip()
        bs = ([{"type": "text", "text": text}] if text else []) + content
        if bs:
            records.append({"timestamp": ts, "message": {"role": "assistant", "content": bs}})

    title = (state.get("customTitle") or "").strip() or re.sub(r"\s+", " ", first_user)[:50]
    meta = {"date": _iso(state.get("creationDate")), "title": title}
    return records, meta
