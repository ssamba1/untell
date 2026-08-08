"""Tests for the humanizer technique-comparison harness."""

from __future__ import annotations

import eval.compare_humanizers as C
from eval.compare_humanizers import _read_corpus, _render, compare


def test_read_corpus_splits_on_blank_lines(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text("para one here.\n\npara two here.\n\n\npara three.", encoding="utf-8")
    assert _read_corpus(str(p)) == ["para one here.", "para two here.", "para three."]


def test_render_handles_metrics_and_errors():
    r = {
        "n": 2,
        "tier": "lite",
        "threshold": 0.3,
        "techniques": {
            "none (raw AI)": {
                "ai_max_mean": 0.5,
                "tells_per_100w_mean": 12.0,
                "tells_total": 6,
                "sim_mean": 1.0,
                "flagged_rate": 1.0,
            },
            "back_translation": {"error": "RuntimeError: no marian"},
        },
    }
    out = _render(r)
    assert "none (raw AI)" in out
    assert "skipped" in out and "no marian" in out


def test_compare_aggregates_with_stub_techniques(monkeypatch):
    # Stub the technique set so the test is fast and deterministic (no models, no network).
    def fake_techniques(tier, threshold):
        return {
            "none (raw AI)": lambda t: t,
            "strip_vocab": lambda t: t.replace("leverage", "use").replace("Furthermore, ", ""),
        }

    monkeypatch.setattr(C, "_techniques", fake_techniques)
    # Also stub score_text so we don't load detector models in a unit test.
    monkeypatch.setattr(C, "score_text", lambda text, tier="full": {"max": 0.4 if "leverage" in text else 0.1})

    texts = ["Furthermore, we leverage robust tools. Moreover, studies show it is pivotal and seamless."]
    r = compare(texts, tier="lite", threshold=0.3)
    assert r["n"] == 1
    t = r["techniques"]
    assert set(t) == {"none (raw AI)", "strip_vocab"}
    # raw keeps similarity 1.0 by construction; stripped vocab lowers the AI score and the tells.
    assert t["none (raw AI)"]["sim_mean"] == 1.0
    assert t["strip_vocab"]["ai_max_mean"] <= t["none (raw AI)"]["ai_max_mean"]
    assert t["strip_vocab"]["tells_per_100w_mean"] <= t["none (raw AI)"]["tells_per_100w_mean"]


def test_compare_empty_corpus_does_not_divide_by_zero():
    r = compare([], tier="lite")
    assert r["n"] == 0
    assert r["techniques"] == {}


def test_compare_records_error_for_failing_technique(monkeypatch):
    def boom_techniques(tier, threshold):
        def boom(t):
            raise RuntimeError("dep missing")

        return {"none (raw AI)": lambda t: t, "boom": boom}

    monkeypatch.setattr(C, "_techniques", boom_techniques)
    monkeypatch.setattr(C, "score_text", lambda text, tier="full": {"max": 0.2})
    r = compare(["some text here"], tier="lite")
    assert "error" in r["techniques"]["boom"]
    assert "dep missing" in r["techniques"]["boom"]["error"]


def test_silent_noop_technique_is_not_published_as_a_measurement(monkeypatch):
    """back_translate degrades to a SILENT no-op (returns its input, no exception) when
    transformers/torch/sentencepiece are missing, so the `except` guard never fires.

    Recording the numbers anyway publishes the raw-AI baseline — sim_mean 1.0, ai and tells
    identical to the untouched text — as if it were a real measurement of the technique. Those
    numbers then get quoted in the docs as the technique's performance."""
    import eval.compare_humanizers as c

    monkeypatch.setattr(c, "_ai_max", lambda out, tier: 0.5)
    monkeypatch.setattr(
        c, "_techniques",
        lambda tier, threshold: {
            "none (raw AI)": lambda t: t,
            "noop_technique": lambda t: t,          # the missing-dep case
            "real_technique": lambda t: t.replace("AI", "stuff"),
        },
    )

    r = c.compare(["AI text one here.", "AI text two here."], tier="lite")
    rows = r.get("techniques", r)

    assert "error" in rows["noop_technique"]
    assert "NO change" in rows["noop_technique"]["error"]
    # The baseline is legitimately unchanged and must still be measured.
    assert "ai_max_mean" in rows["none (raw AI)"]
    # A technique that genuinely rewrites still reports numbers.
    assert "ai_max_mean" in rows["real_technique"]


class TestTheHeadToHeadCanRunOnAPublicCorpus:
    """The central competitive artifact ran on three built-in paragraphs.

    This document's own free-ceiling report calls that corpus "a demo, and measurably easier than
    real AI output", and the difference is not cosmetic. MEASURED on the built-in samples,
    back_translation ties us on evasion (0.267 vs our 0.271); on real HC3 text at n=6 it does not
    come close (0.581 vs 0.287, flagged 83% vs 17%), and it costs meaning we keep (0.911 vs 0.987).

    A head-to-head anyone can reproduce has to run on a corpus anyone can fetch, so `--dataset`
    exists. Nine results in this repository once generalised from a demo corpus, which is why the
    result now also records WHICH corpus produced it.
    """

    def test_the_dataset_and_n_flags_exist(self):
        """Parsed, not run: the run itself needs a corpus download."""
        import contextlib
        import io

        from eval.compare_humanizers import main

        help_text = io.StringIO()
        with contextlib.redirect_stdout(help_text), contextlib.suppress(SystemExit):
            main(["--help"])
        out = help_text.getvalue()
        assert "--dataset" in out, "the head-to-head cannot run on a public corpus"
        assert "--n" in out
        for name in ("hc3", "raid", "mage"):
            assert name in out, f"{name} is not offered as a corpus"

    def test_the_result_records_its_corpus(self):
        from eval.compare_humanizers import compare

        result = compare(["Moreover, the system leverages robust methodologies."], tier="lite")
        # `compare` itself does not set it; `main` does, because only main knows the source.
        assert "corpus" not in result or isinstance(result["corpus"], str)

    def test_the_renderer_shows_the_corpus(self):
        from eval.compare_humanizers import _render

        line = _render({"corpus": "hc3 n=6", "tier": "full", "n": 6, "threshold": 0.3,
                        "techniques": {}}).splitlines()[0]
        assert "hc3 n=6" in line, f"the corpus is not in the header: {line}"

    def test_an_unnamed_corpus_does_not_crash_the_renderer(self):
        from eval.compare_humanizers import _render

        line = _render({"tier": "full", "n": 3, "threshold": 0.3, "techniques": {}}).splitlines()[0]
        assert "unknown" in line
