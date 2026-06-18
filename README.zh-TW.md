# session-to-obsidian

[![CI](https://github.com/timo9378/session-to-obsidian/actions/workflows/ci.yml/badge.svg)](https://github.com/timo9378/session-to-obsidian/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/session-to-obsidian.svg)](https://pypi.org/project/session-to-obsidian/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

把一場 **Claude Code** 或 **GitHub Copilot Chat** 的對話 session,變成 Obsidian 裡**依語意主題分區、可快速翻找、可給 Claude compact 後回想、可拿來寫文章**的回顧筆記。

> English: **[README.md](README.md)**

不是逐字 log dump。它把一場 session 拆成**連貫的主題串**(不是時間段),每條主題底下是「我問 + 助手完整敘述 + 用到的工具/檔案/截圖」,頂部附目錄,並維護一份跨 session 的 `INDEX.md` 索引。

## 為什麼

AI coding 一場 session 常常一次解好幾件事(修個 bug、順手改 UI、中間插一段別的)。事後想翻「那個問題當時怎麼解的」,時間軸沒用——你記得的是**主題**,不是幾點做的。這工具用 LLM 把步驟分到主題,讓筆記照你記憶的方式組織。第一受眾是作者本人;開源是順手。

## 安裝

```bash
pipx install session-to-obsidian
```

語意分群預設呼叫你**本機的 `claude` CLI**(Claude Code)——零 API 金鑰、吃你現有訂閱。沒裝 Claude Code 也能用,分群退化成時間分段。

## 用法

```bash
# Claude Code session(jsonl 在 ~/.claude/projects/<專案>/<uuid>.jsonl)
s2o import ~/.claude/projects/myproj/abc123.jsonl --vault ~/Obsidian

# Copilot Chat session(VS Code 的 chatSessions/<uuid>.jsonl append-log)
s2o import "~/…/workspaceStorage/<hash>/chatSessions/<uuid>.jsonl" --vault ~/Obsidian

# 輸出語言(標籤 + 產生的標題),預設 en
s2o import <file> --vault ~/Obsidian --lang zh-TW

# 不靠 LLM,純時間分段(離線 / 無 Claude Code)
s2o import <file> --vault ~/Obsidian --cluster time

# 只重建索引
s2o index --vault ~/Obsidian
```

來源自動偵測。輸出到 `<vault>/90-Meta/sessions/<日期>-<來源>-<標題>/`(`.md` + `.canvas`)。`S2O_VAULT` 可省 `--vault`,`S2O_LANG` 設預設語言。重匯同一場會自動取代舊版(靠 frontmatter 的 `originSessionId` 去重)。

## 它怎麼運作

```
偵測來源 → adapter 還原步驟 → 抽「提問+檔名+助手首句」→ 分群(LLM)→ 渲染 .md/.canvas → 更新 INDEX.md
```

分群只餵**提問清單 + 該步檔名 + 助手首句**(不餵全文),token 有界。複合提問歸主導主題、主題可跨時間非連續、每步保留原始步號。

## 限制

- **語意分群需要本機 `claude` CLI**(Claude Code)。沒有就 `--cluster time`。
- 圖片預設不抽(`--images` 開啟);圖走 `_attachments/`(自行 gitignore + Syncthing,避免 git 變肥)。
- 主題命名/標題由 LLM 產,品質視模型而定;不滿意可重跑單場。

## 開發

```bash
pip install pytest -e .
pytest
```

## License

MIT — 見 [LICENSE](LICENSE)。
