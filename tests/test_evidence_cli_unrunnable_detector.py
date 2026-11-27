"""A detector untell cannot run must not crash the evidence commands with a traceback.

The commonest first command is someone holding a Turnitin score: `untell brief --detector
turnitin --score 0.82`. Turnitin has no API, so `resolve_scorer` raises; `brief` used to die with
a ValueError traceback. It now builds the brief from the reported score and published rates and
says how to run the stability test by hand. Commands whose whole job is re-running the detector
(`stability`, `report-card`) fail with a one-line usage error instead.
"""

from __future__ import annotations

import pytest

from untell.evidence.cli import brief_main, stability_main

TEXT = ("School uniforms should be mandatory. Moreover, it is important to note that uniforms "
        "foster a sense of community and reduce bullying in every school.")


def test_brief_falls_back_to_the_reported_score_for_an_unrunnable_detector(capsys) -> None:
    assert brief_main(["--detector", "Turnitin", "--score", "0.82", "--flagged", "yes", TEXT]) == 0
    out, err = capsys.readouterr()
    assert "cannot run 'Turnitin'" in err
    assert "manual:scores.csv --name Turnitin" in err
    assert "Traceback" not in err
    assert "**Detector:** Turnitin" in out
    assert "turnitin.com" in out  # the published rates were still looked up by name


def test_brief_without_a_key_for_a_commercial_detector_still_builds(capsys, monkeypatch) -> None:
    monkeypatch.delenv("GPTZERO_API_KEY", raising=False)
    assert brief_main(["--detector", "gptzero", "--score", "0.9", TEXT]) == 0
    _, err = capsys.readouterr()
    assert "cannot run 'gptzero'" in err


def test_brief_still_rejects_a_broken_runnable_spec(capsys) -> None:
    with pytest.raises(SystemExit) as e:
        brief_main(["--detector", "manual:/no/such/scores.csv", TEXT])
    assert e.value.code == 2


def test_stability_reports_an_unknown_detector_as_a_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as e:
        stability_main(["--detector", "turnitin", TEXT])
    assert e.value.code == 2
    assert "unknown detector 'turnitin'" in capsys.readouterr().err


# --- ordinary user errors: one line, exit 2, no traceback ------------------------------------

from untell.evidence.cli import (  # noqa: E402
    capsule_main,
    drift_main,
    flagmath_main,
    report_card_main,
    variants_main,
)


@pytest.mark.parametrize("main, argv", [
    (brief_main, ["--file", "/no/such/doc.txt"]),
    (stability_main, ["--file", "/no/such/doc.txt"]),
    (variants_main, ["--file", "/no/such/doc.txt"]),
    (report_card_main, ["--human", "/no/such/human.jsonl", "--detector", "local:lite"]),
    (drift_main, ["/no/such/a.json", "/no/such/b.json"]),
])
def test_a_missing_input_file_is_one_line_not_a_traceback(main, argv, capsys, monkeypatch) -> None:
    monkeypatch.delenv("UNTELL_DEBUG", raising=False)
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert "error: No such file or directory: /no/such/" in err
    assert len(err.strip().splitlines()) == 1


def test_untell_debug_restores_the_traceback(monkeypatch) -> None:
    monkeypatch.setenv("UNTELL_DEBUG", "1")
    with pytest.raises(FileNotFoundError):
        drift_main(["/no/such/a.json", "/no/such/b.json"])


@pytest.mark.parametrize("argv", [["--fpr", "2"], ["--fpr", "-0.1"], ["--fpr", "0.02", "--tpr", "90"]])
def test_flagmath_rejects_a_rate_outside_zero_to_one(argv, capsys) -> None:
    with pytest.raises(SystemExit) as e:
        flagmath_main(argv)
    assert e.value.code == 2
    assert "between 0 and 1" in capsys.readouterr().err


def test_capsule_names_a_path_that_is_not_a_git_repository(tmp_path, capsys) -> None:
    with pytest.raises(SystemExit) as e:
        capsule_main([str(tmp_path), "--out", str(tmp_path / "c.jsonl")])
    assert e.value.code == 2
    assert "not a git repository" in capsys.readouterr().err
