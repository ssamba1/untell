# The Detector Observatory

Dated, versioned report cards for AI-text detectors, measured on a human corpus whose provenance
is a git timestamp, and compared run to run for silent model changes.

## The corpus

[`corpus-python-peps.json`](corpus-python-peps.json) lists 80 prose documents from
[python/peps](https://github.com/python/peps) exactly as they stood at commit `02d07ca`
(2022-11-29), the last commit before ChatGPT's public release. They were written before any tool
that could have written them was available, so the "human" label rests on a date, not on trust.

The text is not stored here. The manifest names the commit and paths, the
[workflow](../../.github/workflows/observatory.yml) rebuilds the corpus from git on every run, and
each report card records a SHA-256 fingerprint of the corpus, so a reader can confirm a card was
measured on the same documents.

**Limits, stated plainly.** This is one register: technical proposals written by experienced,
mostly native-English programmers. The first 80 files in path order skew toward early PEPs. A low
false-positive rate here says nothing about student essays, non-native writers or short text —
which is where the published evidence says detectors fail. The corpus exists to catch *drift*
cheaply and reproducibly, not to stand in for those audits. Run `untell report-card` on your own
corpus for those (see [auditing.md](../auditing.md)).

## Report cards

| detector | date | false positives | null-edit flips | card |
|---|---|---|---|---|
| untell-local-lite | 2026-11-21 | 1.2% (1/80; 95% CI 0.2–6.7%) | 0/100 variants | [md](untell-local-lite/2026-11-21.md) · [json](untell-local-lite/2026-11-21.json) |

Compare with the same detector on HC3 forum answers: **30%** false positives
([Result 43](../free-ceiling-measured.md)). Same tool, same threshold, 25× the rate, because the
register changed. That gap is the single most important thing a false-positive rate needs
reported next to it.

## Seven commercial detectors, 2023 versions, by writer population

[Liang et al. (Patterns, 2023)](https://doi.org/10.1016/j.patter.2023.100779) published, with their
data, the score seven detectors gave every essay in early 2023
([MIT licence](https://github.com/Weixin-Liang/ChatGPT-Detector-Bias)). untell imports those
recorded scores through its `manual:` scorer and runs a report card per detector
([`untell/bench/liang2023.py`](../../untell/bench/liang2023.py)). False-positive rate on human essays,
flagged at score ≥ 0.5, with 95% intervals:

| detector | toefl-non-native | us-8th-grade | us-college-admissions | stanford-cs224n-abstracts | AUROC |
|---|---|---|---|---|---:|
| gptzero-2023 | **52%** (47/91; 42–62) | **0%** (0/88; 0–4) | **1%** (1/70; 0–8) | **1%** (1/139; 0–4) | 0.748 |
| originality-2023 | **76%** (69/91; 66–83) | **1%** (1/88; 0–6) | **4%** (3/70; 1–12) | **8%** (11/145; 4–13) | 0.640 |
| zerogpt-2023 | **53%** (48/91; 43–63) | **1%** (1/88; 0–6) | **3%** (2/70; 1–10) | **0%** (0/145; 0–3) | 0.570 |
| sapling-2023 | **68%** (62/91; 58–77) | **5%** (4/88; 2–11) | **1%** (1/70; 0–8) | — | 0.512 |
| crossplag-2023 | **52%** (47/91; 42–62) | **12%** (11/88; 7–21) | **0%** (0/70; 0–5) | **3%** (5/145; 1–8) | 0.582 |
| quillbot-2023 | **75%** (68/91; 65–83) | **9%** (8/88; 5–17) | **1%** (1/70; 0–8) | — | 0.585 |
| openai-roberta-2023 | **58%** (53/91; 48–68) | **9%** (8/88; 5–17) | **0%** (0/70; 0–5) | **1%** (2/145; 0–5) | 0.593 |

**Reproduction check.** Averaged across the seven detectors, untell's cards flag 62.0% of the TOEFL
essays; the paper reports 61.3%. The gap is within what duplicates (5 repeated essays) and a
threshold edge (several ZeroGPT scores sit at exactly 0.5) can explain.

**Two data problems the importer found and reports rather than hides:** the score files are not
always in the same order as the essays (CS224N's GPTZero file diverges from position 3), so scores
are aligned by text; and six GPTZero scores were recorded for the placeholder "Project summaries
unavailable" rather than for an abstract, so those six abstracts are unscored.

**What this is and is not.** These are the 2023 versions, before every vendor's later model
changes. They are a baseline: re-scoring the same essays against today's versions and running
`untell drift` against [these cards](liang-2023/cards/) measures what changed. Per-document scores
are in [`liang-2023/scores/`](liang-2023/scores/); the essays themselves are not stored here and are
rebuilt from the authors' repository by `python -m untell.bench.liang2023 <clone>`.

## untell's own full ensemble, audited by itself (2026-11-22)

The same report card, pointed at untell's own `local:full` verdict (five local models; flagged
when the ensemble maximum reaches the shipped 0.30 threshold):

| corpus | false positives on human writing | card |
|---|---|---|
| Liang et al. essays (394 human) | **57.4%** (226/394; 95% CI 52.4–62.1%) | [md](untell-local-full/2026-11-22-liang2023.md) |
| — TOEFL, non-native writers | **92.3%** (84/91) | |
| — US 8th grade | 40.9% (36/88) | |
| — US college admissions | 62.9% (44/70) | |
| — Stanford CS224N abstracts | 42.8% (62/145) | |
| 80 pre-2022 PEPs | **65.0%** (52/80; 95% CI 54.1–74.5%) | [md](untell-local-full/2026-11-22-peps.md) |

AUROC against the 352 GPT-3 texts is 0.817, but recall is **0%** at every capped false-positive
rate (0.5%, 1%, 5%): no threshold flags any AI text without flagging more than 5% of these humans.
Under formatting-only edits, 6 of 55 variants (10.9%) still changed the verdict, with untell's
input normalisation on.

**What this says.** untell's own verdict, on the full tier, is not fit to be evidence about anyone,
and flags non-native writers at more than twice the rate of US students. The previously published
figure (5 of 30 HC3 forum answers, 17%) described one corpus. Taking the maximum of five detectors
against a 0.30 bar makes the most trigger-happy member decide every verdict. This card is why the
evidence tools never use untell's own verdict as a stand-in for a commercial detector, and why
recalibrating it is on the [roadmap](../../ROADMAP.md).

**Fixed the same day** — see [calibration.md](calibration.md): refitted on 268 held-out pre-2022
human documents, the verdict now flags 24% of TOEFL essays, 2.3% of US 8th-grade essays and 0% of
PEPs, at the cost of AI recall falling from 91% to 46%. Cards for the calibrated verdict:
[Liang](untell-local-full/2026-11-22-liang2023-calibrated.md) ·
[PEPs](untell-local-full/2026-11-22-peps-calibrated.md).

## One trailing space

On short text, a single trailing space reversed every "AI" verdict `hc3_roberta` gave in this
corpus — human and AI text alike. [Write-up and data](trailing-space.md).

## Live measurements

Commercial detectors' current versions appear here once their API keys are configured as
repository secrets and the workflow is run with `publish`. None has been measured live yet.
