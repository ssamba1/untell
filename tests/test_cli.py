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
