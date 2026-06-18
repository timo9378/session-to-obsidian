---
name: session-to-obsidian
description: 把一場 Claude Code 或 GitHub Copilot 對話 session 匯入 Obsidian,變成依語意主題分區、可翻找、可 recall 的回顧筆記。當使用者說「把這場對話存進 obsidian / 匯入 session / 做 session 回顧」時使用。
---

# session-to-obsidian

把一場 AI coding session(jsonl)→ Obsidian 主題回顧筆記 + 跨 session 索引。

## 前置
需要已安裝 CLI:`pipx install session-to-obsidian`(提供 `s2o` 指令)。
語意分群會呼叫本機 `claude` CLI(headless),零金鑰。

## 匯入一場 session

1. 找到 session 來源 jsonl:
   - **Claude Code**:`~/.claude/projects/<專案>/<uuid>.jsonl`(挑使用者指定那場;最近的用 `ls -t`)。
   - **Copilot Chat**:VS Code `workspaceStorage/<hash>/chatSessions/<uuid>.jsonl`(append-log)。
2. 確認 vault 路徑(問使用者,或用環境變數 `S2O_VAULT`)。
3. 執行:
   ```bash
   s2o import <jsonl 路徑> --vault <vault 根>
   ```
   來源自動偵測;輸出到 `<vault>/90-Meta/sessions/<日期>-<來源>-<標題>/`(`.md` + `.canvas`),並更新 `INDEX.md`。重匯同一場會自動取代舊版(靠 frontmatter 的 originSessionId 去重)。

## 選項
- `--cluster time`:不用 LLM,純時間分段(離線/無 Claude Code)。
- `--images`:抽出截圖(預設純文字)。
- `--model <id>`:指定分群用模型。
- `s2o index --vault <vault>`:只重建 INDEX.md。

## recall(compact 後查回過去做過什麼)
讀 `<vault>/90-Meta/sessions/INDEX.md`(全 session + 主題地圖)→ 找到相關 session → 開該 `.md` → 用 Obsidian Outline 跳主題。
