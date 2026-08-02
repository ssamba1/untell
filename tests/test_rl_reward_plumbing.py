"""Reward plumbing for the GRPO trainer — no torch, no trl, no GPU.

These are the paths where a wrong value is silently a *valid-looking* reward, which is worse than
a crash: GRPO scores a group of k candidates per prompt and learns from their spread, so a batch
of identical rewards trains on nothing while the loss curve keeps moving.
"""

from __future__ import annotations

import pytest

from training.reward import batch_rewards, fluency, humanness_reward
from training.rl_humanizer import _source_resolver
from untell.rewriter.local_policy import _TRAIN_PROMPT


def test_resolver_returns_the_source_for_a_known_prompt():
    src = "Furthermore, the system leverages robust methodologies to optimize outcomes."
    resolve = _source_resolver({_TRAIN_PROMPT.format(text=src): src})
    assert resolve(_TRAIN_PROMPT.format(text=src)) == src


def test_resolver_survives_whitespace_renormalisation():
    """A tokenize/decode round-trip can collapse whitespace; an exact-match dict then misses."""
    src = "Moreover, organizations increasingly leverage these technologies."
    prompt = _TRAIN_PROMPT.format(text=src)
    resolve = _source_resolver({prompt: src})
    assert resolve(prompt.replace("\n\n", "\n")) == src


def test_resolver_recovers_the_source_by_stripping_the_prompt_prefix():
    src = "Ultimately, a comprehensive security posture is essential for success."
    resolve = _source_resolver({})  # nothing registered at all
    assert resolve(_TRAIN_PROMPT.format(text=src)) == src


def test_resolver_returns_none_rather_than_the_prompt_itself():
    """`source_by_prompt.get(p, p)` handed back the prompt, which fails the similarity and length
    gates every time — so an unmappable prompt quietly made every reward in the batch -1.0 with
    no error and no log line."""
    resolve = _source_resolver({})
    assert resolve("a bare string that is not a prompt at all") is None


def test_humanness_reward_returns_minus_one_for_none_instead_of_crashing():
    """GRPO can hand None to the reward fn when a generation step fails or emits no tokens; the
    AttributeError propagated out and killed the run with no checkpoint."""
    assert humanness_reward("some original text here", None) == -1.0
    assert humanness_reward(None, "some candidate text here") == -1.0
    assert humanness_reward(None, None) == -1.0


def test_batch_rewards_defaults_to_the_backend_bar_not_a_hardcoded_one(monkeypatch):
    """humanness_reward was fixed to ask recommended_bar() for the active similarity backend;
    batch_rewards — the path GRPO actually calls — kept its own hardcoded 0.76."""
    import inspect

    assert inspect.signature(batch_rewards).parameters["sim_floor"].default is None

    seen = []
    import training.reward as reward_mod

    monkeypatch.setattr(reward_mod, "humanness_reward", lambda o, c, **kw: seen.append(kw) or 0.0)
    reward_mod.batch_rewards("original text", ["a", "b"])
    assert all(kw["sim_floor"] is None for kw in seen)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("yes yes yes", pytest.approx(1 / 3)),
        ("the cat sat", 1.0),
        ("no no", 0.5),
        ("hello", 1.0),
    ],
)
def test_fluency_penalises_short_degenerate_repetition(text, expected):
    """Under four words fluency returned a flat 1.0, so a 1-3 token repetition — the completion
    GRPO is most likely to sample when it degenerates — earned zero quality penalty."""
    assert fluency(text) == expected


def test_fluency_unchanged_for_normal_length_text():
    assert fluency("The committee rejected the proposal last week without much debate.") == 1.0
    assert fluency("spam spam spam spam spam spam") < 0.3
