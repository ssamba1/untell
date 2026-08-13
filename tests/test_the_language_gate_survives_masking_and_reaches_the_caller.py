"""The language gate did not fire through the loop, and its caveat never reached the caller.

Two defects in the fix shipped one commit earlier, found by asking the question that commit should
have asked: does the caveat reach the reader?

MASKING DEFEATED THE GATE. `structural_rewrite` declines Latin-script text that is not English. The
loop hands the rewriter SENTINEL-MASKED text, and locking both consumes real words and adds an "HZ"
token per sentinel to the word count. MEASURED on the same paragraphs, raw against masked:

    german   20 words, other-share 0.300  ->  18 words, 0.278   (below the 20-word floor)
    spanish  26 words, other-share 0.231  ->  20 words, 0.100   (below the 0.12 floor)
    french   26 words, other-share 0.269  ->  unchanged, nothing locked

So the gate worked when called directly and was bypassed in production. Its end-to-end test passed
for an unrelated reason — composite declining on score — which is the failure mode that test was
supposed to rule out.

Two fixes, deliberately both: `looks_non_english` now ignores sentinels, which repairs the
rewriter-level gate for any masked caller; and the loop gates on the text as the user supplied it,
before anything is masked, which is the authoritative one.

THE CAVEAT ONLY LOGGED. The rewriter's version calls `logging.warning`, which on the REST and MCP
surfaces reaches the server operator and not the caller — a step worse than the defect this repo has
now fixed on six surfaces, where the caveat at least reached the result. It is now on
`result["warning"]`, which every surface already forwards.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock
from untell.scripts.run import untell_text
from untell.scripts.tells import looks_non_english

NON_ENGLISH = {
    "german": "Die Studie untersuchte den Kohlenstoffgehalt des Bodens an elf Standorten. "
              "Die Ergebnisse variierten je nach Tiefe der entnommenen Bodenprobe erheblich.",
    "spanish": "El estudio examinó el carbono del suelo en once sitios durante cuatro años. "
               "Los resultados variaron según la profundidad de la muestra tomada en cada sitio.",
    "french": "L'étude a examiné le carbone du sol sur onze sites pendant quatre années entières. "
              "Les résultats variaient selon la profondeur de l'échantillon prélevé sur le site.",
}
ENGLISH = (
    "The study examined soil carbon at eleven sites over four years, sampling to ninety "
    "centimetres, and reported mean stocks of 82.4 t/ha in the deepest layer of the profile."
)


@pytest.fixture
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _other_share(text: str, *, strip_sentinels: bool = True) -> tuple[float, int]:
    """The two quantities the gate is built from, computed the way the gate computes them."""
    from untell.scripts import tells as t

    if strip_sentinels:
        text = t._SENTINEL_RE.sub(" ", text)
    words = [w.lower().strip("'") for w in t._WORD_RE.findall(text)]
    words = [w for w in words if w]
    if not words:
        return 0.0, 0
    other = sum(1 for w in words if w in t._OTHER_FUNCTION_WORDS) / len(words)
    return other, len(words)


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_sentinels_do_not_dilute_the_language_ratio(name: str) -> None:
    """Half the defect, and the half that is fixable at this level.

    Each `⟦HZxxxx⟧` contributes "HZ" to the word count, so before the strip a locked span both
    removed a real word and added a token that looked like one. MEASURED, other-language share on
    the masked form, before the strip against after:

        german   0.278 -> 0.357
        spanish  0.100 -> 0.133   (0.100 was below the 0.12 floor; 0.133 is above it)
    """
    masked, mapping = lock(NON_ENGLISH[name])
    if not mapping:
        pytest.skip(f"{name} locks nothing, so there are no sentinels to dilute anything")

    with_strip, _n = _other_share(masked)
    without_strip, _m = _other_share(masked, strip_sentinels=False)
    assert with_strip > without_strip, (
        f"{name}: stripping sentinels did not raise the other-language share "
        f"({without_strip:.3f} -> {with_strip:.3f}), so they are still counted as words"
    )


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_masked_text_can_still_fall_under_the_word_floor(name: str) -> None:
    """The other half, which is NOT fixable at this level and is why the loop gates separately.

    Locking removes real words, and the gate needs 20 to judge from. MEASURED after the strip:

        german   20 words raw -> 14 masked      spanish  26 -> 15      french  26 -> 26 (locks nothing)

    So the rewriter-level gate is best-effort for direct callers, and the authoritative gate runs
    in the loop on the text as the user supplied it, before anything is masked. Asserting that
    masked text is always recognised would be asserting something false.
    """
    masked, mapping = lock(NON_ENGLISH[name])
    _share, words = _other_share(masked)
    if not mapping:
        assert looks_non_english(masked), f"{name} locks nothing, so masking must change nothing"
        return
    assert words < len(NON_ENGLISH[name].split()), "locking should reduce the word count"


def test_at_least_one_fixture_actually_gets_masked() -> None:
    """Guards both tests above. French locks nothing, so if every fixture behaved like French
    neither would be exercising masking at all."""
    locked = {name: len(lock(text)[1]) for name, text in NON_ENGLISH.items()}
    assert sum(locked.values()) > 0, f"no fixture locks any span: {locked}"
    assert any(v == 0 for v in locked.values()), (
        f"no fixture locks nothing, so the unmasked branch above is never taken: {locked}"
    )


def test_english_is_still_not_flagged_after_masking() -> None:
    """The error that matters most, checked on the masked form too."""
    masked, _mapping = lock(ENGLISH)
    assert not looks_non_english(ENGLISH)
    assert not looks_non_english(masked)


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_the_loop_carries_the_caveat_on_the_result(name: str, stdlib_lite) -> None:
    result = untell_text(NON_ENGLISH[name], tier="lite", rewriter="composite", threshold=0.001)
    warning = str(result.get("warning") or "")
    assert "Latin-script language other than English" in warning, (
        f"{name}: the result carries no language caveat, so a JSON, REST or MCP caller is told "
        f"nothing. warning={warning[:120]!r}"
    )
    assert result["final"] == NON_ENGLISH[name], "the text must come back unchanged"


def test_english_gets_no_language_caveat(stdlib_lite) -> None:
    """Guards the guard. A caveat attached to everything says nothing."""
    result = untell_text(ENGLISH, tier="lite", rewriter="composite", threshold=0.001)
    assert "Latin-script language other than English" not in str(result.get("warning") or "")


def test_the_rest_surface_forwards_it(stdlib_lite, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.delenv("UNTELL_API_KEY", raising=False)
    from untell.api_server import app

    with TestClient(app) as client:
        body = client.post(
            "/humanize",
            json={"text": NON_ENGLISH["german"], "tier": "lite", "threshold": 0.001},
        ).json()

    assert "Latin-script language other than English" in str(body.get("warning") or ""), (
        f"REST dropped the caveat: {str(body.get('warning'))[:140]!r}"
    )
