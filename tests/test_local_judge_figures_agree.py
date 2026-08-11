"""The local judge has two measured AUROCs, and every quotation of one has to say which.

README carried **0.59** in the tier table and 0.514 in the environment-variable table, both citing
the same 3.71s latency, which reads as one number contradicting itself. It is not: `local_judge.py`
records two runs —

    AUROC 0.591   20 labelled HC3 pairs, human mean 0.853, flags 89%
    AUROC 0.514   40 labelled HC3 pairs, human mean 0.90

— and each README mention was internally consistent with a different one. Neither stated its n,
which is the actual defect. A first attempt at "fixing" this replaced the 20-pair AUROC and mean
with the 40-pair ones while leaving the 20-pair flag rate in place, producing a mixture that was
never measured. That is the failure this file exists to prevent, so it checks that every quoted
figure is attributed rather than that all figures match.
"""

from __future__ import annotations

import pathlib
import re

_README = pathlib.Path("README.md").read_text(encoding="utf-8")
_SOURCE = pathlib.Path("untell/detectors/local_judge.py").read_text(encoding="utf-8")

_AUROC = re.compile(r"AUROC \*{0,2}(0\.\d+)\*{0,2}")
# "AUROC 0.514 on 40 labelled HC3 pairs" — the figure and the sample it came from.
_ATTRIBUTED = re.compile(r"AUROC \*{0,2}0\.\d+\*{0,2}\s+on\s+\d+\s+labelled")


def _judge_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if "judge" in ln.lower() and _AUROC.search(ln)]


def test_the_source_still_records_both_runs() -> None:
    """If a run is deleted, the README attributions below point at nothing."""
    assert _AUROC.findall(_SOURCE), "local_judge.py records no AUROC at all"
    assert {"0.591", "0.514"} <= set(_AUROC.findall(_SOURCE)), (
        f"expected both measured runs in local_judge.py, found {sorted(set(_AUROC.findall(_SOURCE)))}"
    )


def test_every_readme_figure_is_one_the_source_records() -> None:
    truth = set(_AUROC.findall(_SOURCE))
    quoted = {a for ln in _judge_lines(_README) for a in _AUROC.findall(ln)}
    assert quoted, "no local-judge AUROC in README — did the wording change?"
    assert quoted <= truth, f"README quotes {sorted(quoted - truth)}, which no run in the source produced"


def test_every_readme_figure_names_its_sample_size() -> None:
    """Two runs of the same detector are only distinguishable by n."""
    unattributed = [ln.strip()[:90] for ln in _judge_lines(_README) if not _ATTRIBUTED.search(ln)]
    assert not unattributed, f"AUROC quoted without its sample size: {unattributed}"
