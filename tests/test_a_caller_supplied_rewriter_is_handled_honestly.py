"""`untell_text(rewriter=...)` takes any object. Two things must hold for one it does not know.

1. A COMPLETED RUN IS NEVER LOST TO A MISSING LABEL. `Rewriter` is a `typing.Protocol` declaring
   `name: str`, but Protocol is structural and nothing enforces it at runtime. Reading `rw.name`
   directly raised `AttributeError` while BUILDING THE RESULT — after every rewrite had been paid
   for. The work was done and thrown away for want of a string (issue #57).

2. THE MANIFEST DOES NOT VOUCH FOR WHAT IT CANNOT IDENTIFY. `_manifest_payload` classifies
   determinism by rewriter NAME, and an unrecognised name previously fell through to the
   "reproducible" branch. A caller-supplied rewriter that calls a network service or draws from an
   unseeded generator would have been stamped reproducible by the one artifact whose entire purpose
   is an honest determinism claim.

The second is the more serious of the two and was found while fixing the first.
"""

from __future__ import annotations

from untell.scripts.run import _manifest_payload, untell_text

AI = "Moreover, the framework leverages robust methodologies to deliver outcomes at scale."


class MinimalRewriter:
    """Exactly the protocol's one behavioural member, and deliberately no `name`."""

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        return text.replace("Moreover, ", "")


class NamedRewriter:
    name = "my-custom-rewriter"

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        return text.replace("Moreover, ", "")


def _run(rw):
    return untell_text(AI, tier="lite", max_iters=1, best_of=1, seed=0, rewriter=rw)


class TestACompletedRunSurvivesAMissingName:
    def test_a_nameless_rewriter_does_not_crash_the_loop(self):
        result = _run(MinimalRewriter())
        assert isinstance(result.get("final"), str) and result["final"]

    def test_the_class_name_stands_in_so_the_field_is_still_informative(self):
        """Better than None: a reader of the result can still tell what produced it."""
        assert _run(MinimalRewriter())["rewriter"] == "MinimalRewriter"

    def test_a_declared_name_is_preferred_over_the_class_name(self):
        assert _run(NamedRewriter())["rewriter"] == "my-custom-rewriter"


class TestTheManifestDoesNotVouchForStrangers:
    def test_an_unrecognised_rewriter_is_unknown_not_reproducible(self):
        payload = _manifest_payload(
            AI, _run(NamedRewriter()), threshold=0.30, browser=None
        )
        assert payload["determinism"] == "unknown"
        assert "my-custom-rewriter" in payload["determinism_reason"]

    def test_the_reason_tells_the_caller_how_to_settle_it_themselves(self):
        payload = _manifest_payload(
            AI, _run(MinimalRewriter()), threshold=0.30, browser=None
        )
        assert "output_sha256" in payload["determinism_reason"]

    def test_a_known_local_rewriter_is_still_reproducible(self):
        """The guard must not have made the honest claim unreachable."""
        payload = _manifest_payload(
            AI, {"rewriter": "composite", "final": "x", "seed": 0}, threshold=0.30, browser=None
        )
        assert payload["determinism"] == "reproducible"

    def test_a_remote_rewriter_is_still_called_non_deterministic(self):
        payload = _manifest_payload(
            AI, {"rewriter": "anthropic", "final": "x", "seed": 0}, threshold=0.30, browser=None
        )
        assert payload["determinism"] == "non-deterministic by design"
