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

from . import i18n
from .parse import Step, dump_intents, oneline

GAP = 1200  # time fallback:步間隔 > 20 分鐘 = 換段
FORBID_LINK = re.compile(r"[#\[\]|]")  # Obsidian 連結/標題不安全字元(`/` 在標題保留、檔名才清)


class ClusterError(RuntimeError):
    pass


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
        try:
            return json.loads(t[a:b + 1])
        except Exception:
            pass
    raise ClusterError("分群輸出不是合法 JSON")


def normalize(clustering: dict, steps: list[Step], lang: str = i18n.DEFAULT_LANG) -> dict:
    """保證覆蓋率:漏的步驟丟『其他』;主題按最早步號排;清理名稱與標題。容忍髒 LLM 輸出。"""
    if not isinstance(clustering, dict):
        clustering = {}
    n = len(steps)
    raw, assigned = [], set()
    for t in clustering.get("topics", []) or []:
        if not isinstance(t, dict):
            continue
        idxs = sorted({s for s in (t.get("steps") or [])
                       if isinstance(s, int) and 1 <= s <= n and s not in assigned})
        for s in idxs:
            assigned.add(s)
        if idxs:
            raw.append({"name": _sanitize(str(t.get("name") or "")) or "untitled", "steps": idxs})
    leftover = [s for s in range(1, n + 1) if s not in assigned]
    if leftover:
        raw.append({"name": i18n.L(lang)["other"], "steps": leftover})
    raw.sort(key=lambda g: g["steps"][0])
    title = _sanitize(str(clustering.get("title") or "")) or \
        (oneline(steps[0].intent)[:24] if steps else "session")
    return {"title": title, "topics": raw}


def _cluster_claude_cli(steps: list[Step], model: str | None, timeout: int, lang: str) -> dict:
    payload = {"n": len(steps), "steps": dump_intents(steps)}
    prompt = i18n.cluster_rules(lang) + "\n\n## 輸入\n" + json.dumps(payload, ensure_ascii=False)
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
        raise ClusterError(f"claude -p 失敗(exit {r.returncode}): {(r.stderr or '')[:200]}")
    return _extract_json(r.stdout)


def _cluster_time(steps: list[Step], lang: str) -> dict:
    from datetime import datetime
    phase_fmt = i18n.L(lang)["phase"]
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
        topics.append({"name": f"{phase_fmt.format(n=pi + 1)} {when}".strip(), "steps": idxs})
    return {"title": oneline(steps[0].intent)[:24] if steps else "session", "topics": topics}


def cluster(steps: list[Step], backend: str = "claude_cli", model: str | None = None,
            timeout: int = 180, lang: str = i18n.DEFAULT_LANG) -> dict:
    if not steps:
        return {"title": "(empty)", "topics": []}
    if backend == "time":
        return normalize(_cluster_time(steps, lang), steps, lang)
    if backend == "claude_cli":
        return normalize(_cluster_claude_cli(steps, model, timeout, lang), steps, lang)
    raise ClusterError(f"未知分群後端:{backend}(支援 claude_cli / time)")
