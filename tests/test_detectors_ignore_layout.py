"""Hard wrapping and quote style are layout, not writing: detector input folds both away.

MEASURED with the stability test on Liang et al. essays: hard-wrapping at 72 columns (variant N6)
moved MAGE by up to 1.000, hc3_roberta by 0.92 and roberta_openai by 0.85 on identical words, and
curly -> straight quotes moved hc3_roberta by 0.52.
"""

from __future__ import annotations

from untell.detectors.base import normalise_for_scoring
from untell.evidence.perturb import null_variants

ESSAY = ('I prefer to cook at home. First of all, it is cheaper and safer than the restaurant, '
         'because I can buy the things needed for cooking and make sure they are "clean". Second, '
         "making a good dinner helps me obtain a sense of achievement, and that's important.\n\n"
         "On every Spring festival I make dinner for my whole family.")


def test_hard_wrapped_and_unwrapped_text_score_as_the_same_input():
    variants = {v.id: v.text for v in null_variants(ESSAY)}
    base = normalise_for_scoring(ESSAY)
    for vid in ("N1", "N2", "N6", "N7", "N10", "N12"):
        assert normalise_for_scoring(variants[vid]) == base, vid


def test_paragraphs_and_lists_survive():
    t = "Intro line one\ncontinues here.\n\n- first item\n- second item\n1. numbered\n# Heading"
    out = normalise_for_scoring(t)
    assert out.startswith("Intro line one continues here.\n\n- first item\n- second item")
    assert "\n1. numbered\n# Heading" in out


def test_quotes_fold_to_straight():
    assert normalise_for_scoring("“it’s”") == "\"it's\""
