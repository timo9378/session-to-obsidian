#!/usr/bin/env python3
# Cline / Roo-Code task -> Claude Code 格式 jsonl(餵 s2o --source claude)
# 用法:cline_to_claude.py <task_dir> <out.jsonl>
# Cline 的 api_conversation_history.json 本身就是 Anthropic messages 陣列({role,content[]}),
# 只要逐則包成 Claude Code 的 {type,sessionId,timestamp,message} 一行即可。
import json, sys, os
from datetime import datetime, timezone


def session_ts(taskdir):
    b = os.path.basename(taskdir.rstrip("/"))
    if b.isdigit():                       # cline:資料夾名 = ms epoch
        return datetime.fromtimestamp(int(b) / 1000, tz=timezone.utc)
    f = os.path.join(taskdir, "api_conversation_history.json")   # roo:UUID → 用檔案 mtime
    return datetime.fromtimestamp(os.path.getmtime(f), tz=timezone.utc)


def convert(taskdir, out):
    hist = os.path.join(taskdir, "api_conversation_history.json")
    msgs = json.load(open(hist, encoding="utf-8"))
    sid = os.path.basename(taskdir.rstrip("/"))
    iso = session_ts(taskdir).isoformat().replace("+00:00", "Z")
    n = 0
    with open(out, "w", encoding="utf-8") as w:
        for m in msgs:
            if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
                continue
            rec = {
                "type": m["role"],
                "sessionId": f"cline-{sid}",
                "timestamp": iso,
                "message": {"role": m["role"], "content": m.get("content")},
            }
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


if __name__ == "__main__":
    print(convert(sys.argv[1], sys.argv[2]), "records")
