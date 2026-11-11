"""社團活動公告整理器：不依賴 Streamlit 的核心邏輯（可離線測試）。

流程：輸入檢查 → 呼叫 OpenAI（Structured Outputs，Pydantic）→ 回應檢查 → 回傳 dict。
"""
from __future__ import annotations

import os
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

# ---------- A：任務定位 ----------
APP_TITLE = "社團活動公告整理器"

INSTRUCTIONS = """你是大學社團幹部的助理。使用者會貼上一則社團活動公告（可能是 LINE／IG／Email 的雜亂文字）。
請只根據公告原文，整理成給「想參加的同學」看的重點。

規則：
1. 只能使用原文出現的資訊，不可推測、補造日期、時間、地點、費用、人名或連結。
2. 原文沒有提到的欄位：字串欄位填「原文未提及」；清單欄位若原文沒有內容就回傳空清單。
3. action_items 只列同學「需要做的事」（例如報名、繳費、攜帶物品），每項一句話，照原文意思寫。
4. deadlines 只列原文明確寫出的截止時間，格式「事項：時間」。
5. missing_info 列出同學參加前「一定想知道、但原文沒寫」的資訊（例如沒寫地點、費用、報名方式）。
   不要列與參加無關的缺漏。若原文已齊全，回傳空清單。
6. 使用繁體中文。"""

# ---------- B：資料契約（全部必填、禁止多餘欄位） ----------
class ClubNoticeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(description="活動名稱；原文沒有就填「原文未提及」")
    when_where: str = Field(description="日期、時間與地點合併成一句；缺的部分註明「未提及」")
    action_items: list[str] = Field(description="同學需要做的事，一項一句")
    deadlines: list[str] = Field(description="原文明確的截止時間，格式「事項：時間」")
    missing_info: list[str] = Field(description="參加前需要、但原文沒寫的資訊")


# ---------- C：畫面用中文標籤 ----------
FIELD_LABELS: dict[str, str] = {
    "event_name": "活動名稱",
    "when_where": "時間與地點",
    "action_items": "我需要做什麼",
    "deadlines": "截止時間",
    "missing_info": "公告沒寫、需要再問的事",
}

MAX_CHARS = 6000          # 課堂成本護欄，不是 token 上限
TIMEOUT_SECONDS = 60      # 網路等待設定，不是整段執行時間保證
DEFAULT_MODEL = "gpt-5.4-mini"


class NoticeError(Exception):
    """可顯示給使用者的錯誤；一律不當成功處理。"""


def validate_input(text: str) -> str | None:
    """回傳錯誤訊息；合格回傳 None。不合格時絕不能發出 API 請求。"""
    if not text or not text.strip():
        return "請先貼上公告原文（目前是空白）。"
    if len(text) > MAX_CHARS:
        return f"原文共 {len(text)} 字，超過上限 {MAX_CHARS} 字，請縮短後再送出。"
    return None


def get_api_key(secret_lookup: Callable[[str], str | None] | None = None) -> str | None:
    """先找平台 Secrets（由呼叫端提供查詢函式），再找環境變數／.env。"""
    key = None
    if secret_lookup is not None:
        try:
            key = secret_lookup("OPENAI_API_KEY")
        except Exception:
            key = None
    return (key or os.getenv("OPENAI_API_KEY") or "").strip() or None


def get_model(secret_lookup: Callable[[str], str | None] | None = None) -> str:
    val = None
    if secret_lookup is not None:
        try:
            val = secret_lookup("OPENAI_MODEL")
        except Exception:
            val = None
    return (val or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()


def check_result(data: dict[str, Any]) -> list[str]:
    """回應檢查：欄位齊全、型別正確、字串非空。回傳問題清單（空＝通過）。"""
    problems: list[str] = []
    expected = set(FIELD_LABELS)
    if set(data) != expected:
        problems.append(f"欄位不符：多 {sorted(set(data) - expected)}、缺 {sorted(expected - set(data))}")
        return problems
    for name in ("event_name", "when_where"):
        if not isinstance(data[name], str) or not data[name].strip():
            problems.append(f"{FIELD_LABELS[name]} 不可為空")
    for name in ("action_items", "deadlines", "missing_info"):
        v = data[name]
        if not isinstance(v, list) or not all(isinstance(i, str) and i.strip() for i in v):
            problems.append(f"{FIELD_LABELS[name]} 必須是非空字串的清單")
    return problems


def extract(client: Any, model: str, text: str) -> dict[str, Any]:
    """送出一次請求（最多 1 次，client 需 max_retries=0）。成功回傳 data(dict)。

    任何未完成、拒答、解析失敗、欄位檢查失敗都丟 NoticeError。
    """
    err = validate_input(text)
    if err:
        raise NoticeError(err)

    try:
        response = client.responses.parse(
            model=model,
            instructions=INSTRUCTIONS,
            input=text,
            text_format=ClubNoticeResult,
        )
    except NoticeError:
        raise
    except Exception as exc:  # 網路、驗證、額度、逾時等
        raise NoticeError(f"呼叫服務失敗（{type(exc).__name__}）：{exc}") from exc

    status = getattr(response, "status", "completed")
    if status != "completed":
        reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
        raise NoticeError(f"模型沒有完成回應（status={status}，原因={reason or '未知'}），結果不採用。")

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise NoticeError("模型拒答或沒有回傳可解析的結構化結果，請調整原文後重試。")

    data = parsed.model_dump()
    problems = check_result(data)
    if problems:
        raise NoticeError("回應未通過欄位檢查：" + "；".join(problems))
    return data
