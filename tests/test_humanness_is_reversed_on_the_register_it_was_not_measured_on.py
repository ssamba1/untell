"""The number a user actually reads, on the arms this project can now construct.

`humanness` is the 0-100 score `untell` puts in front of people, and its own docstring records
AUROC **0.978** on HC3 pairs at full length. HC3 is chatbot question-and-answer text: the register a
language model is stereotyped for, and the one the tell catalogue was built from.

MEASURED at matched length, 60-100 words, lite path:

    human academic     n=603   mean humanness 75.4
    machine academic   n= 25   mean humanness 80.8
    machine assistant  n= 12   mean humanness 71.7

    P(machine academic reads MORE human than human academic)  = 0.6733   should be below 0.5
    P(human academic reads MORE human than machine assistant) = 0.6009   should be above 0.5

**A machine-written abstract is judged more human than a real one.** Same tool, three verdicts, and
the variable is register — which round eighty-two established by holding authorship constant.

These tests use the packaged arms and the real function, so they exercise the claim rather than
restate it. The human arm needs the Anthology cache and skips without it; the machine-against-machine
ordering does not, and is the part that runs everywhere.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from eval.data.generated_abstracts import ABSTRACTS
from eval.data.generated_registers import ASSISTANT, PROMOTIONAL
from untell.humanness import humanness

CACHE = Path(__file__).resolve().parent.parent / ".anthology-cache"
needs_corpus = pytest.mark.skipif(
    not CACHE.exists(), reason="needs the Anthology cache; run eval.pre_llm_fpr --download")


def _score(text: str) -> float | None:
    value = humanness(" ".join(text.split()), tier="lite")
    return value.get("score") if isinstance(value, dict) else value


def _band(texts, low: int, high: int) -> list[float]:
    out = []
    for text in texts:
        flat = " ".join(text.split())
        if low <= len(flat.split()) < high:
            score = _score(flat)
            if score is not None:
                out.append(score)
    return out


def _p_higher(a: list[float], b: list[float]) -> float:
    return sum((x > y) + 0.5 * (x == y) for x in a for y in b) / (len(a) * len(b))


def test_the_score_orders_the_machine_registers_correctly():
    """Held-constant authorship, so this is purely a register ordering — and it is the right one.
    Academic prose reads most human, promotional least, which is what anyone would say."""
    academic = statistics.mean(_band(ABSTRACTS, 0, 10 ** 9))
    assistant = statistics.mean(_band(ASSISTANT, 0, 10 ** 9))
    promotional = statistics.mean(_band(PROMOTIONAL, 0, 10 ** 9))
    assert academic > assistant > promotional, (academic, assistant, promotional)


@needs_corpus
def test_a_machine_written_abstract_reads_more_human_than_a_real_one():
    """The finding, in the units a user sees. This is the assertion that should fail if the score
    is ever fixed — and a failure here is good news, so read the message before editing it."""
    import random

    from eval.pre_llm_fpr import pre_llm_abstracts

    texts = [t for t in pre_llm_abstracts(CACHE, 40, 2021) if 60 <= len(t.split()) < 100]
    random.Random(0).shuffle(texts)
    human = [s for s in (_score(t) for t in texts[:250]) if s is not None]
    machine = _band(ABSTRACTS, 60, 100)

    assert statistics.mean(machine) > statistics.mean(human), (
        f"machine {statistics.mean(machine):.1f} against human {statistics.mean(human):.1f}")
    assert _p_higher(machine, human) > 0.55, (
        "the machine arm no longer reads as more human than the human arm — if that is a real fix, "
        "update rounds 81-83 of the ledger and this test together")


def test_the_docstring_records_the_register_dependence_next_to_the_hc3_figure():
    """0.978 on HC3 and a reversal on academic prose are the same tool. Recording one without the
    other is how a number gets read as a property of the score rather than of the corpus — which is
    what rounds sixty-five and seventy-seven both found in other forms."""
    source = (Path(__file__).resolve().parent.parent / "untell" / "humanness.py").read_text(
        encoding="utf-8")
    assert "0.978" in source
    assert "0.6733" in source and "register" in source.lower()
    assert source.index("0.978") < source.index("0.6733"), (
        "the caveat must sit with the figure it qualifies, not elsewhere in the file")
