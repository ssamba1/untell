"""Eight caveats nothing had ever seen appear.

This repository's honesty argument is carried by its caveats — the sentence beside a number saying
what the number is worth. FOUND by listing every function whose name says it produces one and asking
which the suite mentions:

    17 caveat-producing functions, 8 never named in any test

Named-in-a-test is a weak proxy, so each of the eight was driven with an input that should trigger
it. **All eight fire.** No dead caveat — that is the honest answer, and it is worth having rather than
assuming, because a caveat is exactly the kind of code that is never exercised by the happy path and
whose absence nobody notices.

The one that needed two attempts is instructive: `voice._warn_if_sample_is_thin` first reported
`AttributeError` because the probe called a function that does not exist. A probe failing and the
subject failing look identical from the outside, and only reading the error told them apart.

Two more only look dead. They describe the pure-stdlib lite path, and `tier="lite"` upgrades to
GPT-2 wherever torch imports, so asking for `lite` gets the path that has nothing to apologise for.
Forcing the path with `UNTELL_LITE_NO_TORCH=1` fires both. That is the recurring shape here: the
argument names a tier, not a path, and a test that conflates the two silently measures the other
one.

Each warns once per process via a module global, so every case resets it — otherwise the second test
to touch a module would find the flag already spent and read silence as a defect.
"""

from __future__ import annotations

import logging

import pytest

CHINESE = "这是一段中文文字，用来测试检测器的行为，看看它会不会给出一个虚假的判断结果。"
TELL_HEAVY = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes. "
    "Furthermore, it underscores the pivotal integration for every stakeholder involved today."
)


@pytest.fixture
def stdlib_lite(monkeypatch):
    """Force the pure-stdlib sub-path of `--tier lite`.

    Two of these caveats exist only to describe THAT path's weakness, and `lite` silently upgrades
    to GPT-2 whenever torch is importable — which it is in this venv. Without this the tests read
    `tier="lite"` as the path they meant and measure the other one; both failed for exactly that
    reason before it was added. `monkeypatch` is function-scoped and undoes itself, which matters
    here: an `os.environ` assignment at module level leaks to every later test in the process and
    has silently changed results in this suite before.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.fixture
def warnings_from(caplog):
    """Capture WARNING records, resetting the warn-once flags first."""

    def _run(resets, fn):
        import importlib

        for module_name, flag in resets:
            setattr(importlib.import_module(module_name), flag, False)
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            fn()
        return "\n".join(r.getMessage() for r in caplog.records)

    return _run


def test_humanness_says_when_the_text_is_too_short(warnings_from) -> None:
    import untell.humanness as mod

    out = warnings_from([("untell.humanness", "_WARNED_TOO_SHORT")],
                        lambda: mod.humanness("Hi there", tier="lite"))
    assert "shorter than" in out


def test_humanness_says_when_the_band_is_unreliable(warnings_from) -> None:
    import untell.humanness as mod

    out = warnings_from([("untell.humanness", "_WARNED_SHORT_BAND")],
                        lambda: mod.humanness(" ".join(["word"] * 20), tier="lite"))
    assert "does not separate the classes" in out


def test_humanness_says_when_the_script_is_unsupported(warnings_from) -> None:
    import untell.humanness as mod

    out = warnings_from([("untell.humanness", "_WARNED_UNSUPPORTED_LANGUAGE")],
                        lambda: mod.humanness(CHINESE, tier="lite"))
    assert "English-only catalogue cannot match" in out


def test_humanness_forwards_the_weak_path_caveat(stdlib_lite, warnings_from) -> None:
    """The one that matters most on this surface: `humanness` returns a bare float, so a log line is
    the only channel it has for "this number is weak evidence in both directions"."""
    import untell.humanness as mod

    out = warnings_from([("untell.humanness", "_WARNED_WEAK_PATH")],
                        lambda: mod.humanness(TELL_HEAVY, tier="lite"))
    assert "pure-stdlib lite path" in out


def test_sentence_targeting_says_when_it_is_near_chance(stdlib_lite, warnings_from) -> None:
    import untell.scripts.sentences as mod

    out = warnings_from([("untell.scripts.sentences", "_WARNED_UNINFORMATIVE")],
                        lambda: mod.score_sentences(TELL_HEAVY, tier="lite"))
    assert "near-chance" in out


def test_a_thin_voice_sample_is_flagged(warnings_from) -> None:
    import untell.scripts.voice as mod

    out = warnings_from([("untell.scripts.voice", "_WARNED_THIN_SAMPLE")],
                        lambda: mod._warn_if_sample_is_thin("a short sample of only a few words"))
    assert "under 150 words" in out


def test_a_full_voice_sample_is_not_flagged(warnings_from) -> None:
    """Guards the guard. A caveat that fires on everything says nothing."""
    import untell.scripts.voice as mod

    out = warnings_from([("untell.scripts.voice", "_WARNED_THIN_SAMPLE")],
                        lambda: mod._warn_if_sample_is_thin(" ".join(["word"] * 200)))
    assert not out.strip()


def test_the_loop_says_when_a_voice_sample_is_too_short(warnings_from) -> None:
    from untell.scripts.run import untell_text

    # The reset this case originally omitted. It passed alone and failed in the full suite, because
    # another test had already spent the once-per-process flag — the exact failure this file's
    # docstring warns about, made in the one place no reset was passed.
    out = warnings_from([("untell.scripts.run", "_WARNED_VOICE_SAMPLE")], lambda: untell_text(
        TELL_HEAVY, tier="lite", max_iters=1, rewriter="structural", best_of=1,
        voice_sample="tiny",
    ))
    assert "voice" in out.lower()


def test_preserve_says_when_it_has_no_ner(warnings_from) -> None:
    import untell.scripts.preserve as mod

    # The gate is a module-level one-shot, so anything earlier in the session that reached this
    # warning leaves it spent and this test asserts on an empty string forever after. MEASURED
    # 2026-09-01: it passed alone and failed in the file, which is the worst shape for a caveat
    # test -- it looks like coverage and checks nothing. Reset before asserting.
    mod._WARNED_NO_NER = False
    try:
        out = warnings_from([], mod._warn_no_ner)
    finally:
        mod._WARNED_NO_NER = False
    assert out.strip()


def test_the_ner_caveat_names_the_piece_that_is_actually_missing(warnings_from, monkeypatch):
    """The remedy has to match the gap, or it sends the user to a command that cannot run.

    `_spacy_entity_spans` checks for the MODEL without importing spaCy — a deliberate 5s saving,
    documented at the call site. The warning it reached then asserted "spaCy is installed",
    which that path had never checked. MEASURED 2026-09-01 in a container with neither: the
    message named a missing model and prescribed `python -m spacy download en_core_web_sm`,
    which fails with "No module named spacy". Right symptom, wrong diagnosis, unusable fix.
    """
    import importlib.util

    import untell.scripts.preserve as mod

    real = importlib.util.find_spec

    def no_spacy(name, *a, **kw):
        return None if name == "spacy" else real(name, *a, **kw)

    monkeypatch.setattr(importlib.util, "find_spec", no_spacy)
    monkeypatch.setattr(mod, "_WARNED_NO_NER", False)
    out = warnings_from([], mod._warn_no_ner)
    assert "pip install spacy" in out, (
        f"with spaCy absent the message prescribes a spacy subcommand the user cannot run: {out}"
    )

    # ...and where spaCy really is present, the remedy stays the short one. Reset by assignment,
    # not a second `monkeypatch.setattr`: that would capture the True this test just set and
    # restore THAT at teardown, leaving the one-time gate closed for every test after this one.
    mod._WARNED_NO_NER = False
    out = warnings_from([], lambda: mod._warn_no_ner(spacy_present=True))
    assert "pip install spacy" not in out and "spacy download" in out, out
