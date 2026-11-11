"""社團活動公告整理器（Streamlit 入口）。

本機：  streamlit run app.py
雲端：  Main file path 填 `Midterm Mini-Project/app.py`
"""
import os
from pathlib import Path

import streamlit as st

from core import (
    APP_TITLE,
    FIELD_LABELS,
    MAX_CHARS,
    TIMEOUT_SECONDS,
    NoticeError,
    extract,
    get_api_key,
    get_model,
    validate_input,
)

try:  # 本機才需要 .env；雲端用 Secrets
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title=APP_TITLE, page_icon="📣")

SAMPLE_DIR = Path(__file__).parent / "sample_data"


def secret_lookup(name: str):
    try:
        return st.secrets.get(name)
    except Exception:  # 沒有 secrets 檔時 Streamlit 會丟例外
        return None


def load_sample(filename: str) -> str:
    path = SAMPLE_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------- 狀態 ----------
st.session_state.setdefault("record", None)   # {"source": 原文, "data": dict}
st.session_state.setdefault("error", None)    # str
st.session_state.setdefault("notice_text", "")

# ---------- 側邊欄 ----------
with st.sidebar:
    st.header("設定")
    api_enabled = st.toggle("啟用 OpenAI API（預設關閉）", value=False)
    st.caption(
        f"開啟後，每次有效送出最多 1 次請求，不自動重試。原文上限 {MAX_CHARS} 字。"
    )
    st.divider()
    st.subheader("載入虛構範例")
    c1, c2 = st.columns(2)
    if c1.button("完整公告", use_container_width=True):
        st.session_state.notice_text = load_sample("normal.txt")
    if c2.button("資訊不足", use_container_width=True):
        st.session_state.notice_text = load_sample("incomplete.txt")
    st.caption("範例皆為虛構資料。")

# ---------- 主畫面 ----------
st.title(f"📣 {APP_TITLE}")
st.write("把社團群組裡雜亂的活動公告貼進來，整理成「我要做什麼、何時截止、還缺什麼資訊」。")

with st.form("notice_form"):
    text = st.text_area(
        "公告原文",
        key="notice_text",
        height=240,
        placeholder="貼上 LINE／IG／Email 的活動公告……",
    )
    st.caption(f"目前 {len(text)} / {MAX_CHARS} 字")
    submitted = st.form_submit_button("整理公告", type="primary")

if submitted:
    # 每次新提交先清掉舊結果，避免舊成功結果與新錯誤並存
    st.session_state.record = None
    st.session_state.error = None

    err = validate_input(text)
    if err:
        st.session_state.error = err
    elif not api_enabled:
        st.session_state.error = "API 目前是關閉的：請先在左側開啟「啟用 OpenAI API」再送出。（本次 0 次請求）"
    else:
        api_key = get_api_key(secret_lookup)
        if not api_key:
            st.session_state.error = "找不到 OPENAI_API_KEY：請設定 .env（本機）或 Secrets（雲端）。（本次 0 次請求）"
        else:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0)
                model = get_model(secret_lookup)
                with st.spinner("整理中……"):
                    data = extract(client, model, text)
                st.session_state.record = {"source": text, "data": data, "model": model}
            except NoticeError as exc:
                st.session_state.error = str(exc)
            except Exception as exc:  # 例如 openai 套件沒裝
                st.session_state.error = f"發生未預期錯誤（{type(exc).__name__}）：{exc}"

# ---------- 結果／錯誤（獨立顯示） ----------
if st.session_state.error:
    st.error(st.session_state.error)

record = st.session_state.record
if record:
    data = record["data"]
    st.success(f"整理完成（模型：{record['model']}）。請對照原文自行核對，格式合格不代表內容正確。")

    st.subheader(FIELD_LABELS["event_name"])
    st.write(data["event_name"])

    st.subheader(FIELD_LABELS["when_where"])
    st.write(data["when_where"])

    for key in ("action_items", "deadlines"):
        st.subheader(FIELD_LABELS[key])
        if data[key]:
            for item in data[key]:
                st.markdown(f"- {item}")
        else:
            st.caption("原文沒有相關內容。")

    st.subheader(FIELD_LABELS["missing_info"])
    if data["missing_info"]:
        for item in data["missing_info"]:
            st.markdown(f"- ⚠️ {item}")
        st.caption("這些是參加前建議向幹部確認的事，模型不會替你補答案。")
    else:
        st.caption("公告資訊看起來齊全。")

    with st.expander("對照原文（本次送出的內容）"):
        st.text(record["source"])
