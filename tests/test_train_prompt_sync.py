"""The training prompt must have exactly one definition.

The policy is RL-trained on one instruction and prompted with it again at inference. When a
trainer re-types that string as its own literal, editing the canonical one leaves that trainer
producing a model tuned on a different prompt than the one it will be served with — and nothing
reports the drift except a quiet drop in output quality.
"""

from __future__ import annotations

import re
from pathlib import Path

from untell.rewriter.local_policy import _TRAIN_PROMPT

_ROOT = Path(__file__).resolve().parent.parent
_CANONICAL = "untell/rewriter/local_policy.py"


def test_every_trainer_uses_the_same_prompt_object():
    from training.distill import _PROMPT as distill_prompt
    from training.dpo_humanizer import _PROMPT as dpo_prompt
    from training.rl_humanizer import _PROMPT as rl_prompt

    assert distill_prompt is _TRAIN_PROMPT
    assert dpo_prompt is _TRAIN_PROMPT
    assert rl_prompt is _TRAIN_PROMPT


def test_no_module_re_types_the_prompt_as_a_literal():
    """Equality today is not the property that matters — a single source of truth is."""
    needle = "Rewrite the following text so it reads as natural human writing"
    offenders = []
    for path in list(_ROOT.glob("training/*.py")) + list(_ROOT.glob("untell/**/*.py")) + list(
        _ROOT.glob("eval/*.py")
    ):
        rel = path.relative_to(_ROOT).as_posix()
        if rel == _CANONICAL:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        # Only flag it inside a string literal, so a comment mentioning the prompt is fine.
        if re.search(r'["\']' + re.escape(needle), body):
            offenders.append(rel)

    assert not offenders, (
        f"{offenders} re-type the training prompt instead of importing _TRAIN_PROMPT from "
        f"{_CANONICAL}; a change there would silently leave them training on the old instruction"
    )
