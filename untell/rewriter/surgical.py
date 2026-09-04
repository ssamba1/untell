"""Free, no-key surgical rewriter — word-importance substitution as a ``Rewriter`` backend.

The free-ceiling report's **Move #2**: promote PWWS / TextFooler-style word-importance substitution
into the closed loop. Unlike the hosted (Anthropic/OpenAI) and local-policy rewriters, this needs
**no API key, no GPU, and no model download** — it is pure stdlib plus the lite detector. That makes
the whole closed loop runnable at $0, which is what lets the eval harness (``eval/ceiling.py``)
*measure* untell's inference-only evasion ceiling against the local ensemble — the data point the
literature is missing (see ``docs/free-ceiling-report.md``).

It rewrites by ranking each word by how much it drives the detector score, then swapping the
highest-importance words for score-lowering synonyms (``untell.attacks.surgical_substitute``). Minimal
surface change, so the meaning-similarity gate in the loop is easy to hold; deterministic, so the
measurement is reproducible. Weak on its own — it is the *floor* of the free regime, not the
ceiling, and the report says so.

**It cannot move the detector at all, at either tier, and that is now designed around.** MEASURED
on real HC3 AI text: on the pure-stdlib path the score moves 0.5693 -> 0.5663 with 16 of 30 texts
getting zero substitutions, and at full tier it moves 0.9993 -> 0.9991. The cause is not "a small
synonym map" — the map covers every AI-vocabulary word in a 13-tell test paragraph — but that a
detector's score simply does not change when a word is swapped for a synonym, so the "is this
candidate better on score" test can never pass. See ``surgical_substitute``'s docstring for the
per-candidate numbers.

So this rewriter asks ``surgical_substitute`` for the objective it can actually deliver:
``prefer_tells=True`` ranks words by whether swapping one removes a catalogued tell and accepts a
swap that stays inside the loop's 0.02 noise band overall. Measured through the loop on 15 real
texts, stdlib, this took tells/100w from 0.307 to **0.179** with the detector score slightly better
(0.5647 -> 0.5633) — a real gain on the one axis word substitution controls.

``composite`` (structural + surgical) still owes most of its strength to the *structural* half, and
a benchmark row for "surgical" alone is measuring the detector's insensitivity as much as the
rewriter.

**On text carrying no catalogued tell this rewriter cannot act at all, and returns its input
byte-identical.** That follows from the objective above: ``prefer_tells=True`` ranks words by
tell removal, and a text with no tell has an empty ranking, so nothing is ever proposed. MEASURED
on 40 machine-written abstracts, lite: 36 have an empty ranking and 37 come back unchanged, against
18 of 20 changed for ``structural`` and 14 of 20 for ``composite`` on the same corpus. The tells
catalogue reads academic-vs-chatbot REGISTER, so this is the ordinary case for formal prose rather
than an edge — the corpus above is machine-written throughout.

That was silent until it was measured. An identical candidate reproduces every locked span, scores
similarity 1.0 and ties on detector score, so it passes every gate and even satisfies the adoption
guard's ``<=`` on score — what stops it is the separate ``cand_best != best_masked`` check, which is
about the TEXT and not about the comparison the user is then told about. So the loop reported
``stopped: stalled`` and a note saying every draft scored worse than the text, of a rewriter that
had written none. The loop now counts
identical draws separately and names this cause; see ``run.py::_nothing_adopted_warning``.
"""

from __future__ import annotations

_SCOREABLE = ("lite", "full", "heavy", "commercial")


class SurgicalRewriter:
    """Deterministic CPU rewriter backed by ``surgical_substitute``. Always ``available()``."""

    name = "surgical"
    # Deterministic: identical input -> identical output. The loop uses this to stop early once an
    # iteration stops changing the text (re-running would be a guaranteed no-op).
    deterministic = True

    def __init__(self, max_subs: int = 12):
        self.max_subs = max_subs

    def available(self) -> bool:
        # Pure stdlib + the lite detector — runnable anywhere, no key, no heavy deps.
        return True

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.attacks import surgical_substitute
        from untell.layout import restore_layout_lines

        # Target the tier the loop is actually scoring against so the swaps lower the RIGHT signal.
        # Composite labels (e.g. a browser scorer's "browser:zerogpt") aren't directly scoreable;
        # fall back to the full local ensemble, or lite if full isn't implied.
        tier = score_result.get("tier", "lite")
        if tier not in _SCOREABLE:
            tier = "full" if "full" in str(tier) else "lite"
        # prefer_tells=True: rank by tell-removal rather than by detector deletion-importance, and
        # accept a swap that removes a tell while leaving the score inside the loop's own 0.02 noise
        # band. Measured both ways on real HC3 AI text — tells/100w 0.571 -> 0.233 against
        # 0.571 -> 0.458 on the stdlib path, and 0.566 -> 0.196 against 0.566 -> 0.428 at full tier,
        # with the detector score unchanged either way and 2.3x less wall-clock AT FULL TIER — on
        # the stdlib lite path a clean install runs, the two modes cost the same (0.92x, 0.95x
        # measured; the 8.2x cheaper ranking is handed back downstream — see `word_importance`).
        # NOT the default of
        # `surgical_substitute` itself, because eval/compare_humanizers.py uses that function as the
        # `synonym_swap` row standing in for the QuillBot / TextFooler class, and that baseline has
        # to keep modelling their technique rather than inheriting ours.
        #
        # Layout protection was a property of `structural` alone — it and `mt_pivot` were the only
        # rewriters calling into `layout` — so the same document survived `--rewriter structural`
        # and was corrupted by the default `composite`, which reaches this class. MEASURED at every
        # seed, on a four-space indented code block:
        #
        #         def f():                          def f():
        #             return utilize(x)      ->          return use(x)
        #
        # Both halves are damage: the identifier was renamed, and the first line lost its indent, so
        # what remains does not render as code at all. `structural` had protected the same construct
        # for as long as `layout` has existed.
        #
        # Whole document, then restore the layout lines — NOT `apply_per_block`. Splitting was the
        # first fix and it cost quality: MEASURED over 50 HC3 and RAID texts, per-block left the
        # detector score unchanged and made tell removal worse, 9.576 -> 10.616 tells/100w on RAID.
        # A short block scores badly, and this rewriter ranks its swaps by that score. Substitution
        # happens in place and never reflows — line count was identical on all 50 — so restoring by
        # line index protects the layout at no cost to context.
        rewritten = surgical_substitute(
            text, tier=tier, threshold=threshold, max_subs=self.max_subs, prefer_tells=True
        )["text"]
        return restore_layout_lines(text, rewritten)
