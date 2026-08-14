"""A browser checker that raises must not read as a pass.

verify.py:177: when a browser checker's check() raises, the row reports
{"ai": None, "passes": False, "error": ...}. The mutation False -> True makes a
crashed checker read as a pass — the same fail-open class as the NaN row (139)
and the raising commercial detector (152).
"""
import untell.browser_check as browser_check
from untell.scripts.verify import verify


class _Raising:
    def available(self) -> bool:
        return True

    def check(self, text: str) -> float:
        raise RuntimeError("boom")


def test_raising_browser_checker_is_not_a_pass(monkeypatch):
    monkeypatch.setattr(
        browser_check, "get_browser_checker", lambda site: _Raising()
    )
    r = verify("x", browser=["fake"])
    row = r["results"]["fake(web)"]
    assert row["ai"] is None
    assert row["passes"] is False, f"raising checker read as pass: {row}"
    assert row["error"] == "boom"
