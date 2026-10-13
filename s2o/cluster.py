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
import shutil
import subprocess
import tempfile
from pathlib import Path

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


def normalize(clustering: dict, steps: list[Step], lang: str = i18n.DEFAULT_LANG,
              sanitize_names: bool = True) -> dict:
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
            name = str(t.get("name") or "")
            raw.append({"name": (_sanitize(name) if sanitize_names else name.strip()) or "untitled",
                        "steps": idxs})
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
    return _run_claude(prompt, model, timeout)


def _run_claude(prompt: str, model: str | None, timeout: int) -> dict:
    # prompt 走 stdin,不走 argv:大場 dump 會超過 ARG_MAX(Argument list too long)。
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    # headless `claude -p` 會把這次呼叫存成一場 session 到 ~/.claude/projects/<cwd 編碼>/,
    # 污染使用者的 session picker。改在拋棄式 temp cwd 執行,結束後連那個 project 夾一起清掉。
    tmp_cwd = tempfile.mkdtemp(prefix="s2ocluster")
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=timeout, cwd=tmp_cwd)
    except FileNotFoundError:
        raise ClusterError("找不到 `claude` CLI(語意分群需要本機安裝 Claude Code;或改用 --cluster time)")
    except subprocess.TimeoutExpired:
        raise ClusterError(f"claude -p 逾時(>{timeout}s)")
    finally:
        _cleanup_cluster_sessions(tmp_cwd)
    if r.returncode != 0:
        raise ClusterError(f"claude -p 失敗(exit {r.returncode}): {(r.stderr or '')[:200]}")
    return _extract_json(r.stdout)


def _cleanup_cluster_sessions(tmp_cwd: str) -> None:
    """清掉 headless 分群留下的痕跡:Claude Code 依 cwd 編碼落在 ~/.claude/projects 的 session 夾
    + temp cwd 本身。用唯一前綴 glob 比對,免去重現 Claude 的路徑編碼規則(且順手清掉殘留)。"""
    try:
        for p in (Path.home() / ".claude" / "projects").glob("*s2ocluster*"):
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass
    shutil.rmtree(tmp_cwd, ignore_errors=True)


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


# ── 增量分群:續寫的場次沿用舊分組,只替新步驟分群(主題名不再每次同步都變) ──
_TOC_RE = re.compile(r"^- \[\[#[^|\]]*\|(.+?)\]\] · \d+ \S+ `([^`]*)`\s*$")
_STEP_RE = re.compile(r"^## #(\d+) · (.*)$")
_PHASE_RE = re.compile(r"^(第 ?\d+ ?段|Phase \d+)")


def load_previous(md_text: str, steps: list[Step]) -> dict | None:
    """從既有筆記讀回 {title, topics, n}。舊步驟必須跟這次解析出的步驟逐一對得上
    (步驟標題 = 提問前 100 字),否則代表結構變了 → None,讓呼叫端整場重新分群。
    舊版是時間分段(分群失敗時的降級)也回 None,不要永遠卡在時間分段。"""
    lines = md_text.split("\n")
    title, topics, heads = None, [], {}
    in_front = bool(lines) and lines[0].strip() == "---"
    for i, ln in enumerate(lines):
        if in_front:
            if i > 0 and ln.strip() == "---":
                in_front = False
            continue
        if title is None and ln.startswith("# "):
            title = ln[2:].strip()
            continue
        m = _TOC_RE.match(ln)
        if m:
            nums = [int(x) for x in re.findall(r"#(\d+)", m.group(2))]
            if nums:
                topics.append({"name": m.group(1).strip(), "steps": nums})
            continue
        m = _STEP_RE.match(ln)
        if m:
            heads[int(m.group(1))] = m.group(2)
    if not topics or not heads:
        return None
    if all(_PHASE_RE.match(t["name"]) for t in topics):
        return None
    n_old = max(heads)
    if n_old > len(steps):
        return None
    mism = sum(1 for k, h in heads.items() if h != oneline(steps[k - 1].intent)[:100])
    if mism > max(1, n_old // 50):          # 容忍 ≤2%(清理規則小幅調整),再多就視為結構改變
        return None
    return {"title": title or "", "topics": topics, "n": n_old}


def cluster_incremental(steps: list[Step], prev: dict, model: str | None = None,
                        timeout: int = 180, lang: str = i18n.DEFAULT_LANG,
                        use_model: bool = True) -> tuple[dict, int]:
    """沿用 prev 的分組;只把新增步驟(prev['n'] 之後)交給模型歸類。回傳 (分群, 新步驟數)。
    沒有新步驟時完全不呼叫模型。"""
    n_old, n = prev["n"], len(steps)
    topics = [{"name": t["name"], "steps": [s for s in t["steps"] if 1 <= s <= n_old]}
              for t in prev["topics"]]
    new_idx = list(range(n_old + 1, n + 1))
    by = {t["name"]: t for t in topics}
    taken = set()
    if new_idx and use_model:
        existing = [{"name": t["name"],
                     "examples": [oneline(steps[s - 1].intent)[:60] for s in t["steps"][:3]]}
                    for t in topics]
        payload = {"existing_topics": existing, "new_steps": dump_intents(steps)[n_old:]}
        prompt = i18n.cluster_incremental_rules(lang) + "\n\n## 輸入\n" + \
            json.dumps(payload, ensure_ascii=False)
        out = _run_claude(prompt, model, timeout)
        for t in (out.get("topics") or []) if isinstance(out, dict) else []:
            if not isinstance(t, dict):
                continue
            idxs = [s for s in (t.get("steps") or [])
                    if isinstance(s, int) and n_old < s <= n and s not in taken]
            if not idxs:
                continue
            taken.update(idxs)
            name = _sanitize(str(t.get("name") or "")) or "untitled"
            if name in by:
                by[name]["steps"] += idxs
            else:
                by[name] = {"name": name, "steps": idxs}
                topics.append(by[name])
    if new_idx:
        leftover = [s for s in new_idx if s not in taken]
        if leftover:                       # 漏的新步驟併進既有的「其他」,不另開同名主題
            other = i18n.L(lang)["other"]
            hit = next((t for t in topics if t["name"] in (other, _sanitize(other))), None)
            if hit is None:
                hit = {"name": other, "steps": []}
                topics.append(hit)
            hit["steps"] += leftover
    # 舊主題名原樣保留(它們本來就是安全的);模型給的新名字上面已經清理過
    return normalize({"title": prev["title"], "topics": topics}, steps, lang,
                     sanitize_names=False), len(new_idx)

