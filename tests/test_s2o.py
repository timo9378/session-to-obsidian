"""s2o 單元測試 — 釘住得來不易的邏輯(分群契約 / fence / copilot replay / slug)。
跑法:pip install pytest && pytest
"""
import json

from s2o.parse import Step, clean, parse_records, dump_intents
from s2o.render import demote_headings
from s2o.slugs import title_slug, session_slug
from s2o.cluster import normalize, _extract_json
from s2o.adapters import copilot, detect
from s2o.index import build_index


# ── parse:NOISE 清理 ──
def test_clean_strips_harness_wrappers():
    assert clean("<task-notification>done</task-notification>hi") == "hi"
    assert clean("<local-command-caveat>x</local-command-caveat>真內容") == "真內容"


def test_clean_keeps_real_content():
    # <br> / traceback 等是使用者貼的真內容,不可清
    assert "<br>" in clean("第一行<br>第二行")


def test_parse_records_skips_noise_only_turns():
    recs = [
        {"timestamp": "", "message": {"role": "user", "content": "<task-notification>x</task-notification>"}},
        {"timestamp": "", "message": {"role": "user", "content": "真的提問"}},
        {"timestamp": "", "message": {"role": "assistant", "content": [{"type": "text", "text": "答"}]}},
    ]
    steps = parse_records(recs)
    assert len(steps) == 1
    assert steps[0].intent == "真的提問"
    assert steps[0].prose == "答"


def test_dump_intents_shape():
    s = Step(intent="q", asst=["助手回答的首句。後面更多。"])
    s.files.update(["/a/b/foo.py", "/c/bar.js"])
    d = dump_intents([s])[0]
    assert d["i"] == 1 and d["intent"] == "q"
    assert d["files"] == ["bar.js", "foo.py"]
    assert d["gist"].startswith("助手回答的首句")


# ── render:demote + fence 配對 ──
def test_demote_out_of_fence_heading():
    assert demote_headings("# 標題") == "**標題**"


def test_demote_preserves_in_fence_comment():
    src = "```bash\n# 這是註解\n```"
    assert demote_headings(src) == src


def test_demote_balances_unclosed_fence():
    # copilot 抓的 code block 常缺收尾 ``` → 應補上,且後面的 # 不被當標題誤判
    out = demote_headings("```\ncode\n# x")
    assert out.endswith("```")
    assert out.count("```") == 2


# ── slugs:跨平台 sanitize ──
def test_title_slug_strips_forbidden():
    assert "/" not in title_slug("a/b:c?d")
    assert "#" not in title_slug("a#b")


def test_title_slug_caps_and_no_partial_latin():
    s = title_slug("flow2code 棄案 tool-call benchmark 很長很長很長很長", cap=12)
    assert len(s) <= 12


def test_session_slug_format():
    assert session_slug("2026-04-04T01:00:00Z", "copilot", "標題").startswith("2026-04-04-copilot-")
    assert session_slug("2026-06", "session", "x") == "2026-06-session-x"


# ── cluster:覆蓋率正規化 ──
def test_normalize_coverage_dedupe_sort_sanitize():
    steps = [Step(intent=f"q{i}") for i in range(5)]   # 5 步
    clustering = {"title": "T/x#y", "topics": [
        {"name": "b線", "steps": [3, 2]},
        {"name": "a線", "steps": [1, 2]},               # 2 重複 → 只算第一個遇到的
    ]}
    out = normalize(clustering, steps)
    covered = sorted(s for t in out["topics"] for s in t["steps"])
    assert covered == [1, 2, 3, 4, 5]                   # 不重不漏(4,5 進其他)
    assert out["topics"][0]["steps"][0] == 1            # 按最早步號排
    assert "/" not in out["title"] and "#" not in out["title"]


def test_extract_json_strips_fence():
    assert _extract_json('```json\n{"a":1}\n```') == {"a": 1}
    assert _extract_json('胡言 {"a":1} 亂語') == {"a": 1}


# ── copilot adapter:append-log replay ──
def test_copilot_replay(tmp_path):
    f = tmp_path / "chat.jsonl"
    f.write_text("\n".join([
        json.dumps({"kind": 0, "v": {"requests": [], "customTitle": "標題T", "creationDate": 1700000000000}}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [
            {"message": {"text": "你好"}, "timestamp": 1700000000000,
             "response": [{"value": "哈囉"}, {"kind": "toolInvocationSerialized",
                          "pastTenseMessage": {"value": "Read foo.py"}}]}
        ]},
    )]), encoding="utf-8")
    records, meta = copilot.load(str(f))
    assert meta["title"] == "標題T"
    assert detect(str(f)) == "copilot"
    steps = parse_records(records)
    assert len(steps) == 1
    assert steps[0].intent == "你好" and steps[0].prose == "哈囉"
    assert "Read" in steps[0].tools


# ── index:從帶 frontmatter 的 .md 解析標題 ──
def test_build_index_parses_frontmatter(tmp_path):
    sd = tmp_path / "sessions" / "2026-06-19-claude-測試場"
    sd.mkdir(parents=True)
    (sd / "2026-06-19-claude-測試場.md").write_text(
        "---\noriginSessionId: abc\nsource: claude\n---\n\n# 我的標題\n\n"
        "> 3 步 · 2 主題 · 0 圖 · 節點圖見 [[x.canvas]]\n\n## 目錄\n"
        "- [[#主題 1 · 甲|甲]] · 2 步 `#1 #2`\n- [[#主題 2 · 乙|乙]] · 1 步 `#3`\n",
        encoding="utf-8")
    out = build_index(str(tmp_path / "sessions"))
    assert out["sessions"] == 1 and out["topics"] == 2
    idx = (tmp_path / "sessions" / "INDEX.md").read_text(encoding="utf-8")
    assert "我的標題" in idx and "甲 · 乙" in idx
