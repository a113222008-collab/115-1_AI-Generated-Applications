# 📣 社團活動公告整理器

期中個人小專題（第 8 週）。把社團群組裡雜亂的活動公告，整理成「我要做什麼、何時截止、還缺什麼資訊」。

- **App 網址（Streamlit Community Cloud）**：`<<部署後填入>>`
- **雲端驗收日期／結果**：`<<未測，部署並實測後填入>>`
- **部署設定**：Repo `a113222008-collab/115-1_AI-Generated-Applications`、分支 `main`、Main file path `Midterm Mini-Project/app.py`、Python `<<實際選的版本>>`

## 1. 使用者與問題

**使用者**：想參加社團活動的大學生。
**問題**：公告常夾在 LINE／IG 長訊息裡，日期、費用、報名連結、截止時間散落各處；更常見的是「某個關鍵資訊根本沒寫」，同學得到處問。
**這個工具做的事**：貼上公告 → 整理成可行動的清單，並**明確列出公告沒寫的資訊**，而不是讓模型猜。

## 2. 為什麼用 Pydantic（而非 JSON Schema）

- 欄位定義與 Python 型別是同一份（`ClubNoticeResult`），改欄位時只改一處，降低「Schema、檢查、顯示」三處不同步的風險。
- 使用 `client.responses.parse(text_format=ClubNoticeResult)`，SDK 會轉成 strict 的 JSON Schema 並解析成物件，再用 `model_dump()` 轉成 dict。
- `extra="forbid"` 禁止多餘欄位；所有欄位皆必填（沒有預設值）。

## 3. 輸入與輸出欄位

**輸入**：一段公告原文（上限 6000 字，空白不送）。

| 欄位 | 型別 | 為什麼需要 |
|---|---|---|
| `event_name` 活動名稱 | str | 一眼確認是哪個活動 |
| `when_where` 時間與地點 | str | 決定能不能去；缺的部分註明「未提及」 |
| `action_items` 我需要做什麼 | list[str] | 報名、繳費、攜帶物品等下一步 |
| `deadlines` 截止時間 | list[str] | 錯過就不能參加，需獨立凸顯 |
| `missing_info` 公告沒寫、需要再問的事 | list[str] | 本工具的核心：不補造，只標出缺口 |

規則（寫在 `core.py` 的 `INSTRUCTIONS`）：只依原文、缺漏填「原文未提及」或空清單、不補造日期／費用／人名。

## 4. 安裝與啟動（本機）

```bash
cd "Midterm Mini-Project"
python3.14 -m venv .venv          # 專案自己的虛擬環境，不與系統 Python 混用
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

設定金鑰（擇一，皆不會被提交）：

- 複製 `.env.example` 為 `.env` 並填入 `OPENAI_API_KEY`；或
- 複製 `.streamlit/secrets.example.toml` 為 `.streamlit/secrets.toml` 並填入。

```bash
streamlit run app.py
```

離線檢查（0 次真實請求）：`python test_offline.py`

## 5. 操作範例

1. 左側先**不要**開 API，按「完整公告」載入虛構範例並送出 → 出現「API 目前是關閉的」，0 次請求。
2. 開啟「啟用 OpenAI API」，再送出 → 最多 1 次請求，顯示五個欄位。
3. 展開「對照原文」，逐欄核對。
4. 按「資訊不足」載入 `sample_data/incomplete.txt` 再送出 → 期望 `missing_info` 列出時間、地點、報名方式等，且不補造。

## 6. 安全與成本

- 金鑰只放 `.env` 或 Secrets；`.gitignore` 排除 `.env`、`.streamlit/secrets.toml`、`.venv/`、`__pycache__/`。
- API 預設關閉；空白／過長／缺金鑰都在請求**前**停止。
- 每次有效提交最多 1 次請求，`max_retries=0`，timeout 60 秒。6000 字是成本護欄，不是 token 上限。
- 新提交會先清掉舊結果，失敗時只顯示錯誤，不會留著舊的成功結果。
- 回應未完成、拒答、解析失敗、欄位檢查失敗都視為失敗，不呈現部分結果。

## 7. 測試狀態（如實記錄；未測就填「未測」）

| 項目 | 狀態 | 說明 |
|---|---|---|
| 空白／6001 字不請求 | 離線腳本通過 | `test_offline.py`，只證明輸入檢查 |
| 失敗分流（未完成／拒答／例外／欄位不符） | 離線腳本通過 | 使用**假回應**，不是模型成果 |
| 正常公告真實呼叫 | `<<未測>>` | 填：日期、模型、請求數、input、output、逐欄核對 |
| 資訊不足真實呼叫 | `<<未測>>` | 同上 |
| 雲端部署與真實呼叫 | `<<未測>>` | 填：網址、日期、入口、請求數 |
| 缺金鑰行為 | `<<未測>>` | 移除金鑰後重啟，應在請求前停止 |

詳細紀錄見 `第08週_課堂簡化版_專題設計與驗收紀錄.md`。

## 8. 限制

- 格式合格不代表事實正確，需自行對照原文。
- 圖片公告（海報）不支援；本週只處理貼上的文字。
- 模型可能把「明天」「週五」這類相對時間照抄，不會換算成日期。

## 9. AI 協助紀錄

- AI 協助：產生程式與文件初稿（`<<請改成你實際的說明>>`）。
- 我自己修改／驗證：`<<填：改了哪些欄位、prompt、親自跑了哪些測試>>`
- 測試資料皆為虛構，已於檔案內標示。
