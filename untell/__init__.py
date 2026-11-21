"""untell — an AI-detector auditing toolkit: what is a detector's verdict worth?

The runnable Python lives in a few places:
  - ``untell.evidence`` — evidence briefs, verdict stability, report cards, drift (the audit).
  - ``untell.detectors`` — tiered detector adapters (local and commercial) behind one protocol.
  - ``untell.scripts`` — score / preserve / quality helpers the skill shells out to, and the
    detector-in-the-loop robustness probe.
  - ``untell.bench`` / ``untell.training`` — measurement harnesses and GPU training code.

The ``lite`` tier runs on the standard library alone (no model downloads); ``full`` and
``heavy`` tiers activate automatically when their optional dependencies are installed.
"""

__version__ = "0.4.0"
