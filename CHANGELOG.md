# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-03

### Changed
- Re-importing a session now keeps its existing folder name instead of renaming it
  from the newly clustered title, which broke wikilinks and external references.
  Pass `--rename` to opt back into renaming, or `--slug` to set a name explicitly.

### Fixed
- Each step's intent is capped at 300 characters in the clustering input. A step
  containing a huge pasted prompt (e.g. another session's step list) could dominate
  the input, and the model would copy its labels as topic names.

## [0.1.1] - 2026-07-26

### Fixed
- Copilot: detect version-3 whole-file JSON sessions and restore code blocks from
  `textEditGroup` edits (previously rendered as empty blocks).
- Clustering runs `claude -p` in a temporary cwd and cleans up afterwards, so headless
  clustering sessions no longer appear in the Claude Code session picker.

### Added
- Helper converters for Cline / Roo Code and Gemini CLI sessions
  (`cline_to_claude.py`, `gemini_cli_to_claude.py`).

## [0.1.0] - 2026-06-19

Initial release.

### Added
- `s2o import <file> --vault <dir>` — import a Claude Code or GitHub Copilot
  Chat session into Obsidian as a topic-organized recap note + topic-grouped
  Canvas, and update a cross-session `INDEX.md`.
- Auto source detection: Claude native jsonl, Copilot Chat append-log (replayed).
- Semantic topic clustering via the local `claude` CLI (headless, no API key);
  `--cluster time` fallback with no LLM.
- Bilingual output (`--lang en|zh-TW`, default `en`; `S2O_LANG` env).
- Frontmatter `originSessionId` for dedupe — re-importing a session replaces it.
- `s2o index` to rebuild the index.

[Unreleased]: https://github.com/timo9378/session-to-obsidian/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/timo9378/session-to-obsidian/releases/tag/v0.1.0
