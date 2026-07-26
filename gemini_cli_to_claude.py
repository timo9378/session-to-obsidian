#!/usr/bin/env python3
# Gemini CLI chat session (tmp/<hash>/chats/session-*.json) -> Claude Code 格式 jsonl
# 格式:{sessionId, startTime, messages:[{timestamp, type:"user"|"gemini", content:str}]}
import json, sys, os

def convert(src, out):
    o = json.load(open(src, encoding="utf-8"))
    sid = o.get("sessionId") or os.path.basename(src)
    start = o.get("startTime", "")
    n = 0
    with open(out, "w", encoding="utf-8") as w:
        for m in o.get("messages", []):
            if not isinstance(m, dict):
                continue
            t = m.get("type")
            role = "user" if t == "user" else "assistant"   # gemini / model → assistant
            c = m.get("content")
            if not isinstance(c, str) or not c.strip():
                continue   # 跳過非文字(工具事件等)
            rec = {
                "type": role,
                "sessionId": f"gemini-cli-{sid}",
                "timestamp": m.get("timestamp") or start,
                "message": {"role": role, "content": c},
            }
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n

if __name__ == "__main__":
    print(convert(sys.argv[1], sys.argv[2]), "records")
