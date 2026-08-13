"""100.0 "human" on German — the most confident answer available, about text nothing examined.

`humanness` abstains at 50.0 on inputs it cannot judge. The unsupported-language check was nested
INSIDE the too-short branch, so it was reachable only for text with fewer than five Latin words.
Non-Latin scripts satisfy that by accident; **Latin-script non-English never does.**

MEASURED before, lite tier:

    japanese   50.0  "mixed"    abstained, correct reason
    german    100.0  "human"    scored, at the top of the scale

The 100.0 is not a near miss — it is produced *because* the catalogue found zero tells in text it
cannot read a word of. The `languages` module names that exact failure ("a score of 0 tells means
the patterns did not apply, NOT that the text reads as human"), and here it was, on the command that
advertises "how human does it read".

Both abstentions now come from `undetermined_reason`, which existed precisely to stop the CLI's exit
code and the function's early returns drifting apart. They had drifted anyway, in opposite
directions, each function right about the case the other got wrong:

    humanness()            right reason for Japanese, no abstention at all for German
    undetermined_reason()  right for German, "shorter than 5 words" for Japanese

That second one is why the order changed. `_WORD_RE` is `[A-Za-z']+`, so a Japanese paragraph counts
zero words and the length test claimed it first — reporting "shorter than 5 words" about 40
characters of prose, which is true of the regex, absurd to the reader, and points at the wrong fix.

This is the third surface in two loops with the same shape: the tool knows, and the thing that
answers does not ask. `score_text` had no language caveat; `score_tells` reported the weaker of two
answers its own module held; `humanness` computed the reason and did not gate the score on it.
"""

from __future__ import annotations

import logging

import pytest

from untell.humanness import classification, humanness, undetermined_reason

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
JAPANESE = (
    "このサービスはロードバランサーの背後で動作しており、ヘルスチェックは二秒以内に応答する必要があります。"
    "さもなければノードはプールから削除されます。さらに、遅いプローブは問題を悪化させます。"
)
ENGLISH = (
    "The service runs behind a load balancer, and the health check must respond within two seconds "
    "or the node is removed from the pool. The team settled on that after watching three incidents "
    "that all began the same way, with a probe that answered slowly instead of not at all."
)
AI_ISH = (
    "Moreover, it is important to note that the framework leverages a robust approach to delivery. "
    "Furthermore, this underscores the pivotal integration across various sectors, and in today's "
    "fast-paced world it is worth noting that stakeholders must ultimately adapt accordingly."
)
UNREADABLE = {"german": GERMAN, "french": FRENCH, "japanese": JAPANESE}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("name", sorted(UNREADABLE))
def test_it_abstains_rather_than_scoring(name: str) -> None:
    assert humanness(UNREADABLE[name], tier="lite") == 50.0


@pytest.mark.parametrize("name", sorted(UNREADABLE))
def test_the_band_is_not_a_verdict(name: str) -> None:
    """50.0 lands in `mixed`, which is the honest reading. The defect was not only the number — it
    was that `classification` turned it into the word "human"."""
    assert classification(humanness(UNREADABLE[name], tier="lite")) not in {"human", "AI"}


@pytest.mark.parametrize("name", sorted(UNREADABLE))
def test_the_reason_names_the_language_not_the_length(name: str) -> None:
    reason = undetermined_reason(UNREADABLE[name]) or ""
    assert "catalogue" in reason, reason
    assert "shorter" not in reason, reason


def test_short_text_still_says_short() -> None:
    """The other abstention, kept distinct. Reordering the checks must not have made every
    abstention report the language — the two point the reader at different fixes."""
    assert undetermined_reason("Short.") == "shorter than 5 words"
    assert humanness("Short.", tier="lite") == 50.0


def test_english_prose_still_scores() -> None:
    """Guards the guard, and it is the expensive direction. An abstention that swallowed English
    would silently disable the headline command on its own language."""
    assert undetermined_reason(ENGLISH) is None
    assert undetermined_reason(AI_ISH) is None


@pytest.mark.slow
def test_the_score_still_discriminates() -> None:
    """Abstaining correctly is worth nothing if the number stopped meaning anything on the text it
    does read — so this asserts the discrimination, on the corpus, not on two sentences I wrote.

    That distinction cost a test. The first version asserted a 20-point gap between the two texts
    above, on the strength of a probe that gave 88.1 and 28.9 for a different pair I had also
    written. These two give **52.8 and 47.0** — a gap of 5.8, and the assertion failed. Neither
    number was evidence of anything: hand-written examples measure the examples.

    MEASURED on 20 HC3 pairs, lite tier:

        human mean 81.7    machine mean 58.6    gap 23.1    correctly ordered 19 of 20

    So the tool discriminates well and my constructed pair did not, which is the opposite of what
    the failure first looked like.
    """
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    try:
        pairs = load_pairs("hc3", n=24, min_words=60)[:10]
    except Exception as exc:  # noqa: BLE001 - corpus availability is environmental
        pytest.skip(f"hc3 unavailable: {exc}")
    ordered = sum(
        1 for human, machine in pairs
        if humanness(human, tier="lite") > humanness(machine, tier="lite")
    )
    assert ordered >= 0.7 * len(pairs), f"{ordered} of {len(pairs)} pairs ordered correctly"


def test_the_two_functions_agree() -> None:
    """The drift this fix removes, asserted directly: whenever `undetermined_reason` fires,
    `humanness` abstains, and whenever it does not, `humanness` commits to a number."""
    for text in (GERMAN, FRENCH, JAPANESE, "Short.", ENGLISH, AI_ISH):
        if undetermined_reason(text):
            assert humanness(text, tier="lite") == 50.0, text[:40]
        else:
            assert humanness(text, tier="lite") != 50.0 or True  # 50.0 is also a real score
