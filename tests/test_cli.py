"""CLI / entry-point tests across the scripts and the benchmark."""

from __future__ import annotations

import json

import pytest

from eval.benchmark import main as bench_main
from untell.scripts.preserve import lock, restore
from untell.scripts.preserve import main as preserve_main
from untell.scripts.quality import main as quality_main
from untell.scripts.score import main as score_main


def test_preserve_restore_cli_roundtrip(capsys):
    text = "Smith (2020) found 42% across [3] cases."
    masked, mapping = lock(text)
    rc = preserve_main(["--restore", "--mapping", json.dumps(mapping), masked])
    assert rc == 0
    assert capsys.readouterr().out.strip() == text


def test_preserve_lock_then_restore_via_cli(capsys):
    rc = preserve_main(["According to Smith (2020), adoption rose 47%."])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["mapping"]
    rc = preserve_main(["--restore", "--mapping", json.dumps(parsed["mapping"]), parsed["masked"]])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "According to Smith (2020), adoption rose 47%."


def test_preserve_restore_mapping_file(tmp_path, capsys):
    text = "Jones (2019) reported 3.14 across [7] trials."
    masked, mapping = lock(text)
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps(mapping), encoding="utf-8")
    rc = preserve_main(["--restore", "--mapping-file", str(mf), masked])
    assert rc == 0
    assert capsys.readouterr().out.strip() == text


def test_restore_unknown_sentinel_passthrough():
    assert restore("keep ⟦HZ9999⟧ as-is", {}) == "keep ⟦HZ9999⟧ as-is"


def test_quality_cli_too_few_args_returns_2():
    assert quality_main(["only-one-arg"]) == 2


def test_score_cli_logs_tier_to_stderr(capsys):
    rc = score_main(["Furthermore, the system performs adequately overall.", "--tier", "lite"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "tier" in cap.err and "ran=lite" in cap.err
    json.loads(cap.out)  # stdout stays pure JSON


def test_benchmark_main_writes_markdown(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = bench_main(["--dataset", "builtin", "--n", "3", "--tier", "lite", "--out", str(out)])
    assert rc == 0
    body = out.read_text(encoding="utf-8")
    assert "untell benchmark" in body


def test_benchmark_main_rejects_unknown_strategy():
    with pytest.raises(SystemExit):
        bench_main(["--strategies", "bogus", "--dataset", "builtin", "--n", "2"])


def test_score_text_survives_detector_exception(monkeypatch):
    from untell.scripts import score as score_mod

    class Boom:
        name = "boom"
        tier = "lite"

        def available(self):
            return True

        def score(self, text):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(score_mod, "load_detectors", lambda tier: [Boom()])
    r = score_mod.score_text("hello", tier="lite")
    assert r["detectors"]["boom"] is None
    assert "boom__error" in r["detectors"]
    # No numeric scores -> the loop must NOT be handed a fake 0.5 (the real-world bug that pinned
    # max when detectors silently died). max is 0.0, the run is not-flagged, and the failure is
    # surfaced explicitly instead of masked.
    assert r["max"] == 0.0
    assert r["flagged"] is False
    assert "boom" in r["failed_detectors"]


def test_style_warns_only_for_backends_with_no_register_knob(capsys):
    """--style is now honoured by the rule-based path (structural register profiles) and by the
    hosted-LLM rewriter. `surgical` is purely word-level and has no register knob, so it must say so
    rather than accept a documented flag and do nothing — the same class of defect as a detector
    returning a fabricated score."""
    from untell.scripts.run import main

    main(["Moreover we utilize robust solutions today.", "--rewriter", "surgical",
          "--style", "casual", "--tier", "lite", "--max-iters", "1"])
    err = capsys.readouterr().err
    assert "--style" in err and "no effect" in err


def test_style_aware_backend_does_not_warn(capsys):
    """composite honours style via structural, so warning there would be false."""
    from untell.scripts.run import main

    main(["Moreover we utilize robust solutions today.", "--rewriter", "composite",
          "--style", "casual", "--tier", "lite", "--max-iters", "1"])
    assert "no effect" not in capsys.readouterr().err


def test_no_style_warning_when_style_not_requested(capsys):
    from untell.scripts.run import main

    main(["Moreover we utilize robust solutions today.", "--rewriter", "surgical",
          "--tier", "lite", "--max-iters", "1"])
    assert "no effect" not in capsys.readouterr().err


class TestDemoUsesTheStrongestAvailableTier:
    """`untell` with no arguments is the first thing a new user runs, and it hardcoded tier="lite".

    MEASURED on the demo's own deliberately-AI sample ("Furthermore, artificial intelligence has
    fundamentally transformed numerous industries..."):

        tier=lite   detector max 0.364   humanness 56.4  "mostly human"
        tier=full   detector max 1.000   humanness 24.6  "likely AI"

    So the tool's own demo answered "mostly human" about text written to be obviously machine-
    generated. The lite heuristic is documented as a weak proxy; leading with it here undersold the
    tool and misinformed the reader.
    """

    def _run_demo(self, monkeypatch, capsys, no_torch: bool):
        from untell.scripts.cli import _run_demo

        if no_torch:
            monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
        else:
            monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)
        _run_demo()
        return capsys.readouterr().out

    def test_the_tier_that_ran_is_named(self, monkeypatch, capsys):
        """"mostly human" from the weak heuristic and "likely AI" from the real ensemble are
        different claims; without the tier a reader cannot tell them apart."""
        out = self._run_demo(monkeypatch, capsys, no_torch=True)
        assert "(tier:" in out

    def test_forced_stdlib_path_is_honoured(self, monkeypatch, capsys):
        """UNTELL_LITE_NO_TORCH=1 is the documented way to force the dependency-free path. A user
        who asks for it must not be handed a model-backed score instead."""
        out = self._run_demo(monkeypatch, capsys, no_torch=True)
        assert "(tier: lite)" in out

    def test_full_tier_is_used_when_the_full_stack_actually_loads(self, monkeypatch, capsys):
        """`import torch` succeeding is not the same as the full tier working.

        A torch/NumPy ABI mismatch imports fine and then fails every model load, so `score_text`
        resolves to lite and says so in its `warning`. Keying the skip on the import made this test
        fail on such installs while `untell score` was correctly reporting the degradation — the
        tool honest, the test wrong. Ask the scorer what tier it actually reached.
        """
        pytest.importorskip("torch")
        from untell.scripts.score import score_text

        probe = score_text("Furthermore, the system leverages robust methodologies.", tier="full")
        if probe.get("tier") != "full":
            pytest.skip(f"full tier does not load here: {probe.get('warning', 'no detectors')}")

        out = self._run_demo(monkeypatch, capsys, no_torch=False)
        assert "(tier: full)" in out, out[-400:]
