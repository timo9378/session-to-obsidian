# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
