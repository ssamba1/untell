"""Kill the prompts.py survivors found by .claude/mutate.py.

Every test calls the REAL build_rewrite_prompt (and through it the real
_worst_detectors) and asserts on the actual prompt text — nothing is
reimplemented or mocked.

Survivors killed here (module:line / mutation):
  prompts.py:75    _worst_detectors default k=3 -> 4
  prompts.py:77    numeric filter `and` -> `or` (error-named detectors leak in)
  prompts.py:77    `"__error" not in n` -> `in` (normal detectors vanish)
  prompts.py:78    sorted reverse=True -> False (worst = lowest, not highest)
  prompts.py:96    `style and style in STYLES` -> `or` (unknown style -> KeyError)
  prompts.py:99    flagged_sentences `or []` -> `and []` (list never listed)
  prompts.py:101   flagged_sentences[:8] -> [:9] (cap not enforced)
"""

from untell.rewriter.prompts import build_rewrite_prompt


def test_worst_detectors_names_exactly_top_three():
    """k=3 caps how many detectors are named. With four numeric detectors the
    fourth (lowest) must stay out of the prompt."""
    sr = {
        "detectors": {
            "alpha": 0.90, "beta": 0.80, "gamma": 0.70, "delta": 0.60,
        }
    }
    p = build_rewrite_prompt("Some text.", sr, 0.30)
    assert "alpha (P(AI)=0.90)" in p
    assert "beta (P(AI)=0.80)" in p
    assert "gamma (P(AI)=0.70)" in p
    assert "delta" not in p


def test_worst_detectors_are_named_highest_first():
    """reverse=True means the worst (highest P(AI)) detector is named first."""
    sr = {"detectors": {"alpha": 0.90, "beta": 0.80, "gamma": 0.70}}
    p = build_rewrite_prompt("Some text.", sr, 0.30)
    assert p.index("alpha (P(AI)=0.90)") < p.index("beta (P(AI)=0.80)")
    assert p.index("beta (P(AI)=0.80)") < p.index("gamma (P(AI)=0.70)")


def test_error_suffixed_detector_is_never_named():
    """A detector key carrying __error is a failure row, not a score — it must
    not appear among the named detectors even when its value is numeric."""
    sr = {"detectors": {"good": 0.80, "bad__error": 0.99}}
    p = build_rewrite_prompt("Some text.", sr, 0.30)
    assert "bad__error" not in p
    assert "good (P(AI)=0.80)" in p


def test_normal_detector_is_named():
    """The `not in "__error"` filter must keep ordinary detectors: a plain
    numeric detector has to reach the prompt as feedback."""
    sr = {"detectors": {"mage": 0.80}}
    p = build_rewrite_prompt("Some text.", sr, 0.30)
    assert "mage (P(AI)=0.80)" in p


def test_unknown_style_is_skipped_not_crashed():
    """A style name outside STYLES must be ignored silently, not turned into a
    KeyError by indexing the dict."""
    p = build_rewrite_prompt("Some text.", {"style": "bogus", "detectors": {}}, 0.30)
    assert "Voice:" not in p


def test_flagged_sentences_are_listed():
    """flagged_sentences must survive the `or []` default into the prompt."""
    sr = {"flagged_sentences": ["Sentence one."], "detectors": {}}
    p = build_rewrite_prompt("Some text.", sr, 0.30)
    assert "Sentence one." in p


def test_only_first_eight_flagged_sentences_are_listed():
    """The [:8] cap keeps the prompt bounded; the ninth sentence must be cut."""
    nine = [f"Sentence number {i}." for i in range(9)]
    p = build_rewrite_prompt("Some text.", {"flagged_sentences": nine, "detectors": {}}, 0.30)
    assert "Sentence number 0." in p
    assert "Sentence number 7." in p
    assert "Sentence number 8." not in p
