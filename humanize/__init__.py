"""humanize — closed-loop, detector-feedback AI-text humanizer packaged as a Claude skill.

The runnable Python lives in two places:
  - ``humanize.scripts`` — score / preserve / quality helpers the skill shells out to.
  - ``humanize.detectors`` — tiered detector adapters behind a common protocol.

The ``lite`` tier runs on the standard library alone (no model downloads); ``full`` and
``heavy`` tiers activate automatically when their optional dependencies are installed.
"""

__version__ = "0.1.0"
