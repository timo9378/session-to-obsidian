"""語意主題分群:提問清單 → {title, topics}。

後端:
- claude_cli:呼叫本機 `claude -p` headless(host Claude,零金鑰,需裝 Claude Code)。
- time:純時間間隔分段,完全不用 LLM 的降級模式。

契約:每步恰好一主題(不重不漏);主題可非連續;複合提問不拆歸主導線;
主題按最早步號排;tiny 場(同一事)就 1 主題。詳見 SPEC。
"""
from __future__ import annotations
import json
import re
import subprocess

from .parse import Step, dump_intents, oneline

GAP = 1200  # time fallback:步間隔 > 20 分鐘 = 換段
FORBID_LINK = re.compile(r"[#\[\]|]")  # Obsidian 連結/標題不安全字元(`/` 在標題保留、檔名才清)


class ClusterError(RuntimeError):
    pass


RULES = """你是對話主題分群器。輸入是一場 AI coding session 的步驟清單,每步有 intent(提問)、files(碰的檔名)、gist(助手首句)。把步驟分到幾條連貫主題,並給整場一個總標題。

規則(嚴格遵守):
1. 每步恰好歸一主題(不重不漏,所有 1..n 都要被分到)。
2. 一主題 = 一條連貫的問題/任務串。別碎到每步一主題;tiny(≤5 步同一事)→ 1 主題;大場(>50 步)可較多主題。
3. 主題【可非連續】:時間隔開但同一條線的步驟歸同一主題(中間插別的、後面回來收尾 commit → 收尾步歸回那條線)。
4. 複合提問【不拆】,整步歸主導/最主要那條線(看重心 + files + gist + 後續步接哪條線)。
5. files/gist 是消歧訊號:提問字面看不出時(如「這是連結」),用 files/gist 判斷屬哪條線。
6. 主題名簡短中文(≤16 字),總標題涵蓋全場(≤24 字);名稱與標題不可含 # [ ] | 與斜線。
7. 不要空主題。

只輸出一段 JSON(無 code fence、無其他文字):
{"title":"總標題","topics":[{"name":"主題名","steps":[1,2,3]}, ...]}
steps 用 1-based 原始步號。"""


def _sanitize(s: str) -> str:
    return FORBID_LINK.sub("", (s or "")).replace("/", "、").replace("\\", "、").strip()


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        return json.loads(t[a:b + 1])
    raise ClusterError("分群輸出不是合法 JSON")


def normalize(clustering: dict, steps: list[Step]) -> dict:
    """保證覆蓋率:漏的步驟丟『其他 / 未分類』;主題按最早步號排;清理名稱與標題。"""
    n = len(steps)
    raw, assigned = [], set()
    for t in clustering.get("topics", []):
        idxs = sorted({s for s in t.get("steps", []) if 1 <= s <= n and s not in assigned})
        for s in idxs:
            assigned.add(s)
        if idxs:
            raw.append({"name": _sanitize(t.get("name", "") or "未命名"), "steps": idxs})
    leftover = [s for s in range(1, n + 1) if s not in assigned]
    if leftover:
        raw.append({"name": "其他 / 未分類", "steps": leftover})
    raw.sort(key=lambda g: g["steps"][0])
    title = _sanitize(clustering.get("title", "")) or (oneline(steps[0].intent)[:24] if steps else "session")
    return {"title": title, "topics": raw}


def _cluster_claude_cli(steps: list[Step], model: str | None, timeout: int) -> dict:
    payload = {"n": len(steps), "steps": dump_intents(steps)}
    prompt = RULES + "\n\n## 輸入\n" + json.dumps(payload, ensure_ascii=False)
    # prompt 走 stdin,不走 argv:大場 dump 會超過 ARG_MAX(Argument list too long)。
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise ClusterError("找不到 `claude` CLI(語意分群需要本機安裝 Claude Code;或改用 --cluster time)")
    except subprocess.TimeoutExpired:
        raise ClusterError(f"claude -p 逾時(>{timeout}s)")
    if r.returncode != 0:
        raise ClusterError(f"claude -p 失敗(exit {r.returncode}): {r.stderr[:200]}")
    return _extract_json(r.stdout)


def _cluster_time(steps: list[Step]) -> dict:
    from datetime import datetime
    phases, ph, last = [], [], None
    for i, s in enumerate(steps):
        if ph and s.ts and last and (s.ts - last) > GAP:
            phases.append(ph)
            ph = []
        ph.append(i + 1)
        last = s.ts or last
    if ph:
        phases.append(ph)
    topics = []
    for pi, idxs in enumerate(phases):
        when = ""
        ts0 = steps[idxs[0] - 1].ts
        if ts0:
            when = datetime.fromtimestamp(ts0).strftime("%m/%d %H:%M")
        topics.append({"name": f"第 {pi + 1} 段 {when}".strip(), "steps": idxs})
    return {"title": oneline(steps[0].intent)[:24] if steps else "session", "topics": topics}


def cluster(steps: list[Step], backend: str = "claude_cli", model: str | None = None,
            timeout: int = 180) -> dict:
    if not steps:
        return {"title": "(空)", "topics": []}
    if backend == "time":
        return normalize(_cluster_time(steps), steps)
    if backend == "claude_cli":
        return normalize(_cluster_claude_cli(steps, model, timeout), steps)
    raise ClusterError(f"未知分群後端:{backend}(支援 claude_cli / time)")
