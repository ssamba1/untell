"""The rewriter refuses non-English text and says so. The two reporting surfaces did neither.

MEASURED, one paragraph of the same content in five languages, lite tier, through the shipped loop:

    language   score   flagged   rewritten   language caveat from score_text
    english    0.7495  True      yes         n/a
    german     0.4788  True      NO          NONE
    spanish    0.2680  False     NO          NONE
    french     0.2364  False     NO          NONE
    japanese   0.0000  False     NO          present (non-Latin script)

The German row is the defect: a confident-looking AI verdict on text the rest of the pipeline had
already decided it cannot process, with caveats attached about its LENGTH and its TIER and nothing
about its language. `untell_text` gets this right — it returns the text unchanged and says "any
score here is not a verdict about this text" — but `score_text` is a separate public surface, used
by the CLI's `score`, the MCP tool and the REST endpoint, and it never consulted the check.

The second surface was `score_tells`, where this module contained two answers to the same question:

    `looks_non_english`     German is not English   (written for the rewriter, after English
                                                     openers were welded into German sentences)
    `_language_supported`   German is supported     (script-based: it catches Korean, not German)

and the output field reported the second. That field exists precisely so a zero tell count is not
read as a clean bill of health — its own module says so, about Korean. German produced the identical
misleading zero, and Latin-script non-English is by far the commoner case of the two.

The widening is the risky half, so the control that guards it is measured too: **a run of English
headings stays supported.** The module records that as the outcome "far worse" than letting German
through, because the English-function-word share does not separate the classes — headings score
0.000 and Italian 0.125.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

ENGLISH = (
    "The service runs behind a load balancer, and the health check must respond within two seconds "
    "or the node is removed from the pool. Moreover, it is important to note that a slow probe "
    "compounds during a rollout, and the team settled on two seconds after three incidents."
)
GERMAN = (
    "Der Dienst läuft hinter einem Lastverteiler, und die Zustandsprüfung muss innerhalb von zwei "
    "Sekunden antworten, sonst wird der Knoten aus dem Pool entfernt. Darüber hinaus ist es wichtig "
    "zu beachten, dass eine langsame Prüfung sich während eines Rollouts verstärkt."
)
FRENCH = (
    "Le service fonctionne derrière un répartiteur de charge, et le contrôle de santé doit répondre "
    "en moins de deux secondes, sinon le nœud est retiré du pool. De plus, il est important de "
    "noter qu'une sonde lente s'aggrave pendant un déploiement progressif."
)
SPANISH = (
    "El servicio funciona detrás de un balanceador de carga, y la comprobación de estado debe "
    "responder en menos de dos segundos o el nodo se retira del grupo. Además, es importante "
    "señalar que una sonda lenta se agrava durante un despliegue progresivo."
)
JAPANESE = (
    "このサービスはロードバランサーの背後で動作しており、ヘルスチェックは二秒以内に応答する必要があります。"
    "さもなければノードはプールから削除されます。さらに、遅いプローブはロールアウト中に問題を悪化させます。"
)
NON_ENGLISH = {"german": GERMAN, "french": FRENCH, "spanish": SPANISH}
# The false positives that matter more than the gap. A run of English headings has almost no
# function words; Italian has some. Any bar drawn on function-word share alone either lets German
# through or disables the tool on English headings, and the module records the second as far worse.
ENGLISH_SHAPED = {
    "headings": "Overview\nPrerequisites\nDeployment\nRollback\nMonitoring\nTroubleshooting",
    "prose": ENGLISH,
    "terse list": "- Build the image\n- Push the tag\n- Watch the rollout\n- Revert on failure",
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_the_score_says_it_is_not_a_verdict(name: str) -> None:
    warning = score_text(NON_ENGLISH[name], tier="lite", threshold=0.3).get("warning") or ""
    assert "not a verdict about this text" in warning, warning[:160]


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_the_language_caveat_comes_first(name: str) -> None:
    """Ahead of the threshold and tier notes, because it invalidates the number those qualify
    rather than qualifying it. A reader who stops after one sentence has to meet this one."""
    warning = score_text(NON_ENGLISH[name], tier="lite", threshold=0.3).get("warning") or ""
    assert warning.startswith("this text reads as a Latin-script language"), warning[:90]


@pytest.mark.parametrize("name", sorted(NON_ENGLISH))
def test_the_tell_count_is_marked_unsupported(name: str) -> None:
    """0.00 tells per 100 words is true of German and means nothing. The field is what stops a
    caller reading it as a clean bill of health."""
    result = score_tells(NON_ENGLISH[name])
    assert result["language_supported"] is False
    assert result["tells_per_100w"] == 0.0


def test_non_latin_script_is_still_caught() -> None:
    """The case the field already handled, kept — the widening must not have replaced one test with
    another."""
    assert score_tells(JAPANESE)["language_supported"] is False


@pytest.mark.parametrize("name", sorted(ENGLISH_SHAPED))
def test_english_is_not_swept_up(name: str) -> None:
    """Guards the guard, on the axis the module names as the expensive one. Marking English as
    unsupported would silently disable the entire tool on its own language, and the shapes at risk
    are the ones with the fewest function words."""
    assert score_tells(ENGLISH_SHAPED[name])["language_supported"] is True


def test_english_prose_gets_no_language_caveat() -> None:
    warning = score_text(ENGLISH, tier="lite", threshold=0.3).get("warning") or ""
    assert "Latin-script language" not in warning, warning[:120]


def test_the_tell_catalogue_still_counts_english() -> None:
    """A supported flag is worth nothing if the counting behind it stopped."""
    assert score_tells(ENGLISH)["tells_per_100w"] > 0
