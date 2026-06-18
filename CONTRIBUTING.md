# Contributing

Thanks for your interest! This is a small, dependency-free tool — contributions that keep it simple are very welcome.

## Setup

```bash
git clone https://github.com/timo9378/session-to-obsidian
cd session-to-obsidian
pip install pytest -e .   # or use a venv
pytest
```

## Project layout

```
s2o/
  parse.py        jsonl → steps (no LLM)
  adapters/       source detection + restore (copilot append-log replay, claude native)
  cluster.py      ask-list → {title, topics}; backends: claude_cli (host Claude), time
  render.py       steps + topics → .md (TOC + topic sections) + .canvas
  index.py        sessions/ → INDEX.md
  slugs.py        title → cross-platform filename slug
  i18n.py         output labels + clustering prompt (en / zh-TW)
  cli.py          orchestration (import / index)
```

Design rationale lives in [SPEC.md](SPEC.md) — read it before changing clustering or rendering.

## Guidelines

- **No runtime dependencies.** Standard library only. The LLM step shells out to the `claude` CLI.
- Add a test for any bug you fix or behavior you add (`tests/test_s2o.py`).
- The hard-won bits (Copilot append-log replay, heading-demote + fence-balancing, topic clustering contract) are covered by tests — keep them green.
- Adding a new source (e.g. another AI IDE)? Write an adapter in `s2o/adapters/` returning `(records, meta)` and wire it into `detect()`.
- Adding a language? Extend `LABELS` and `_RULES_NAME` in `s2o/i18n.py`.

## Reporting issues

Include the source type (Claude / Copilot), the command you ran, and what the output looked like vs what you expected.
