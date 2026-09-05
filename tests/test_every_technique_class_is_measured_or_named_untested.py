"""A technique that could not run must never be reported as one that did not work.

The comparison table this repo publishes covers three techniques. The census it also publishes
sorts 435 repositories into twelve categories. `eval/technique_matrix.py` measures every class that
can run here, on one corpus, against four axes — and the axis nobody else reports is the one that
changes the conclusion.

MEASURED, 25 machine-written abstracts, lite:

    technique              category                    chg   P(AI)              tells/100w    Δstyle
    none (control)         —                             0   0.3084 -> 0.3084   0.32 -> 0.32  +0.0000
    homoglyph_substitute   unicode-trickery             25   0.3084 -> 0.3084   0.32 -> 0.32  -0.1220
    synonym_swap           adversarial-perturbation      0   0.3084 -> 0.3084   0.32 -> 0.32  +0.0000
    structural             rule-based-rewriter          22   0.3084 -> 0.2823   0.32 -> 0.23  -0.0111
    our closed loop        detector-in-loop             15   0.3084 -> 0.2652   0.32 -> 0.09  -0.0125

Two results the usual single-axis table cannot show. **Homoglyph substitution changes every
document, adds 641 invisible or counterfeit characters, and moves the detector score by nothing at
all** — the unicode-trickery category is sabotage with no measured benefit here. And **every
technique that works has NEGATIVE Δstyle**: they all move the document TOWARD the machine centroid
while lowering its score, which is the in-loop/held-out gap made concrete.

The defect this file guards is the one the first run of that table had: `back_translate` returns its
input unchanged when its models are absent, so the row read "0 changed, no effect" — an untested
technique reported as an ineffective one, in a table that ranks this repo against other people's
work, erring in the flattering direction.
"""

from __future__ import annotations

import inspect

from eval import technique_matrix as M


def test_the_matrix_covers_more_than_the_shipped_comparison_does() -> None:
    """The reason this module exists. If it does not reach more of the census's categories than
    `compare_humanizers` already did, it is a second copy of the same table."""
    from eval import compare_humanizers

    categories = {category for category, _ in M._techniques().values()}
    shipped = inspect.getsource(compare_humanizers._techniques)
    assert len(categories) >= 5, f"too few technique classes to be a survey: {categories}"
    for missing in ("unicode-trickery", "paraphrase-model", "detector-in-loop"):
        assert missing in categories, f"{missing} is a census category and is not covered"
    assert "homoglyph" not in shipped, (
        "the shipped comparison already covers unicode trickery; this module's premise is stale"
    )


def test_an_absent_technique_is_named_untested_not_scored_as_ineffective() -> None:
    """`back_translate` returns its input when the models are absent. Inferring "no effect" from
    that publishes a fiction, and in a competitive table it flatters us."""
    report = M.measure(["The quick brown fox jumps over the lazy dog. " * 20], n=1)
    for row in report["rows"]:
        if "unavailable" in row:
            assert "NOT TESTED" in row.get("note", ""), row
            # An untested row must carry no numbers at all: a cell that is absent and a cell that
            # is zero are the same pixel and opposite facts.
            for numeric in ("score_after", "tells_per_100w_after", "delta_displacement"):
                assert numeric not in row, f"untested row carries a measurement: {row}"


def test_availability_is_probed_not_inferred_from_the_output() -> None:
    """A no-change rule cannot tell "absent" from "ran and genuinely changed nothing", and this repo
    has a measured instance of the second — `surgical` returns its input on text with no catalogued
    tell (round 109). Collapsing both would file that finding as a missing package."""
    source = inspect.getsource(M._availability)
    assert "available()" in source, "availability must be asked, not deduced"
    absent = M._availability()
    assert "back_translation" in absent, absent


def test_integrity_separates_a_rewrite_from_a_sabotage() -> None:
    """Homoglyph substitution wins the detector axis by construction in the literature and destroys
    the text. A table without this column ranks it above a real rewrite."""
    from untell.attacks import homoglyph_substitute

    clean = "We present a method for aligning multilingual sentence embeddings."
    attacked = homoglyph_substitute(clean, rate=0.5)
    marks = M.integrity(clean, attacked)
    assert marks["foreign_letters"] > 0, "the attack planted no counterfeit letters"
    honest = M.integrity(clean, clean.replace("method", "technique"))
    assert honest["foreign_letters"] == 0 and honest["hidden_chars"] == 0


def test_the_stylometric_frame_is_fixed_once_for_every_technique() -> None:
    """Recomputing the centroid or the z-scale per technique would let each one move the ruler it is
    measured with — the same error as scoring a rewrite against its own output."""
    source = inspect.getsource(M.measure)
    assert source.count("vocabulary(") == 1, "the feature space must be built once"
    assert source.count("centroid(") == 1, "the centroid must be built once"


def test_the_blocker_names_which_wall_it_hit() -> None:
    """"torch is absent" and "the weights host is blocked" are different facts with different
    remedies, and this repo's documents called both the first one.

    MEASURED: `pip download torch` fetches a 554.6 MB wheel without trouble — PyPI is reachable —
    while `https://huggingface.co/` returns 403, CONNECT tunnel failed, and no weight cache exists
    anywhere on the machine. So installing the package would not make one model-backed row
    measurable, and a reason that says "torch absent" sends a reader to spend 554 MB finding that
    out.
    """
    reason = M._model_blocker()
    assert reason, "a technique must never be unavailable for no stated reason"
    # Whichever wall is live, the message has to identify it rather than name a package by default.
    if M._weights_reachable() is False:
        assert "unreachable" in reason and "would not make this measurable" in reason, reason
    else:
        assert "not installed" in reason or "unavailable" in reason, reason


def test_the_reachability_probe_never_raises_and_never_retries() -> None:
    """A 403 from the proxy is a policy decision, not a transient error. Retrying it is both futile
    and the thing this environment's instructions forbid, so the probe makes one attempt and reports
    what it found — including "could not tell", which is a third answer and not a synonym for no."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(M._weights_reachable).lstrip())
    # Walk the AST rather than grep the source: the first version matched the word "for" inside the
    # docstring's prose and failed for a sentence, which is the kind of test that gets deleted
    # rather than fixed.
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
    assert not loops, "the probe must make one attempt, not retry a policy decision"
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert any(getattr(h.type, "id", None) == "Exception" for h in handlers), (
        "the probe must never propagate a transport error"
    )
    assert M._weights_reachable(timeout=5.0) in (True, False, None)
