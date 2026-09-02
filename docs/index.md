# untell — an AI-detector auditing toolkit

**Measure whether an AI detector can be trusted: what it does to writing a human actually wrote, how stable its verdict is, and whether that verdict survives meaning-preserving edits.**

[![CI](https://github.com/ssamba1/untell/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/untell/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/untell)](https://pypi.org/project/untell/)

---

## What this is for

An AI detector gives you a number, and that number is increasingly used to make consequential accusations. This measures what it is worth. Measured here, at each tool's own shipped threshold: the full local ensemble flags **17% of genuine human writing**; the lite tier flagged **30%** on conversational prose; one bundled detector flags **6 of 8** human documents and another flags **89%** of them.

The rewrite loop is the instrument, not the product: score, edit under a meaning gate, re-score — because a verdict that collapses under meaning-preserving editing was never measuring authorship. Its result is a negative one, and it is stated as such: the loop moves the detectors it optimises against and **does not move a detector it has never seen**.

That iterative, detector-feedback approach is the strongest *training-free* technique in the published literature ([arXiv 2506.07001](https://arxiv.org/abs/2506.07001): −88% TPR@1%FPR, transfers across detectors, preserves meaning) — and **no shipping tool, open or commercial, actually does it.**

## Key capabilities

| Capability | untell | Others |
|---|---|---|
| **Closed detector-feedback loop** | ✅ | ❌ blind single pass |
| **Real detectors in the loop** | ✅ 8 local + 7 commercial | ❌ internal proxy only |
| **Semantic meaning gate** | ✅ NLI entailment + contradiction veto, over a similarity bar | ❌ no verification |
| **Per-sentence targeting** | ✅ rewrite only the flagged spans | ❌ whole-text reroll |
| **Citation lock** | ✅ byte-for-byte preserve | ❌ facts get mangled |
| **Free no-key path** | ✅ surgical rewriter ($0) | ❌ paid API required |
| **Run locally** | ✅ CPU, no GPU needed | ❌ cloud-only |
| **MCP server** | ✅ Claude Desktop integration | ❌ |
| **REST API server** | ✅ FastAPI, auth, OpenAPI | ❌ |
| **Open source** | ✅ MIT | ❌ closed SaaS |

## Quick install

```bash
pip install untell                     # zero-dependency lite tier
pip install "untell[full]"             # real detector ensemble on CPU
pip install "untell[server]"           # REST API server
```

One command to humanize:

```bash
untell humanize "Your AI-sounding paragraph here." --rewriter surgical
```

## The measurement log — start here

Most tools in this space publish a benchmark table. This one publishes **[the full measurement
log](free-ceiling-measured.md)**: 229 numbered results, including every experiment that *failed* and
every claim of ours that a later measurement refuted.

A sample of what is in there, because the refutations are the point:

| | |
|---|---|
| **Result 17** | The hypothesis that one stubborn detector sets the ceiling — **refuted**. The reported `max` is an envelope; different texts are caught by different detectors. |
| **Result 18** | A diversity gate that provided *no* diversity. Draw-to-draw similarity was identical to four decimals with it on and off. |
| **Result 21** | Two structural moves measured and then **declined**: passive→active reaches too little to justify the grammar risk, and first-person injection would make the tool assert a stance its input never had. |
| **Result 22** | The rewriter was emitting **sentence fragments**, invisible to every metric here, and fixing it **cost** 0.026 of evasion score. Both stated. |
| **Result 24** | The free tier called **60% of human writing AI**. Fixed by separating the reported verdict from the loop's target. |

Run `untell-audit` to re-check the claims in these documents against the code as it stands.

## Documentation

- **[Quick Start](quickstart.md)** — install and run in 60 seconds
- **[API Server](api-server.md)** — deploy the REST API
- **[What each function returns](result-shapes.md)** — the key that carries the answer, per entry point. They differ, and guessing wrong returns a plausible value rather than raising.
- **[Measured: the free evasion ceiling](free-ceiling-measured.md)** — the full log, 229 results
- **[Summary: the free-ceiling report](free-ceiling-report.md)** — the short version
- **[Humanizer comparison](humanizer-comparison.md)** — untell vs every free technique
- **[The 435-repo census](humanizer-census.md)** — what this field is actually made of
- **[Why this is the most rigorous open detector audit](why-best-open-repo.md)** — the argument, with its corrections
- **[Training runbook](free-training-runbook.md)** — the GPU path (RL against the ensemble)

### The measurement that changed what this project thinks it has

✗ **A false-positive rate is half a measurement, and the other half is worse.** Every number here
asks how often the detector is wrong about human text, never how often it is right about machine
text — because that needs an AI-labelled corpus and the usual ones require a download. A language
model wrote one instead, in the same register, where the label is provenance rather than annotation.

MEASURED at the shipped threshold, matched by length against pre-LLM ACL abstracts, the lite tier
flags **10.7%** of machine abstracts and **30.4%** of human ones over the matched 40–100 range,
intervals not overlapping — and flags human text more often in **every** band. Threshold-free,
**AUROC 0.3529**, bootstrap interval [0.2822, 0.4270], entirely below the 0.5 of a coin flip.

**On this register the ordering is reversed, not weak.** Both live features rank below 0.5 alone, so
no single term is at fault. Reproduce with `eval/detection_power.py`; the limits — one model, one
register, 56 machine documents — are in round seventy-six of the ledger.

**Why it happens, tested without any machine text at all.** The explanation offered was that these
features read how closely a document sounds like a standard academic abstract. That was inferred
from 56 documents; `eval/register_conformity.py` tests it on **6,841 pre-2022 ACL abstracts, every
one of them human**, where the more standard-sounding a document is the more AI it should score.
MEASURED: rho **+0.0586**, bootstrap CI [+0.0357, +0.0842], **all six length bands positive**.

⚠️ **And the same measurement bounds the explanation.** That rho is **0.34%** of the score's
variance — so register conformity is a real component of what the detector measures and nowhere near
all of it. It accounts for the *direction* of the inversion, not its *size*. The venue split, which
never looks at the text, orders the same way at the extremes but has no power across five classes.

### The literature this project argues from

- **[What untell should be](strategy-options.md)** — four candidate identities, three rejected on the
  evidence. Read this first if you want the argument rather than the sources.
- **[A literature map of AI-writing research](https://github.com/ssamba1/untell/blob/main/ai-writing-research.md)**
  — prevalence, homogenization, detection, fairness, attacks, watermarking, evaluation
- **[What we can build from it](research-to-build.md)** — the intersection with this codebase:
  datasets, metrics and arms, ranked
- **[Verification ledger](research-verification.md)** — every claim, the tier it was checked to, and
  the eight that changed when they were checked. **The corrections are the point of this document.**
- **Reproduce the survey yourself:** `python -m eval.litreview --download` re-derives the count the
  strategy rests on (186 volumes, 46,905 abstracts; 157 papers on evasion robustness against 13 on
  false positives and 13 on fairness — and 82 on multilingual detection, six times the fairness row
  for the same population). `--noise-floor` reports the error term on those counts: 13.2% of the
  corpus is a different detection problem, and removing all of it moves no share by more than 1.4
  points. **The shares matter, not the counts** — 24–28% against under 3%, at every filter setting
  swept — because they hold across three different detection filters; see round thirty of the ledger
- **And the filter's own recall is swept, not assumed:** `--window-sweep` varies the one number the
  survey rests on from 0 to 400 characters. The corpus runs 343–768 papers over that range and no
  topic share moves more than 4.3 points — but the finding is that **false positives saturates at 13
  papers early and 192 further detection papers enter behind it without one of them being about
  false positives**, while robustness nearly doubles. The gap is in the literature, not the filter
- **And the detector's own calibration is swept, not assumed.** `eval/constant_census.py` counts
  what nobody chose: **111 numeric constants, 41 with no stated reason** — and the five that decide
  the stdlib score were not constants at all, just literals inside an expression. Named, then swept
  by `eval/constant_sensitivity.py`: MEASURED over **30 settings, not one brings the AUROC above
  0.5**. **The inversion is not something a different calibration could have avoided.**
  Then `eval/constant_influence.py` perturbs **every** undefended constant rather than the ones that
  looked important: MEASURED, **0 of 35 move the published score**, against a positive control that
  moves 99.6% — so the zero is a result and not a broken harness. Six constants a perturbation
  cannot reach are listed rather than scored as zero.
- **And the topic patterns are swept too**, which is the sweep that could have broken this:
  `--topic-sweep` broadens the 13-paper false-positives row through four meaning-preserving rungs.
  MEASURED: it reaches **21 papers, so the honest row is 13–21**, and the ratio stays between
  **7.5x and 14.2x**, never near parity. The shipped pattern turns out to be the ladder's *most* discriminating
  rung and its *lowest* count, which is the opposite of a filter chosen to flatter a conclusion

## License

MIT — free to use, modify, and distribute.
