# session-to-obsidian

[![CI](https://github.com/timo9378/session-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/timo9378/session-to-obsidian/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/session-to-obsidian.svg)](https://pypi.org/project/session-to-obsidian/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Turn a **Claude Code** or **GitHub Copilot Chat** session into an Obsidian note that is organized **by topic**, easy to browse, good for writing from, and useful as a memory layer your AI can recall after a context compaction.

繁體中文說明見 **[README.zh-TW.md](README.zh-TW.md)**.

Not a verbatim log dump. It splits one session into **coherent topic threads** (not time slices). Under each topic: *what you asked + the assistant's full narrative + the tools/files/screenshots involved*, with a table of contents on top — plus a cross-session `INDEX.md`.

## Why

One AI coding session often does several unrelated things (fix a bug, tweak some UI, detour into something else). Later you want to find "how did I solve that thing" — and a timeline is useless, because what you remember is the **topic**, not the timestamp. This tool uses an LLM to cluster steps into topics so the note is organized the way you remember it.

The first audience is the author's own future self (a tool you keep using); open source is a bonus.

## Install

```bash
pipx install session-to-obsidian
```

Topic clustering calls your **local `claude` CLI** (Claude Code) in headless mode — no API key, uses your existing subscription. No Claude Code? It still works, clustering just degrades to time-slicing (see below).

## Usage

```bash
# A Claude Code session (jsonl lives in ~/.claude/projects/<proj>/<uuid>.jsonl)
s2o import ~/.claude/projects/myproj/abc123.jsonl --vault ~/Obsidian

# A Copilot Chat session (VS Code's chatSessions/<uuid>.jsonl append-log)
s2o import "~/…/workspaceStorage/<hash>/chatSessions/<uuid>.jsonl" --vault ~/Obsidian

# Output language (labels + generated titles). Default: en
s2o import <file> --vault ~/Obsidian --lang zh-TW

# No LLM — pure time-segmentation (offline / no Claude Code)
s2o import <file> --vault ~/Obsidian --cluster time

# Rebuild the index only
s2o index --vault ~/Obsidian
```

Source (Claude native / Copilot append-log) is auto-detected. Output goes to `<vault>/90-Meta/sessions/<date>-<source>-<title>/` with a `.md` (recap) and `.canvas` (topic-grouped node graph). Set `S2O_VAULT` to skip `--vault`; `S2O_LANG` to set a default language. Re-importing the same session replaces the previous note (deduped by an `originSessionId` stored in frontmatter).

## How it works

```
detect source → adapter restores steps → extract "ask + files + first-line gist"
   → cluster (LLM) → render .md/.canvas → update INDEX.md
```

Clustering only feeds the LLM **the ask list + each step's touched filenames + the assistant's first line** (never the full transcript), so token use is bounded. Compound asks go to their dominant topic; topics may be non-contiguous in time; each step keeps its original number.

## Limitations

- **Topic clustering needs the local `claude` CLI** (Claude Code). Without it, use `--cluster time`.
- Images are not extracted by default (`--images` to enable). By Obsidian convention images live under `_attachments/` (gitignore them; sync via Syncthing to avoid bloating git).
- Topic names / titles are LLM-generated; quality depends on the model. Re-run a single session to regenerate.

## Development

```bash
pip install pytest -e .
pytest
```

## License

MIT — see [LICENSE](LICENSE).
