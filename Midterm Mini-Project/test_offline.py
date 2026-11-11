"""離線檢查（0 次真實請求）。執行：python test_offline.py

只證明輸入檢查與回應檢查的邏輯；假回應不是模型成果。
"""
from types import SimpleNamespace

from core import (
    MAX_CHARS,
    ClubNoticeResult,
    NoticeError,
    check_result,
    extract,
    validate_input,
)


class FakeClient:
    """模擬 client.responses.parse；calls 用來證明沒有多打請求。"""

    def __init__(self, response=None, raises=None):
        self.calls = 0
        self._response, self._raises = response, raises
        self.responses = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._response


def good():
    return ClubNoticeResult(
        event_name="測試活動", when_where="時間未提及；地點未提及",
        action_items=["報名"], deadlines=[], missing_info=["地點"],
    )


def expect_error(fn):
    try:
        fn()
    except NoticeError:
        return True
    return False


def main():
    results = []

    def t(name, ok):
        results.append(ok)
        print(("PASS" if ok else "FAIL"), name)

    # 輸入檢查：不得發出請求
    t("空白被擋", validate_input("   ") is not None)
    t("6000 字可通過", validate_input("字" * MAX_CHARS) is None)
    t("6001 字被擋", validate_input("字" * (MAX_CHARS + 1)) is not None)
    c = FakeClient(SimpleNamespace(status="completed", output_parsed=good()))
    t("空白不呼叫 API", expect_error(lambda: extract(c, "m", "")) and c.calls == 0)
    t("過長不呼叫 API", expect_error(lambda: extract(c, "m", "字" * 6001)) and c.calls == 0)

    # 成功：恰好 1 次請求
    c = FakeClient(SimpleNamespace(status="completed", output_parsed=good()))
    data = extract(c, "m", "有內容")
    t("成功回傳 dict 且 1 次請求", isinstance(data, dict) and c.calls == 1)

    # 失敗分流：都必須丟 NoticeError，不能冒充成功
    c = FakeClient(SimpleNamespace(status="incomplete",
                                   incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                                   output_parsed=good()))
    t("未完成被擋", expect_error(lambda: extract(c, "m", "x")))
    c = FakeClient(SimpleNamespace(status="completed", output_parsed=None))
    t("拒答／無解析結果被擋", expect_error(lambda: extract(c, "m", "x")))
    c = FakeClient(raises=TimeoutError("模擬逾時"))
    t("服務例外被包成 NoticeError", expect_error(lambda: extract(c, "m", "x")))
    bad = ClubNoticeResult(event_name=" ", when_where="a", action_items=[], deadlines=[], missing_info=[])
    c = FakeClient(SimpleNamespace(status="completed", output_parsed=bad))
    t("空字串欄位未過檢查", expect_error(lambda: extract(c, "m", "x")))

    # check_result
    d = good().model_dump()
    t("欄位齊全通過", check_result(d) == [])
    d2 = dict(d); d2["extra"] = 1
    t("多餘欄位被抓", check_result(d2) != [])
    d3 = dict(d); d3["action_items"] = ["", "ok"]
    t("清單內空字串被抓", check_result(d3) != [])

    # Schema：禁止多餘欄位
    schema = ClubNoticeResult.model_json_schema()
    t("additionalProperties=False", schema.get("additionalProperties") is False)
    t("全部欄位必填", set(schema["required"]) == set(schema["properties"]))

    print(f"\n{sum(results)}/{len(results)} 通過")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
