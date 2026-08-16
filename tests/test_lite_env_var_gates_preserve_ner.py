"""UNTELL_LITE_NO_TORCH=1 must also gate the preserve layer's spaCy NER pass.

The env var is documented (README env table) as "force the pure-stdlib lite path even
when torch is installed", and it already gates the perplexity detector, the quality
gate's embedding backend, and the NLI/roles meaning gates (test_lite_env_var_gates_nli_
and_roles.py). It did NOT gate `preserve._spacy_entity_spans`: `lock()` — called from
`_mostly_locked_warning` on every scoring pass and from the rewrite loop — imported
spaCy, and spaCy imports torch itself through thinc (`thinc.compat` imports torch when
installed), so "no torch" was violated on the one path documented as stdlib-only.

MEASURED on this machine (torch installed): `untell-score --tier lite -q "..."` under
the env var took 26.9-44.4s and imported torch/transformers/spacy/thinc; with the NER
pass gated the same call completes in ~0.5s with none of those imported.
"""
from __future__ import annotations

import builtins

from untell.scripts.preserve import _spacy_entity_spans, lock

HEAVY = {"torch", "transformers", "spacy", "thinc"}


def _no_heavy_imports(monkeypatch):
    """Fail the test if any heavy library is imported after this point."""
    real_import = builtins.__import__

    def spy_import(name, *a, **kw):
        top = name.split(".")[0]
        assert top not in HEAVY, (
            f"{name} was imported under UNTELL_LITE_NO_TORCH=1"
        )
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", spy_import)


def test_entity_spans_skip_without_importing_spacy_or_torch(monkeypatch):
    """The whole point: a lite run must not pay spaCy/thinc/torch's import."""
    _no_heavy_imports(monkeypatch)
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    assert _spacy_entity_spans("Alice met Bob at the office on Monday.") == []


def test_lock_still_locks_regex_facts_without_heavy_imports(monkeypatch):
    """The regex locks (citations, numbers, quotes, URLs) survive the NER skip."""
    _no_heavy_imports(monkeypatch)
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    masked, mapping = lock("As Smith (2020) reported, 47% of cases rose $500.")
    # lock() replaces each protected span with a sentinel; the mapping holds the originals.
    assert any("Smith (2020)" in v for v in mapping.values()), f"citation lost: {mapping}"
    assert any("47%" in v for v in mapping.values()), f"number lost: {mapping}"
    assert any("$500" in v for v in mapping.values()), f"amount lost: {mapping}"


def test_env_gate_warns_once(monkeypatch, caplog):
    import logging

    import untell.scripts.preserve as preserve

    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(preserve, "_WARNED_NO_NER_ENV", False)
    with caplog.at_level(logging.WARNING, logger="untell.scripts.preserve"):
        _spacy_entity_spans("Alice met Bob on Monday.")
        _spacy_entity_spans("Bob met Alice on Tuesday.")
    names = [r.getMessage() for r in caplog.records if "UNTELL_LITE_NO_TORCH" in r.getMessage()]
    assert len(names) == 1, f"expected exactly one env-gate warning, got {len(names)}"


def test_ner_re_enabled_when_env_var_unset(monkeypatch):
    """Clearing the env var must restore the real NER pass (no permanent disable)."""
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
    spans = _spacy_entity_spans("Alice met Bob at the office on Monday.")
    # Real NER on en_core_web_sm tags Alice/Bob as PERSON — but only when the model is
    # installed; the point is that the env gate did not poison the unset path.
    import importlib.util

    if importlib.util.find_spec("en_core_web_sm") is not None:
        assert spans, "NER pass returned no spans with the env var unset"
