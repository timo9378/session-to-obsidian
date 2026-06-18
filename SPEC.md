# session-to-obsidian — 專案規格(SPEC)

把 Claude Code session(jsonl)轉成 Obsidian 裡**可快速翻找、可給 Claude compact 後回想、可拿來寫文章**的結構化紀錄。

## 1. 目的 / 受眾
- **單場回顧 + 寫文章素材**:翻找「某問題當時怎麼解的」,加速回憶;`.md` 是主力。
- **Claude 跨 compact 的記憶層**:context 被壓縮後,Claude 能回去查前面做了什麼/怎麼解 → 這份結構化紀錄是持久記憶。
- **受眾**:AI coding agent 使用者 ∩ Obsidian 使用者(交集窄)。**第一受眾是作者本人**(永久使用者容器);開源是順手,不以採用率為成敗。

## 2. 形態 / 發佈
- **一個自有專案**,發佈成 **Claude Code skill/plugin(SKILL.md + 腳本)**。
- **語意那步用 host 的 Claude(零外部 LLM 依賴)**;想跑 standalone/cron 再選配外部/地端 LLM(hybrid)。
- 「skill」只是呼叫格式,骨子是專案。skill 不穩的疑慮 → 把 agent 的工作限到**只有「主題分群」**,其餘全是死板腳本。

## 3. 分工(誰做、要不要 LLM)
| 步驟 | 誰 | LLM |
|---|---|---|
| 解析 jsonl → 步驟/提問/工具/檔案/截圖/時間 | 腳本 | ❌ |
| **把步驟分到主題串 + 命名** | host agent(隔離 sub-agent) | ✅ 唯一一處 |
| 組 `.md`(目錄 + 主題分區 + 提問當小標 + 完整作法 + 截圖) | 腳本 | ❌ |
| 建圖 (b) 單場主題級 / (c) 跨 session | 腳本(有標籤就純機械) | ❌ |
| 儲存(git 文字 / Syncthing 圖) | 腳本 | ❌ |

## 4. Token 控制(主題分群)
- 原則 = **不餵全 transcript**,但給「便宜且高鑑別度」的結構訊號。實測(2026-06-19,dcfce9f1):
  **只餵提問清單會壞** —— context-dependent 的提問(「這是連結」「放到 X 後要 run…」)光看字面無法歸線,
  agent 會把它併進前一條主題、還生出空主題。**修法 = 提問 + 該步碰的檔名(basename,上限 6)+ 助手首句 gist(上限 160 字)**,
  量仍有界(每步 ≈ 一兩百字),救回 context-dependent 步驟。`--dump-intents` 已內建這三項。
- 跑在**隔離 sub-agent(Task)**:不吃主 session context、不害它提早 compact。各場 sub-agent 讀自己的 dump、寫自己的 topics.json。
- 分群契約:每步恰好一主題(不重不漏,render 端驗證);**主題可非連續**(隔時收尾步歸回原線);複合提問不拆、歸主導線;
  主題按最早步號排;步號保留原始編號(主題視圖仍可還原時序)。tiny 場(≤5步同一事)→ 1 主題,別硬切。

## 5. 輸出
- **`<slug>.md`**:每步「我問 + 助手完整敘述 + 工具/檔案 + 截圖」,依主題分區 + 頂部目錄。**核心價值**。導覽靠 Obsidian 原生 Outline/搜尋。
- **(b) 單場主題級節點圖**:主題串當節點(非每步、非檔案 hub —— 那是毛球教訓)。對「一場多主題」的 session 有用。
- **(c) 跨 session 圖**:每場一節點。關聯訊號(由強到弱):**共用檔案(權重,設門檻)+ 同專案分簇 + 共用主題標籤(白拿)**;**embedding 語意相似 = opt-in**(新依賴);模糊字串搜尋最弱、不用。避免毛球 → 只用強邊。

## 6. 儲存架構(已定案)
- **git 只放文字**(.md/.canvas)→ 永不肥。
- **圖走 Syncthing 的 vault `_attachments/`**(gitignore)→ server↔手機,免 git bloat。
- 全圖原檔私有封存;文章要用的圖才逐張走 blog pipeline 公開(session 截圖含敏感,別全公開)。
- 手機:termux SSH(免 PAT)或 Obsidian-Git(HTTPS+PAT);**手機 pull-only**(多寫手會打架);Android 共用儲存 `git config core.filemode false`。

## 7. 未解 / 待做(下次開工)
- ✅ **主題分群 step**(2026-06-19 完成):`--dump-intents`(提問+files+gist)→ 隔離 sub-agent 分群+命名+總標題 → `--topics` render。20 場已重匯。
- ✅ **.md 導覽**:頂部 TOC(wikilink heading 連結)+ 主題分區 + 原始步號;助手敘述的 ATX 標題 demote 成粗體、fence 強制配對 → Obsidian Outline 只剩 主題/步驟。
- ✅ **手刻 mesh 砍掉**(候選3降範圍);單場 `.canvas` 改主題分組彩色框。
- **(b)(c) 圖的呈現形式**:仍未做。傾向原生 graph(linked notes,scoped local graph)而非手刻布局。跨 session(c)未動。
- ✅ **檔名帶標題**(2026-06-19):session 資料夾/檔名 = `<date>-<source>-<標題slug>`(跨平台 sanitize + 截長),側欄一眼看出主題,不再是 uuid。
- ✅ **recall 入口**(2026-06-19):`build_index.py` 掃 `sessions/*/*.md` 產 `INDEX.md`(全 session + 主題地圖,按月分組)。
  雙受眾:人一頁掃完、Claude compact 後讀這張當 recall 地圖(找到 → 開 .md → Outline 跳主題)。慣例已寫進 vault `CLAUDE.md`。
  進階(未做):`/recall <query>` skill 直接回傳命中主題(屬候選5打包範圍)。
- **打包成 skill/plugin**(SKILL.md 把 extract→cluster→render 串起來)+ 選配 standalone CLI。骨架已成形(三段拆分),待寫 SKILL.md。

## 現況(2026-06-19)
`session_to_obsidian.py`:解析 → `--dump-intents`(提問+files+gist 給分群 agent)→ `--topics`(吃 {title,topics} render 主題分區 .md + TOC + 主題分組 canvas);沒給 `--topics` 退回時間分段。`NOIMG=1` 純文字。
**20 場全部以主題分群重匯完成**(9 copilot + 11 Claude),coverage/headings/fence parity 全驗證通過。dump/topics 暫存 `/tmp/s2o/`。mesh 已移除。
待:SKILL.md 打包、recall 入口、(b)(c) 圖、選配重抽圖(目前 text-only)。
