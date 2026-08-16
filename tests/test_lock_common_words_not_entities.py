"""Killing test: spaCy NER must not lock common English words as entities.

spaCy's en_core_web_sm tags the capitalised verb 'Email' as a PERSON
(measured: 'Email me the file' -> [('Email', 'PERSON')]). lock() then treats
it as a protected fact, so a rewrite can never touch sentence-initial
'Email' — a false positive in the NER entity lock. Same class: 'May',
'Will', 'Mark' as verbs.

This test pins the fix: common-word PERSON entities must not produce
lock spans. Skipped when spaCy/model absent (the lock already no-ops).
"""
import pytest

spacy = pytest.importorskip("spacy")
pytest.importorskip("en_core_web_sm")

from untell.scripts.preserve import lock  # noqa: E402  (after importorskip guard)

VERB_FALSE_POSITIVES = [
    "Email me the file",          # 'Email' is a verb, not a person
    "Email us at support",        # same
    "This Email needs review",    # noun use
    "May we proceed",             # 'May' modal, not a month/person
    "Will you help",              # 'Will' future marker
    "Mark the spot",              # 'Mark' verb
]


@pytest.fixture(autouse=True)
def _real_ner_env(monkeypatch):
    """This module tests the NER pass itself, so UNTELL_LITE_NO_TORCH must be OFF.

    The env var (README) forces the pure-stdlib path and therefore skips the spaCy NER
    pass entirely (spaCy imports torch through thinc) — a run pinned stdlib-only cannot
    lock entities. CI exports the env var, so without clearing it here every assertion
    in this file would be vacuously true and `test_real_entity_still_locked` would fail.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)


def test_common_word_person_entities_not_locked():
    for text in VERB_FALSE_POSITIVES:
        masked, mapping = lock(text)
        # The common word must survive lock() unmasked
        first_word = text.split()[0]
        assert first_word in masked, (
            f"lock() masked common word {first_word!r} in {text!r}: {masked!r}"
        )


def test_real_entity_still_locked():
    # A genuine person entity must still lock
    masked, mapping = lock("Contact John Smith about the project")
    assert "John Smith" not in masked, f"real entity not locked: {masked!r}"
    assert any("Smith" in v for v in mapping.values()), f"mapping lost Smith: {mapping}"
