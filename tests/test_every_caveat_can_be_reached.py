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

    # The flag is once-per-process: without resetting it this passed or failed by test order (it
    # failed in the lite tier, where an earlier test had already triggered the warning).
    out = warnings_from([("untell.scripts.preserve", "_WARNED_NO_NER")], mod._warn_no_ner)
    assert out.strip()


def test_preserve_says_spacy_itself_is_missing(warnings_from) -> None:
    """The base install has no spaCy: it must not be told to `spacy download` a model.

    It used to get "spaCy is installed but the 'en_core_web_sm' model is not" and a download
    command that fails without spaCy, because the cheap model check ran first and assumed spaCy.
    """
    import untell.scripts.preserve as mod

    out = warnings_from([("untell.scripts.preserve", "_WARNED_NO_SPACY")], mod._warn_no_spacy)
    assert "spaCy is not installed" in out
    assert "untell[full]" in out



@pytest.mark.parametrize("spacy_present, expected", [
    (False, "_warn_no_spacy"),
    (True, "_warn_no_ner"),
])
def test_the_missing_piece_picks_the_message(monkeypatch, spacy_present, expected) -> None:
    """No spaCy -> the install hint; spaCy without its model -> the download hint."""
    import importlib.util

    import untell.scripts.preserve as mod

    called: list[str] = []
    monkeypatch.setattr(mod, "_warn_no_spacy", lambda: called.append("_warn_no_spacy"))
    monkeypatch.setattr(mod, "_warn_no_ner", lambda: called.append("_warn_no_ner"))
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    real_find_spec = importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        if name == "en_core_web_sm":
            return None
        if name == "spacy":
            return object() if spacy_present else None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    # The loaded pipeline is cached on the function, and results are cached by text: start from
    # "never loaded", use a text no other test passes, and put the cached pipeline back after.
    sentinel = object()
    saved = getattr(mod._spacy_entity_spans, "_nlp", sentinel)
    if saved is not sentinel:
        del mod._spacy_entity_spans._nlp
    try:
        text = f"Ada Lovelace met Charles Babbage in London ({expected})."
        assert mod._spacy_entity_spans(text) == []
        assert called == [expected]
    finally:
        if saved is sentinel:
            if hasattr(mod._spacy_entity_spans, "_nlp"):
                del mod._spacy_entity_spans._nlp
        else:
            mod._spacy_entity_spans._nlp = saved
