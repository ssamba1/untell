"""The modern-LLM recall page is generated from its JSON and strips essay scaffolding correctly."""

from untell.bench.modern_recall import _rate, render_markdown, strip_markdown


def test_strip_markdown_removes_scaffolding_but_keeps_words():
    text = "# Title\n\n**Bold** start of an essay.\n\n- point one\n* point two\n\n\n\nEnd."
    out = strip_markdown(text)
    assert "#" not in out and "**" not in out
    assert "Bold start of an essay." in out
    assert "point one" in out and "point two" in out
    assert "\n\n\n" not in out


def test_page_reports_every_detector_with_counts():
    out = {"n": 4, "provenance": {"model": "m", "temperature": 0.8, "prompts": 2},
           "detectors": {
               "untell (calibrated-v2)": {"recall": {"as generated": _rate(1, 4),
                                                     "markdown stripped": _rate(0, 4)}},
               "org/det": {"threshold": 0.91, "recall_default": {"as generated": _rate(4, 4),
                                                                  "markdown stripped": _rate(3, 4)},
                           "recall_recommended": {"as generated": _rate(2, 4),
                                                  "markdown stripped": _rate(2, 4)},
                           "auroc_vs_persuade_human": {"as generated": 0.9, "markdown stripped": 0.85}}}}
    md = render_markdown(out)
    assert "25% (1/4" in md and "0% (0/4" in md
    assert "org/det | 0.5 (default) | 100% (4/4" in md
    assert "0.9100 (fitted)" in md and "0.850" in md
    assert "do not edit by hand" in md
