<div align="center">

<a href="https://ssamba1.github.io/untell/"><img src="docs/og.png" alt="untell — an AI-detector auditing toolkit: measures detector false-positive rates on human writing and tests how stable a verdict is under meaning-preserving edits" width="820"></a>

# untell — an AI-detector auditing toolkit

### Measure whether an AI detector can be trusted: what it does to writing a human actually wrote, how stable its verdict is, and what happens to that verdict under meaning-preserving edits.

A **detector-in-the-loop measurement harness**, shipped as a **Claude Code skill** *and* a Python CLI.
Free. Open source. Its headline result is a negative one, and it says so.

[![CI](https://github.com/ssamba1/untell/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/untell/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-8A2BE2.svg)](#-quick-start)
[![Zero-dependency lite tier](https://img.shields.io/badge/install-zero--dependency-brightgreen.svg)](#tiers)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)
[![Live site](https://img.shields.io/badge/site-ssamba1.github.io%2Funtell-2ea44f.svg)](https://ssamba1.github.io/untell/)
[![good first issues](https://img.shields.io/github/issues/ssamba1/untell/good%20first%20issue.svg?label=good%20first%20issues&color=7057ff)](https://github.com/ssamba1/untell/labels/good%20first%20issue)

**What this is for: finding out how much a detector's verdict is worth.** Detectors are increasingly
used to make consequential accusations, and this repository exists to measure how well that holds up.
Measured here, at each tool's own shipped threshold: the full local ensemble flags **17% of genuine
human writing** (5 of 30 real HC3 answers — 95% CI **7.3%–33.6%**); the lite tier flagged **30%** on
conversational prose; one bundled detector flags **6 of 8** human documents (CI **40.9%–92.9%**) and
another flags **89%** of them — that second one was demoted out of its tier for it. Before a
calibration fix, the ensemble flagged **95% of human documents**.

**The strongest of these numbers is the newest, because its ground truth cannot be argued with.**
Scored against ACL abstracts published through 2021 — before ChatGPT, so every flag is a false
positive by construction — the lite tier flags **19.47%** of them (**all n = 6,810**, CI
**18.55%–20.43%**), and **30.0%** of the same text truncated to 50 words or fewer (CI
**22.5%–38.7%**). Reproduce with `python -m eval.pre_llm_fpr --download --n 0` (`--n 0` scores the whole corpus; the default is 100).

⚠️ **That rate is quoted for documents of 60 words or more, and the floor is load-bearing.** The same
probe returns 22.0% at a 30-word floor and **14.3% at 150** — an 8.4-point swing from a parameter
nobody chose deliberately. There is no such thing as *the* false-positive rate; there is one per
corpus definition, and every report now carries the definition that produced it.

✗ **And a false-positive rate is half a measurement. The other half is worse.** Every number above
asks how often the detector is wrong about human text and never how often it is right about machine
text — because that needs an AI-labelled corpus, and the ones everyone uses require a download. A
language model wrote one instead: 70 abstracts in the same register, where the label is provenance
rather than annotation.

MEASURED at the shipped threshold, matched by length against those same pre-LLM abstracts:

| band (words) | machine flagged | human flagged |
|---|---|---|
| 40–60 | **9.7%** | **64.5%** |
| 60–100 | **12.0%** | **28.7%** |
| 100+ | **7.1%** | **18.6%** |
| **40–100 pooled** | **10.7%** [5.0%, 21.5%] | **30.4%** [27.0%, 34.1%] |

**In every band it flags human text more often than machine text**, and over the matched range the
intervals do not overlap. Threshold-free, **AUROC is 0.3529** with a bootstrap interval of
[0.2822, 0.4270] — entirely below the 0.5 of a coin flip.

**On this register the lite tier is not a weak detector. Its ordering is reversed.** Both of its live
features are below 0.5 ranked alone, so there is no single bad term to remove: they measure how much
a document reads like a standard academic abstract, and in this corpus that is what the human writing
is. Reproduce with `eval/detection_power.py`.

⚠️ One model, one register, 56 machine documents in the matched range. The human arm is 634 real
abstracts, so the human rate is solid; the machine rate is not precise. What the interval does rule
out is that the two are the right way round.

**And there is an answer to the false-positive half, if not to that one.** `untell/calibrate.py`
derives a threshold with a *bounded* false-positive rate from a human-only corpus. MEASURED on all
6,810 documents, the shipped 0.45 flags **19.47%** and the conformal threshold at α = 0.05 is
**0.5401**. A tenth of a threshold is the difference between one human document in five being
accused and one in twenty.

⚠️ **The bound is marginal, not conditional, and that distinction is the whole story.** Conformal
prediction promises the false-positive rate is at most α *averaged over calibration sets*.
Conditional on the one set you actually have, the realised rate is Beta-distributed with mean α — so
it lands **above α about half the time**, at every sample size. `coverage_spread()` reports that band
and `calibrate()` now returns it, because a caller reading a single calibration as a guarantee is
reading it wrong.

**More data does not fix this; it was never the problem.** Going from 150 to 6,810 calibration
documents leaves the chance of exceeding α at ~50%. What it buys is width: the realised rate's
p5–p95 band narrows from **2.2%–7.7%** to **4.6%–5.4%**. **Buy data for precision, not for safety.**

⚠️ **Every rate above is a proportion with a sample size, and the intervals are wide.** That is the
point rather than a caveat: this repo's own measurements move by more than 15 points between n = 20
and n = 60, so a bare detector percentage — ours, or a vendor's — is not a fact about a detector.

The rewriting loop is the *probe*, not the product: it is how you test whether a verdict survives
meaning-preserving editing. The answer it produced is a negative one — the loop moves the detectors it
optimises against, and **does not move a detector it has never seen** (4/10 flagged, every seed, every
objective, every rewriter).

⚠️ **Read that as a fact about this loop, not about evasion.** Stronger methods do transfer, and the
peer-reviewed literature is clear about it: RAFT compromises every detector it tests by up to 99% and
is [transferable across source models](https://aclanthology.org/2024.emnlp-main.939/); MASH reaches
[92% attack success rate black-box across five detectors](https://aclanthology.org/2026.findings-acl.1487/);
evasive soft prompts [transfer from one model to another](https://aclanthology.org/2023.findings-emnlp.94/).
Non-transfer here is the ceiling of a CPU-only black-box loop with no training — it is not evidence
that detectors are safe from transfer attacks, and it should never be quoted as if it were.
[What the measurements establish →](#-the-measured-free-ceiling)

</div>

---

## Intended use

Built for **detector evaluation and reliability research**: measuring false-positive rates on human
writing, auditing a detector before anyone relies on it, testing robustness claims, and stripping
hidden-unicode carriers (zero-width characters, bidi overrides — the Trojan Source class) from text
before it is read or scored.

**Not built for, and not supported for, misrepresenting authorship** — including submitting
machine-written work as your own where that is prohibited. If that is what you are here for, the
measurements below are the wrong news anyway: the evasion this tool achieves is against its own local
proxies, it does not transfer to a detector it has not seen, and it has never been shown to move a
commercial checker.

The honest summary of the capability is in [Honest caveats](#honest-caveats), and every number is
reproducible from [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md).

## TL;DR

**An AI detector gives you a number. This tells you what that number is worth.**

Point it at a detector and it will measure three things: how often that detector calls human writing
machine-generated, whether its verdict is stable across seeds and paraphrases, and whether a score
you can move is a score that means anything. It does the last one by putting the detector *in a
closed loop* — score, edit under a meaning gate, re-score — because a verdict that collapses under
meaning-preserving editing was never measuring authorship.

The loop is a measurement instrument, and it produced a negative result about itself: it reliably
moves the detectors it optimises against and does not move one it has never seen.

That iterative, detector-feedback approach is the strongest *training-free* technique in the published
literature ([arXiv 2506.07001](https://arxiv.org/abs/2506.07001): −87.88% average TPR@1%FPR, transfers
across neural, watermark-based and zero-shot detectors). A 2026-08-05 sweep of 435 open-source repos
found **44 that use a detector loop at inference time** — but **none that combines it with a mechanical
meaning gate, citation preservation, and tests in an installable package**
([census](docs/humanizer-census.md)). This repo does.

> The strongest of those 44 is [`chengez/Adversarial-Paraphrasing`](https://github.com/chengez/Adversarial-Paraphrasing),
> which does per-token guidance (stronger than our per-candidate loop). It is research code: no
> meaning gate inside the pipeline (quality is a post-hoc GPT-4o evaluation for the paper, which reports
> "mostly a slight degradation in text quality" rather than preserved meaning), no numeral or citation
> preservation, no installable package, no tests. Its bypass numbers are far stronger than anything
> measured here. See [why-best-open-repo.md](docs/why-best-open-repo.md) for the full comparison —
> including the honest note that packaging its mechanism behind these meaning gates would beat this repo.
>
> On the **commercial** side: those products are closed, so "no commercial tool does
> it" is not something anyone can verify — what is true is that none of them *documents* a
> detector-feedback loop. StealthGPT describes model-level training, HumanizerAI offers user-driven
> re-runs (iteration by the person, not by a detector). Independent 2026 testing also has StealthGPT
> still failing Turnitin (86% AI), Originality.ai (100%) and GPTZero (48%) — consistent with the
> caveat below that nobody, paid or free, reliably beats that class of detector.

> ```
> Measured live:  a formulaic AI paragraph went  100% → 0% AI on ZeroGPT  in one loop.
>                 a stickier one went             100% → 35% → 0%          once the loop
>                 used per-sentence feedback to target only the flagged spans.
> ```
>
> Two paragraphs against one live checker — a demonstration, not a rate. Real ChatGPT output is
> harder: against the local ensemble it ends at **0.86, still flagged**
> ([Result 11](docs/free-ceiling-measured.md)). Read that before treating the line above as typical.

```bash
# Zero dependencies. Works right now, in Claude Code:
/untell  <paste your AI-sounding text or a file path>
```

---

## ⚡ Quick start

**Web UI:** [`docs/demo.html`](docs/demo.html) is a front-end for the REST API — **not** an
in-browser detector. Start the server, then open it pointed at that server:

```bash
pip install -e ".[server]" && untell-server     # then open docs/demo.html?api=http://localhost:8000
```

Your text is POSTed to that API. Run it locally and it never leaves your machine; point `?api=` at
a remote host and it does.

**Install the Claude Code skill — one line:**

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/ssamba1/untell/main/install.sh | sh
# Windows PowerShell
irm https://raw.githubusercontent.com/ssamba1/untell/main/install.ps1 | iex
```

Then in Claude Code: **`/untell <your text or a file path>`**. Claude is the rewriter; the bundled scripts
score the text and lock your facts. Zero dependencies (lite tier).

**Or install as a Claude Code plugin** (marketplace):

```text
/plugin marketplace add ssamba1/untell
/plugin install untell@untell
```

**As a Python package** (`pip install untell` lands with the first PyPI release — from source today):

```bash
git clone https://github.com/ssamba1/untell && cd untell
pip install -e ".[full]"                          # real detector ensemble on CPU

# One unified command (`untell --help` lists them all; bare `untell` runs the guided demo):
untell humanize "Your AI-sounding paragraph here."   # the closed loop (alias: loop); default $0 composite
untell humanize "text" --rewriter surgical           # NO key needed — runs the loop for $0
untell humanize "text" --rewriter ensemble           # strongest free path: composite + mt + neural, pick best (.[full])
untell score "text" --tier full --threshold 0.3      # just score it
untell tells "text"                                  # count the AI writing tells (naturalness)
untell verify --file draft.txt                       # honest pass/fail per detector
untell compare                                       # head-to-head vs free-humanizer techniques
untell ceiling --rewriter composite --best-of 3 --repeats 3  # measure free evasion (with error bars)

# Shipped and, until now, undocumented here (waves 6-7):
untell humanize "text" --inspect                     # per-sentence: rewritten or not, and WHICH meaning gate rejected each draft
untell humanize "text" --jsonl                       # one JSON object per paragraph, flushed as it completes (long documents)
untell humanize "text" --html report.html            # self-contained report: locked spans marked, per-sentence scores, no network
untell humanize "text" --manifest run.json           # sha256 in/out + seed + rewriter + an honest determinism class
untell humanize "text" --timings                     # per-phase cost breakdown

# (every subcommand is also a standalone `untell-<name>` script, e.g. `untell-loop`, `untell-tells`)
```

> **How far does free actually go?** Three numbers, because one of them alone would mislead you.
>
> | measured on | before | after | still flagged |
> |---|---|---|---|
> | built-in demo sample (3 paragraphs, ~36 words each) | 0.86 | **0.15 ± 0.04** | 100% → **0%** |
> | real AI text (RAID, n=40, 3 repeats) | 0.629 | **0.287 ± 0.003** | 83% → **28%** |
> | **a detector the loop never optimised against** (RADAR, n=10 × 3 seeds) | 0.722 | **0.44–0.50** | 70% → **40%, every seed** |
>
> The first row is the one most tools would print. It is the easiest corpus in the repository, and
> this project's own measurement log says so. The third row is the one that matters: **the in-sample
> flagged count moves freely (10/10 → 4, 2, 3 across seeds) and the held-out count does not move at
> all (4/10 in every seed, every selection objective, every rewriter tried).** A second held-out
> control flipped zero verdicts in 60 rewrites.
>
> So: the loop reliably moves the detectors it optimises against, and has **not been shown** to move
> a detector it does not. That is the honest state of the art here, it is not the claim we set out to
> make, and it is measured rather than assumed — see Results 163, 228 and 229. Meaning is held by an
> NLI gate plus a predicate-argument veto. An earlier draft of this line quoted a
> tighter figure from three repeats that did not replicate — see the note under the table. The
> largest correction was the detector itself: the
> one detector present at every tier was itself anti-correlated and saturating, so every previous
> number on this page had been measured through it. An earlier
> version of this README claimed the loop was "powerless against content-locked detectors" — that was
> measured with a single rewrite draw and a miscalibrated detector, and **it did not survive
> re-measurement**. Full numbers, method, superseded claims and honest limits:
> [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md)
> (the report: [`docs/free-ceiling-report.md`](docs/free-ceiling-report.md)).

<details>
<summary>Manual / MCP install</summary>

```bash
# Manual skill copy:
git clone https://github.com/ssamba1/untell && cp -r untell/untell ~/.claude/skills/untell

# MCP server (Claude Desktop & any MCP client) — exposes score/sentences/untell/verify/scrub as tools:
pip install -e ".[mcp]" && untell-mcp     # (pip install "untell[mcp]" once on PyPI)

# Feature extras (not required for the core loop):
pip install -e ".[docs]"     # .docx / .pdf file input (python-docx, pypdf) — needed for --file *.docx / *.pdf
pip install -e ".[rich]"     # coloured terminal output (rich) — auto-detected; falls back to plain text without it
pip install -e ".[quality]"  # higher-fidelity quality gate (BERTScore-F1 backend, vs. embedding/token-overlap)
```
</details>

---

## How it works

```
/untell <text|file>
  scrub hidden watermark characters — zero-width, tag, control, blank-rendering and
    homoglyph carriers, plus orphaned ZWJ / variation selectors / bidi marks (kept where
    emoji or right-to-left text makes them load-bearing)   (attacks/unicode_tricks.py)
  preserve-lock citations / numbers / quotes / URLs / entities / code / paths /
    CLI flags / env vars   (scripts/preserve.py)
    — scrub first, on purpose: locking first would capture any hidden characters inside a
      locked span into the mapping, and the final restore would put them straight back
  repeat up to N times:
    score = scripts/score.py <text>          # ensemble of detectors -> {detector: P(AI), max}
    sentences = scripts/sentences.py <text>  # which sentences read as AI (target only these)
    meaning = NLI gate: no contradiction AND bidirectional entailment  (scripts/entailment.py)
              + predicate-argument check: roles not permuted            (scripts/roles.py)
              + quantity check: every number survives                   (scripts/numerals.py)
              + certainty check: no hedge dropped, no claim added       (scripts/hedges.py)
              the last two are stdlib-only and run even with no ML installed
    if max(score) < threshold and sim ok: stop
    Claude rewrites the flagged sentences using the per-detector scores as feedback
      (raise burstiness + perplexity, vary sentence architecture, kill clichés/formulaic
       transitions, diversify vocab — while keeping meaning + every locked span)
  restore locked spans -> humanized text + a before/after detector table
```

Three design choices make it work where blind paraphrasers fail:

1. **It drives the `max` across detectors, not the average** — a rewrite only wins when the *hardest*
   detector is satisfied (genuine multi-detector evasion).
2. **Every rewrite is gated on meaning by an NLI check, not cosine similarity** *(when the NLI
   stack is installed — see the scope note at the end of this item)* — it *refuses* the
   meaning-mangling that wrecks other tools' output. Cosine similarity alone was measured to fail in
   **both** directions: it passed rewrites that INVERT the source ("runs faster" → "runs slower"
   scores 0.974 against a 0.76 bar) while rejecting 6 of 8 faithful formal→casual rewrites, because
   it penalises register change — exactly what humanizing does. The gate requires no
   contradiction *and* bidirectional entailment: 7/8 faithful rewrites admitted, **0/11**
   meaning-lost ones, versus 2/8 and 4/11 for the similarity bar it replaced.

   NLI has a blind spot of its own, so a **predicate-argument check** sits behind it. Rewrites that
   keep every content word and only permute the roles — "the company sued the regulator" → "the
   regulator sued the company" — score 0.99 entailment, because as bags of tokens they are identical.
   Word order cannot separate those from a faithful voice change, so `scripts/roles.py` compares
   parsed (subject, verb, object) structure with the passive normalised into active order:
   **9/9 role permutations caught, 0/13 faithful rewrites falsely vetoed** by that check. End to end
   the gate admits **0 of 25** meaning-changing rewrites — role swaps, negation flips, altered
   quantities, dropped hedges, association reported as causation, and dropped attribution.

   The full gate is a conjunction — similarity floor, contradiction, bidirectional entailment,
   predicate-argument structure, retained quantities, retained claim strength. Measured on the
   faithful set it now rejects **0 of 13**, and on **~70 candidates the composite rewriter actually
   produced** (25 texts × 3 runs, since the rewriter is randomised) it passes **96–100%**, mean 99%
   across runs. The only rejection left is the predicate-argument check, at ~1%.

   ⚠️ **Scope: the NLI and role checks need `torch` + `transformers` (the `.[full]` extra).** On a
   zero-dependency install `available()` returns False and the gate falls back to the similarity bar
   alone — the metric this very bullet describes as passing inversions. MEASURED on its own example,
   "The new build runs faster than the old one." → "...runs slower...", similarity 0.983 against the
   0.76 bar: **rejected with NLI, ADMITTED without it.** The mechanical checks (retained quantities,
   retained claim strength) run on every path; contradiction, bidirectional entailment and
   predicate-argument structure do not. Every loop result now reports `meaning_gate`
   (`"nli"` / `"similarity-only (NLI unavailable)"` / `"similarity-only (veto disabled)"`) and the
   CLI warns when the veto did not run, so a passing verdict says which gate produced it.

   ⚠️ **Scope: every figure in this bullet is measured on sentence-length examples**, and that used
   to be the only length at which they held. Both model-backed gates truncate their input, so until
   2026-08-09 each was scoring the front of a long document and reporting a verdict about all of it
   — a negation 143 words in scored 0.0179, the contradiction value for two *identical* strings, and
   a whole sentence replaced 280 words in scored a similarity of 1.0000. Not a mis-set threshold:
   the changed text was never fed to the model. Both gates now score aligned chunks and take the
   worst, and `tests/test_gates_read_the_whole_document.py` fails if any gate's verdict depends on
   where in the document the change sits. `roles`, `hedges` and `numerals` never had the problem.

   One limit survives the fix, on the free path only. `token_overlap` is the sole meaning gate on a
   zero-dependency install, and it cannot detect a single destroyed sentence inside a paragraph at
   *any* chunk size — the granularity that catches it (20 words, score 0.10) also rejects 3 of 25
   genuine rewrites, because Dice cannot tell "reworded heavily" from "replaced entirely". So the
   free tier detects meaning **drift across a document** and not **destruction of one sentence**;
   the same case scores 0.98 contradiction under `.[full]`. Measured in
   [Result 36](docs/free-ceiling-measured.md).

   Both numbers moved because the claim-strength check was over-strict in ways that had nothing to
   do with claim strength: "due to", "will", "set to" and "going to" were classed as *intention*
   hedges, so every rewrite of "the delay was due to X" or "this function will return X" was vetoed;
   "hint" was missing from the *evidential* class, so swapping one weak hedge for another read as
   dropping it; and a negator more than 30 characters from its verb was invisible, so a rewrite that
   explicitly *denied* causation was vetoed for asserting it. Tightening that same pass closed a
   real leak in the other direction — "critics allege the firm misled investors" → "the firm misled
   investors" cleared every check, because dropping an attribution does not contradict the source,
   it just asserts more. The quantities check moved too: it read only DIGITS, so "three sites took
   part" → "five sites took part" passed, and reading spelled-out numbers on both sides closed that
   while removing the last of its false vetoes on real candidates.
3. **Citations, numbers, quotes, URLs and named entities are locked byte-for-byte** via preserve-lock, so
   your APA/IEEE/MLA references and your facts survive the rewrite untouched.

---

## 📉 The measured free ceiling

*How far does $0 actually get you? We measured it.* Most humanizers sell a fantasy ("99% human, undetectable!"). We did the opposite: we **measured** the
real ceiling of a free, training-free loop and published the numbers, the method, and the limits.
The published state of the art (92–97.6% attack success) **needs GPU fine-tuning**; the literature had
**no data point** for the inference-only regime this tool runs in. With a working local detector stack we
produced it — see **[`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md)** (research:
**[`docs/free-ceiling-report.md`](docs/free-ceiling-report.md)**).

Reproduce it yourself, no API key, on CPU:

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --rewriter composite --tier full --best-of 3 --max-iters 2 --repeats 3
```

| Free, no-key rewrite vs the local open ensemble (3 repeats = 9 loop runs) | before | after |
|---|---|---|
| flagged rate (max P(AI) ≥ 0.30) | 1.00 | **0.00** (`--best-of 3`, 27 loop runs) |
| mean max P(AI) | 0.86 | **0.15 ± 0.04** (`--repeats 9`) |
| meaning similarity (cosine; the gate is NLI + roles) | — | **0.93 mean, 0.87 worst** |

Per detector, before → after: `hc3_roberta` 0.73 → 0.06, `roberta_openai` 0.52 → 0.08,
`perplexity_burstiness` 0.41 → 0.12, `fast_detectgpt` 0.21 → 0.03.

> ⚠️ **Read that table with its corpus.** Those are `untell-ceiling`'s **built-in sample: three
> hand-written paragraphs, mean 36 words.** They read as AI, and they are measurably *easier* than
> real AI output — they start at 0.86 where actual ChatGPT answers start at **1.00**. Holding length
> constant on HC3 pairs (tier=full, best-of-3):
>
> | corpus | words | before | after | still flagged |
> |---|---|---|---|---|
> | built-in sample | 37 | 0.86 | **0.23** | **0%** |
> | HC3 ChatGPT answers, cut to 36w | 36 | 1.00 | **0.63** | **50%** |
> | HC3 ChatGPT answers, full length | 186 | 1.00 | **0.76** | **83%** |
>
> The gap is the **corpus, not the length** — at identical length the built-in sample lands three
> times lower. Length then adds on top, because detectors take the `max` over windows and the loop
> has to clear *every* window: a separate sweep at 348–1601 words ended at 1.00, still flagged.
>
> So the table above measures the loop's **mechanics on short, easy text** — it is a demo, not a
> claim about real AI documents.

**The number against real AI text** — 8 HC3 ChatGPT answers, mean 195 words, 24 loop runs:

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 8 --rewriter composite --tier full --best-of 3 --max-iters 5 --repeats 3
```

| | built-in sample | **real HC3 answers** |
|---|---|---|
| mean max P(AI) | 0.86 → 0.15 ± 0.04 | 1.00 → **0.998 ± 0.001** |
| flagged rate | 1.00 → 0.00 | 1.00 → **1.00** |
| meaning similarity | 0.93 / 0.87 worst | 0.99 / 0.97 worst |

Per detector: `roberta_openai` 0.99 → **0.64**, `fast_detectgpt` 0.64 → **0.46**,
`perplexity_burstiness` 0.62 → **0.59**, **`hc3_roberta` 1.00 → 0.999 (does not move at all)**.

> **This row was corrected on 2026-08-08 and the previous figures were better than reality.** It
> used to read 0.86 post, with `roberta_openai` 0.99 → 0.09 and `hc3_roberta` 1.00 → 0.81. Re-running
> the command above reproduces none of that. Checked against a worktree at the commit *before* that
> day's rewriting work, in case it was a regression: the baseline gives `roberta_openai` → 0.83 and
> `hc3_roberta` → 0.999, so the current code is **better** on this corpus, not worse, and the old
> numbers describe a state neither commit produces. They were stale, and nothing was re-running
> them — which is why `untell-audit` now exists.

Not one sample cleared, and the spread across three repeats is 0.001 — the loop hits the same wall
every run. It is not a lack of effort: **89–93% of tokens are rewritten**, and `roberta_openai`
going to 0.09 on that same text proves the rewriter is working. `hc3_roberta` measures *subject
matter*, and a meaning-preserving rewrite is not allowed to change that. Similarity stays at 0.98
for the same reason — it is a content metric too.

So the honest summary for **this rewriter**: style detectors fall, the content detector does not,
and one unclearable passage flags the whole document because the ensemble aggregates with `max`.
Measured per text, the spread is between texts rather than along length — a 207-word paragraph
reaches 0.40 while a 199-word one never leaves 0.999 — so a longer document is worse mainly because
it is another chance to contain a text the loop cannot clear.

> **`hc3_roberta` is not immovable — that was a property of `composite`, the default.** The whole
> table above is one rewriter, and swapping it changes the headline. Same six HC3 answers, same
> command, `pre` identical at 0.9994 ([Result 13](docs/free-ceiling-measured.md)):
>
> Replicated at `--repeats 3` (36 loop runs) so the gap can be told from the noise — the single-run
> figures below it were within one run's spread of each other:
>
> | n=6, `--repeats 3` | `composite` | `neural` |
> |---|---|---|
> | mean max P(AI) | 0.999 → **0.778 ± 0.020** | 0.999 → **0.380 ± 0.079** |
> | flagged rate | 1.00 → **0.94** | 1.00 → **0.28** |
> | **`hc3_roberta`** | 1.00 → **0.710** | 1.00 → **0.248** |
> | meaning similarity | 0.978 / 0.921 worst | 0.932 / 0.831 worst |
>
> **What DOES reproduce, measured 2026-08-12 at commit `9545d62`.** Same rewriter, same settings,
> the other corpus — RAID paper abstracts, which no detector in the ensemble was trained on:
>
> | RAID, n=6, `--repeats 3`, `composite` | before | after |
> |---|---|---|
> | flagged rate | 0.83 | **0.28** |
> | mean max P(AI) | 0.629 | **0.287 ± 0.003** |
> | `roberta_openai` | 0.333 | **0.0005** |
> | `hc3_roberta` | 0.350 | **0.105** |
> | meaning similarity | — | 0.979 mean / 0.939 worst |
>
> Every detector moves, the three runs agree to ±0.003, and 72% of documents end unflagged.
>
> **Read the two corpora together or neither is honest.** RAID starts easier — 0.83 flagged at mean
> max 0.629, against HC3's 1.00 at 0.9997 — so this is not "the loop does better", it is a different
> starting point. And HC3 is the harder case for a specific, nameable reason: `hc3_roberta` is
> fine-tuned on HC3, so on that corpus the ensemble contains a detector for which the text is
> in-distribution and the max cannot move. Quoting RAID alone would be the same error this file
> already documents about the built-in sample.
>
> **RE-MEASURED 2026-08-12 and the composite column no longer reproduces.** The same command on the
> same six answers now returns mean max **0.9994**, flagged **1.00**, with `hc3_roberta`
> **0.9992 → 0.9992** — unmoved, where this table has it dropping to 0.710. The figures above were
> produced before `structural.py`'s draws were seeded; that commit's own message records outputs
> depending on what the process had rewritten earlier, so the old numbers came from a stream that no
> longer exists. One alternative was tested and **refuted**: disabling the deletion guard added the
> same week changes nothing, byte for byte (0.9995 / 1.00 / 0.9992 both arms). Treat the composite
> column as unreproduced pending a re-derivation.
>
> The `neural` column does not reproduce either. A full n=6 `--repeats 3` run exceeded a
> 90-minute budget without finishing (~950s per text by this script's own figures, 18 runs),
> so this is **n=2, `--repeats 1`** and is quoted as a direction rather than a rate: mean max
> **0.9958**, flagged **1.00**, `hc3_roberta` **0.9992 → 0.9955**, similarity 0.884 mean /
> 0.767 worst — against a published 0.380 and flagged 0.28. Two detectors do move well
> (`fast_detectgpt` 0.646 → 0.300, `perplexity_burstiness` 0.605 → 0.420); the max does not.
>
> **72% of real AI paragraphs clear** where composite cleared almost none, and the gap (0.398)
> is twice the worst within-rewriter spread (0.191), so it is a finding rather than a draw.
> `neural` is **4× as variable** as composite, though — a single run of it can land at 0.485,
> most of the way back — so quote it with repeats or not at all. It is **not free**: meaning drops, `neural`
> needs the `.[full]` extra (~850MB T5) and several times the wall-clock, and it is not uniformly
> better per detector — it loses on `roberta_openai` (0.30 vs 0.12) while winning the `max` that
> decides the verdict. The default is unchanged; a run that ends flagged now prints the trade so
> you can choose. Note also that `max` is an **alias** for `ensemble`, so a table listing both is
> listing one method twice.

Two obvious-looking fixes were measured and **refuted**: exiting early when the loop stalls (it
would have cost the improvable text more than half its gain), and clearing each paragraph separately
before reassembling (no difference — the paragraphs do not clear either). Full method, the falsified
claims and the corpus caveat: [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md)
(Results 10–13). Every result now carries the `corpus` **and the `rewriter`** it came from — the
missing rewriter field is exactly why the wall above was read as a property of the free tier — and
a built-in-sample run says so in its output.

¹ Figures marked `--best-of 8` predate the detector calibration fixes and are indicative only. The
"after" number improved (0.26 → 0.18, flagged 0.15 → 0.07) when two detectors were recalibrated —
not because the rewriter got better, but because the detectors had been over-scoring *everything*,
including the loop's own output. The "before" number barely moved (0.859 → 0.859): AI text is
flagged just as confidently. See the note on false-positive rates below.

**Use `--repeats 9`, not 3.** Two independent 3-repeat runs of the identical command gave
0.247 ± 0.015 (flagged 0.00) and 0.330 ± 0.118 (flagged 0.44) — one contained a single 0.496 draw
that moved its mean by 0.08. A low stdev across three repeats does not mean the estimate is stable.
The instability is the rewriter's randomness, and repeats average it out; the current 9-repeat
figure is **0.15 ± 0.04, flagged 0.00** over 27 loop runs. See
[`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md).

More draws buy **reliability, not a lower average**: 3 → 8 barely moves the mean but halves the
run-to-run spread and clears every sample. Meaning is measured alongside, so a good evasion number
can't hide a mangled rewrite.

Per-detector, before → after (9 repeats, 27 loop runs, post-recalibration):

| detector | before | after |
|---|---|---|
| `perplexity_burstiness` | 0.41 | **0.14** |
| `roberta_openai` | 0.52 | **0.11** |
| `hc3_roberta` (content/genre) | 0.73 | **0.05** |
| `fast_detectgpt` (curvature) | 0.21 | **0.02** |

**The detectors were flagging human writing, and AUROC could not see it.** Measured on 40 HC3 pairs
at the default 0.30 threshold, before the fixes in this section: `fast_detectgpt` scored human prose
at a mean of 0.510 and flagged **92%** of it; `perplexity_burstiness` flagged 32%. The ensemble
aggregates with `max`, so the full tier flagged **95% of human documents** — it would have told
almost any writer their own work was machine-generated, and the loop would then have rewritten it.

Both were pure calibration: each logistic had its midpoint at the human mean or at the class
midpoint rather than where the threshold needed it. AUROC was 0.999+ throughout and never moved by
more than 0.001, which is why the detector audit reported both as healthy. Refit on 40 pairs and
checked on 60 unseen ones:

| | human mean | human flagged | AI caught |
|---|---|---|---|
| full ensemble, before | 0.520 | 95% | 100% |
| full ensemble, after | 0.164 | **12%** | 100% |
| lite, before | 0.244 | 32% | 100% |
| lite, after | 0.136 | **5%** | 100% |

`untell-detector-audit` now reports false-positive rate alongside AUROC and has a `MISCALIBRATED`
verdict, because a threshold-free metric cannot catch this class of bug on its own.

Three further findings, all measured, and one of them overturned this project's own earlier conclusion:

- **The "content tell" was mostly a *selection* limit — on this corpus.** An earlier version of
  this table (measured with a single rewrite draw) showed HC3-RoBERTa stuck at 0.73 → 0.67 and
  concluded no meaning-preserving rewrite could move it. With **best-of-3 selection against the tier
  you actually score on**, it drops to **0.04**. The lever was never a cleverer rewriter — it was
  choosing among several drafts against the real signal.
  **Scope correction:** that holds on the built-in sample. On real HC3 answers the same selection
  leaves `hc3_roberta` at **1.00 → 0.999 — it does not move at all**, and `roberta_openai` at
  0.99 → 0.64. So selection is a real lever on easy text and content is still the wall on real text.
  Both results, and the caveat that `hc3_roberta` is *trained on* HC3, are in
  [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md) (Results 10–11).
  <br>**These figures used to read 0.81 and 0.09 here, contradicting the corrected row above in
  this same file.** The row was re-measured on 2026-08-08 and this bullet was missed. Re-measured
  again 2026-08-11 over 6 HC3 answers: `hc3_roberta` lands at 0.9992 and never leaves 0.999 on any
  of them, which is what the corrected row says. Three of the five default detectors saturate on
  this corpus — `mage` 1.0000 on 6/6, `hc3_roberta` 0.9992–0.9993 on 6/6, `roberta_openai` ≥0.999
  on 5/6 — so no rewriter can move `max` here, and the ceiling figures in the linked document are
  historical rather than current.
- **The one "immovable" detector turned out to be broken — and once fixed, it moves.**
  `fast_detectgpt` never budged in any configuration (0.31 → 0.28) because its calibration constants
  assumed a curvature range the model never produces, pinning **every** input to ~0.30 regardless of
  content. Recalibrated, it turns out to be the *strongest* baseline signal (0.63, not 0.31) and it
  drops to 0.25 under rewriting. All four local detectors move.
- **The local proxies partly anti-correlate with human-ness.** A rewrite that reads *obviously* more human
  scored **higher** on the proxy (0.578 → 0.918). So a low local score means "passed the weak local
  proxies," not "reads human" and **not** "beats GPTZero." That's exactly why the loop treats the local
  score as a weak hint and gates hard on meaning instead.

**The honest ceiling:** for free you can strip the lexical/perplexity tells *and* most of the
content/genre signal, and clear the *free* web checkers — but the curvature detector still doesn't
move, and clearing the local proxies does not imply clearing GPTZero / Originality / Turnitin (which
need their API in the loop — paid). The tool says so, everywhere.

---

## 🏆 Why this is the most rigorous open detector-audit toolkit

We surveyed ~110 open-source humanizer repos (GitHub topics, papers-with-code, the research SOTA) as part
of building this project, and re-swept the field on 2026-08-05 across **624 queries turning up 1287 candidate
repos, of which the top 435 were read individually** — the full method and raw data are in the
[census](docs/humanizer-census.md). That deep-research survey ([`humanizer-research-report.md`](humanizer-research-report.md)) ranks the
exploitable gaps; its first one, quoted exactly:

> *"**Closed-loop detector-feedback rewriting.** No shipping product does iterative rewrite against live
> detector scores. Evidence says it's the single strongest lever (−88% TPR, training-free,
> quality-preserving). **Build this first.**"*

**This is the repo that closed that loop.** The four criteria in the table below are *our own* framing of
what closing it end-to-end requires — not a quotation. An earlier version of this section attributed a
four-part sentence to the report *"verbatim"*; [that sentence is not in it, in any commit](docs/why-best-open-repo.md),
and the report's real claim is about *shipping products* rather than open-source repos. Here it is against
the strongest open competitors:

| Capability | **untell (this repo)** | lynote (1.4k★) | patina (196★) | StealthHumanizer (58★) | harshaneel (51★) | Aboudjem (97★) | StealthRL (research) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Inference-time **detector-feedback loop** | ✅ | ❌ | ◑ own score | ◑ multi-pass | ◑ manual | ❌ | ◑ train-time |
| **Real detectors** in the loop (not an internal score) | ✅ | ❌ | ❌ | ❌ | ◑ Binoculars only | ❌ | ✅ ensemble |
| **Commercial** adapters (Originality/GPTZero/Turnitin-class) | ✅ 6 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Semantic meaning gate** + citation lock | ✅ | claim | ◑ rollback | ◑ keyword | heuristic | ❌ | ✅ BERTScore |
| **Per-sentence** targeting | ✅ | ❌ | ◑ | ❌ | ❌ | ❌ | ❌ |
| **Live detector round-trip** (real score shown) | ✅ ZeroGPT 100→0 | ❌ | ❌ | ❌ | ◑ Binoculars | GIF | ✅ paper |
| Packaged **install** (pip *and* Claude skill) | ✅ both | ✅ | ✅ | web app | ✅ skill | ✅ skill | ❌ research |
| **CI** on real models | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Runs **without a GPU** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| License | MIT | MIT | MIT | MIT | MIT | MIT | MIT |

**Stars are not capability.** lynote (1.4k★) is an unvalidated translation chain with no loop or verifier;
the highest-starred repos win on SEO, not architecture. The full, evidenced breakdown — including the *one*
place we're honestly **not** #1 (StealthRL's GPU-trained RL policy is a stronger raw *attack model*, though
it's a training framework, not a usable tool) — is in **[docs/why-best-open-repo.md](docs/why-best-open-repo.md)**
and the ~110-repo capability audit in **[docs/competitive-gap-plan.md](docs/competitive-gap-plan.md)**.

**vs the *free SaaS* humanizers** (Undetectable, QuillBot, HIX Bypass, Humanize AI Pro, …): they all
reduce to 3–4 mechanisms we already implement, so we benchmark them apples-to-apples and measure that
our loop is the **only** technique that lowers the AI-tells rate while holding the meaning gate —
on the built-in demo corpus it reaches **zero tells** (14.46 → 0.0, meaning 0.93, n=3); on real HC3
text the same configuration gets **4.22 → 3.81** and the detector barely moves. The zero is a
property of the demo paragraphs, not of the tool, and
[docs/humanizer-comparison.md](docs/humanizer-comparison.md) has said so for longer than this line
did. Their "99% bypass" claims don't survive independent testing (Originality flags the top "free"
tool at **100% AI**). The reproducible head-to-head, the catalog, and the honest verdict:
**[docs/humanizer-comparison.md](docs/humanizer-comparison.md)**.

**[docs/removing-ai-tells.md](docs/removing-ai-tells.md)** is the one-page answer to the question
underneath all of this: every technique class the 435-repo census identifies, measured on one corpus
against four axes — detector score, catalogued tells, stylometric displacement, and whether the
output is still text a human can use. Three results a single-axis table cannot show: unicode
trickery changes every document and moves the detector score by **nothing** while planting 641
invisible or counterfeit characters; word substitution is **inert** on prose carrying no catalogued
tell; and **no technique moves a document away from how machines write** — every one that works
moves it closer while lowering the score.

---

## Tiers

The scripts auto-detect what's installed and **degrade gracefully** — the score JSON reports which `tier`
actually ran, so you always know how much to trust the number.

| Tier | Install | Detectors | Notes |
|---|---|---|---|
| **lite** | *(default — nothing to install)* | perplexity + burstiness heuristic; token-overlap quality | Stdlib only, **weak** — a demo signal, not an evasion claim. **MEASURED on 100 real HC3 pairs at the shipped 0.30 threshold: it flags 65% of HUMAN text and 99% of AI**, so on the stdlib path "flagged" at this tier is close to "flagged everything". AUROC is 0.810 — the separation is real, the *threshold* was what was mis-placed for it. **Fixed 2026-08-08**: the reported verdict now uses its own calibrated cut point (`verdict_threshold`, 0.45 on this path) while the rewrite loop keeps optimising against 0.30, so stronger rewriting is not traded away for a kinder verdict. Measured on 100 human / 100 AI texts pooled from HC3 and RAID, that takes false positives on human text from **60% to 15%** (AI recall 93% to 70%, balanced accuracy 66.5% to 77.5%). The GPT-2 path's swept optimum is 0.30 exactly, which is why the raise is per scoring path and not global. A lite flag is still worth re-running at `--tier full`. Instant on a clean install; if `torch` happens to be present it silently upgrades to GPT-2 perplexity — and that upgrade is what those numbers hinge on: **measured on the same 100 pairs, the GPT-2 path flags 6% of human text (AUROC 0.997) against the stdlib path's 69% (AUROC 0.754)**, an 11.5x difference in false positives under one tier name. `score` now reports `detector_modes` so a result says which path produced it, and warns when the stdlib path is the whole verdict. `UNTELL_LITE_NO_TORCH=1` forces the genuinely-instant stdlib path (0.2s, ~11s first call otherwise). |
| **full** | `pip install -e ".[full]"` | + RoBERTa-OpenAI, HC3-RoBERTa, MAGE, Fast-DetectGPT, GPT-2 perplexity; MiniLM cosine quality | Real proxy signal on CPU. Downloads models on first run. |
| **+ RADAR** | `UNTELL_ENABLE_RADAR=1` (opt-in) | + RADAR — the **paraphrase-robust** detector, the hardest open one to fool | ⚠️ `TrustSafeAI/RADAR-Vicuna-7B` is **non-commercial licensed** — research/eval only. |
| **heavy** | `pip install -e ".[heavy]"` | + Binoculars (2×Falcon-7B) | GPU recommended. Eval only. The local LLM-as-judge is **opt-in** (`UNTELL_ENABLE_LOCAL_JUDGE=1`), not part of any default tier: **3.7s per call** against 0.03–0.06s for every other detector, for **AUROC 0.591** on 20 labelled HC3 pairs — barely above chance. Worse, it scores human text at a mean of 0.853 and flags **89%** of it, and since the ensemble takes `max` that made the whole heavy tier flag 90% of human documents against full's 15%. **Re-measured 2026-08-11: the full tier's own figure is now 40–42%**, not 15% — 40% over 20 HC3 pairs and 42% over 40, at natural document length (median 141 words). The cause is the same `max` aggregation described here, with a different member: `mage` flags 33% of human text on its own, against 7% for hc3_roberta and roberta_openai, 3% for perplexity and 0% for fast_detectgpt. It is worst on SHORT text and non-monotonically so (100% of human text at 40 words, 17% at 200), which is also why the short-text table in `scripts/score.py` moved. **That 33% is HC3-SPECIFIC — re-measured 2026-08-11 over 30 pairs on each of three corpora, `mage`'s human false-positive rate at 0.30 is HC3 33.3%, RAID 0%, MAGE 3.3%.** So the false positives are a corpus artifact, not a property of the detector, and the full tier's 40–42% figure above is likewise an HC3 number. What IS a detector property is `mage`'s **saturation**: every AI text scores ≥0.999 on all three corpora (`ai_saturated_frac` 1.00 each), which is why it pins `max` everywhere and why the composite rewriter's selector could never see an improvement (see `rewriter/composite.py`). Two different things were being read off one number. The same sweep found **`hc3_roberta` at AUROC 0.531 on MAGE — chance** (human mean 0.147 against AI 0.274, TPR 0.267 at 0.30): it is trained on HC3 and does not transfer, so on out-of-distribution text it is in the default ensemble contributing nothing. **Priced through `max` rather than per-detector** (30 pairs per corpus, threshold 0.30), balanced accuracy by ensemble composition:

| composition | HC3 | RAID | MAGE | AI recall cost |
|---|---|---|---|---|
| default (all 5) | 0.783 | 1.000 | 0.917 | — |
| **minus `hc3_roberta`** | **0.800** | 1.000 | **0.950** | **zero on all three** |
| minus `mage` | 0.917 | 1.000 | 0.850 | 13.3pp on MAGE |
| minus both | **0.950** | 1.000 | 0.900 | 13.3pp on MAGE |

Dropping `hc3_roberta` weakly dominates the default everywhere and costs no AI recall on any corpus tested. `mage` is not free: on MAGE it uniquely catches 4 AI texts nothing else reaches at 0.30, while on HC3 it is what takes human false positives from 0.167 to 0.433.

**Re-run on REWRITTEN text** (n=8/corpus, the loop's actual job — raw-text accuracy could not tell "this detector does nothing" apart from "dropping it just makes the loop's target easier"):

| | HC3 human FPR | HC3 rewritten recall | RAID rewritten recall | MAGE rewritten recall |
|---|---|---|---|---|
| default (all 5) | **0.75** | 1.000 | 1.000 | 1.000 |
| minus `hc3_roberta` | 0.625 | **1.000** | **1.000** | **1.000** |
| minus `mage` | 0.25 | 1.000 | 0.875 | 0.750 |
| minus both | **0.00** | 1.000 | 0.750 | 0.750 |

**`hc3_roberta` costs zero recall on rewritten text on all three corpora**, and no composition catches rewritten AI that the default misses. So it does not earn its place by refusing to move — it does not earn it at all. Dropping it ties or beats the default on every corpus, raw and rewritten, which no other composition does.

**`mage` cannot be dropped.** It is the only detector reaching some AI text on two of three corpora — removing it costs 0.125 recall on RAID and 0.250 on MAGE — while on HC3 it flags **6 of 8 human texts**, single-handedly why the default sits at 0.625 balanced accuracy there. One member, load-bearing on two corpora and precision-catastrophic on the third; there is no composition that is best everywhere.

Still **not acted on**: dropping a detector from a shipped default is a product decision, and this is n=8 (n=4 on MAGE), one threshold, one rewriter. What it does establish is that the two members behave oppositely and that the case against `hc3_roberta` no longer has a counterargument from recall. The 15% figure is left in place above because it is what the heavy-tier comparison was made against. A 1.5B model asked "rate how likely this is AI" answers high almost regardless of input; that is instruction-following, not detection. |
| **commercial** | `pip install -e ".[commercial]"` + your keys | + Originality.ai, GPTZero, Winston, Sapling, ZeroGPT, Copyleaks, **LLM-as-judge** | The real checkers. Key-gated; nothing runs or bills unless you set a key. LLM-as-judge = a frontier model rates AI-likelihood against the ai-tells catalog (often the best free-of-proxy signal). |

```bash
untell-score "Your text here" --tier full --threshold 0.3
echo "piped text" | untell-score

# The full tier loads real models (~20s on first run, cached after) — the CLI says so before it
# starts. Add -q/--quiet to silence the notice; stdout stays pure JSON either way.
UNTELL_LITE_NO_TORCH=1 untell-score --tier lite -q "instant, stdlib-only, no network"
```

---

## Config file

`untell humanize` reads its defaults from `untell.yaml` in the working directory, or
`[tool.untell]` in `pyproject.toml`. A command-line flag always wins over the file, and an
`UNTELL_*` environment variable sits between the two.

```yaml
# untell.yaml
tier: full
rewriter: composite
style: academic
threshold: 0.30
max_iters: 5
best_of: 3
```

Those six keys are what is wired. A value outside the allowed set for its flag is refused with a
message rather than silently becoming a broken default — `tier: fulll` would otherwise reach the
scorer as an empty detector list. `untell score`, the REST server and the MCP server keep their
own defaults and do **not** read this file.

---

## Passing the real commercial detectors

Local detectors are *proxies*. To optimize for the checkers people actually care about — **GPTZero,
Originality.ai, Turnitin-class, Copyleaks, ZeroGPT, Winston, Sapling** — wire the real APIs. Each is
**key-gated**; nothing runs or bills unless you set its key.

```bash
pip install -e ".[commercial]"
export GPTZERO_API_KEY=...      ORIGINALITY_API_KEY=...   WINSTON_API_KEY=...
export SAPLING_API_KEY=...      ZEROGPT_API_KEY=...       COPYLEAKS_EMAIL=...  COPYLEAKS_API_KEY=...

untell-loop  "text" --tier commercial      # rewrite until EVERY configured checker passes
untell-verify "text" --threshold 0.30      # pass/fail per checker + overall verdict (exit 0 = all pass)
untell-prove "Your AI text" --margin 0.10  # verify → loop → re-verify: one before/after table
```

`untell-verify` exits `0` only when **every** configured checker scores under the threshold. `untell-prove`
runs the whole thing end-to-end so you get an honest before/after AI% per checker. (Each `--tier commercial`
iteration calls every checker, so it **costs API credits** — cap with `--max-iters`.)

### Free ways to test without paying

```bash
# No key at all — deterministic CPU word-substitution rewriter drives the loop ($0, no SDK):
untell-loop "text" --rewriter surgical --tier full
untell-ceiling --rewriter composite --tier full --best-of 3 --repeats 3   # vs the local ensemble

# Check the detectors themselves before trusting a number any of them produced:
untell-detector-audit                # fast smoke test — catches a dead or inverted detector
untell-detector-audit --pairs 100    # the real measurement: AUROC on labelled human/AI pairs
                                     # (needs .[eval]; only this mode supports a discrimination claim)

# Optimize against a REAL detector for free via its web UI (slow, needs a browser):
pip install -e ".[browser]" && playwright install chromium
untell-verify --browser zerogpt "text"     # drives the free ZeroGPT web UI — no API key, $0
untell-loop   "text" --browser zerogpt      # iterate against the LIVE ZeroGPT detector until it clears
```

The **`--rewriter surgical`** path makes the whole loop runnable with **no API key, no GPU, no model
download** — the bundled deterministic rewriter (PWWS/TextFooler-style word-importance substitution)
stands in for the hosted LLM. Weaker than Claude-as-rewriter, but it's what makes the free measurement
above reproducible. (In Claude Code, `/untell` uses Claude itself as the rewriter — also free.)

⚠️ **On text carrying no catalogued tell, `surgical` does nothing at all** — it returns your input
byte-identical, rather than rewriting it weakly. It ranks words by whether swapping one removes a
tell from `references/ai-tells.md`, so a text with no tell gives it no word to try. MEASURED on 40
committed machine-written abstracts (`eval/data/generated_abstracts.py`), lite tier: 36 have an
empty ranking and 37 come back unchanged, against 18 of 20 changed for `structural` and 14 of 20 for
`composite` on the same corpus. The tell catalogue reads academic-vs-chatbot **register**, so formal
prose is the ordinary case for this, not an edge — and more `--best-of` draws cannot help, because
the rewriter is deterministic. Use `composite` (the default) or `structural` on that text; the loop
now says so in its `warning` when it happens, instead of reporting the run as drafts refused on
score.

Free rewriter backends, weakest → strongest (all no-key): **`surgical`** (word swaps, zero-dep) →
**`structural`** (sentence-level transforms) → **`composite`** (structural + surgical, the default) →
**`neural`** (T5 best-of-N paraphrase + composite; needs `.[full]`) → **`ensemble`** / **`max`** (runs
composite + mt_pivot + neural and keeps the per-input detector-lowest — `>=` any single method
**on a single call**). `max` is an alias for `ensemble`, not a second technique. And the `>=`
guarantee is per call, not per `--best-of N` run: under an outer best-of loop, `neural` spends every
draw on an independent stochastic T5 sample while `ensemble` spends each draw on an internal contest
a composite output can win — and composite draws from a narrower distribution, so `ensemble
--best-of 3` is **not** guaranteed to beat `neural --best-of 3`. Measured as mean pairwise
similarity among 4 consecutive draws on two documents (lower is more diverse): ensemble
0.858/0.859, neural 0.569/0.808.
T5-base paraphrase is high-variance on its own (a single draw can *raise* a detector score), so the
neural path samples several and keeps the best, and the ensemble only ever adopts a rewrite that beats
the original — see [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md).

The `--browser` path drives a real headless browser through a free web checker and reads the % score.
**ZeroGPT ships built-in** (confirmed working live). Most other free detectors are now bot-gated
(reCAPTCHA / login-redirect / iframe widgets) — see [docs/free-detector-probes.md](docs/free-detector-probes.md).
Add your own site with **zero code** — it's just CSS selectors in a JSON file
([examples/browser_sites.example.json](examples/browser_sites.example.json)).

> ⚠️ Browser checking is **slow, fragile, and ToS-caveated** — for occasional checks on your own text, not
> the hot loop. The reliable multi-detector path is the key-gated commercial tier.

---

## ❓ FAQ

<details>
<summary><b>Can a free tool actually move a detector's verdict?</b></summary>

Yes — the lite tier installs with **zero dependencies** and the `--browser zerogpt` path optimizes against a
real detector for **$0**. "Actually works," honestly: the loop reliably clears the *free* web detectors
(ZeroGPT live-measured 100%→0%), and the full/commercial tiers optimize against the harder ones. No tool —
this one included — can promise it passes *every* commercial detector forever; the ones that claim "99%
human" are lying. This repo tells you the real per-detector score instead.
</details>

<details>
<summary><b>Will this get past GPTZero / Turnitin / Originality.ai?</b></summary>

It *optimizes and verifies against* them. ZeroGPT is built into the free browser path and live-proven.
GPTZero, Originality.ai, Turnitin-class, Copyleaks, Winston and Sapling are wired as **key-gated commercial
adapters** — the loop drives the max across every checker you configure below threshold. Originality.ai is
genuinely the hardest (the research literature and public benchmarks consistently rank it the toughest to evade); we don't
claim to beat it without your API key to prove it. Honesty is the point.
</details>

<details>
<summary><b>Will it ruin my meaning, citations, or numbers?</b></summary>

No — that's the core differentiator. A **semantic-similarity gate** rejects any rewrite that drifts too far
from the original meaning, and **preserve-lock** freezes citations, numbers, quotes, URLs and named entities
byte-for-byte. Other humanizers are known to inject grammar errors and even reverse facts when they paraphrase
blindly; this one refuses meaning-breaking rewrites by design. Good for academic / legal / ESL writing.
</details>

<details>
<summary><b>How is this different from Undetectable.ai / QuillBot / WriteHuman?</b></summary>

Those are closed SaaS that do a single blind pass and report a fake binary "human/AI." This is open source,
runs a **closed detector-feedback loop**, optimizes against **multiple real detectors at once**, gates on
**meaning preservation**, and gives you an **honest, reproducible per-detector score** instead of a marketing
claim. It's a research/defensive tool you can read, audit, and run yourself.
</details>

<details>
<summary><b>Is this against the rules / ethical?</b></summary>

AI detectors are noisy proxies — they falsely flag non-native English writers at high rates (~61% in some
Stanford-cited studies). This exists as a **research harness and a defense against false positives**, not an
academic-dishonesty aid. Don't use it to misrepresent authorship where that's prohibited. See the caveats
below — we mean them.
</details>

---

## Eval harness (research)

Validates the thesis — closed loop beats single-pass — without a human in the seat (a scripted rewriter
stands in for Claude so it's measurable):

```bash
pip install -e ".[full,eval]"
python -m eval.benchmark --dataset builtin --n 5                      # zero-download smoke run
python -m eval.benchmark --dataset raid --n 200 --tier full --enable-radar   # adversarial: hardest detector + RAID

untell-ceiling --rewriter composite --best-of 3 --repeats 3   # free inference-only evasion (no key, $0)
untell-eval-policy --policy out/rl-humanizer --vs-base   # A/B a trained LoRA policy vs the untuned base
```

The report shows **per-detector beat-rates** and names the **hardest detector to beat** (the honest
headline). `untell-ceiling` measures how far the free loop moves the local ensemble (see the
[measured ceiling](#-the-measured-free-ceiling)); `untell-eval-policy`
scores the optional GPU-trained single-pass policy (`training/`) against held-out text.
`--enable-radar` adds the paraphrase-robust RADAR detector (non-commercial — research/eval only).
For broader cross-detector benchmarking, [IMGTB](https://github.com/kinit-sk/IMGTB) + the
[RAID](https://github.com/liamdugan/raid) leaderboard are the standard references.

---

## Repo layout

```
untell/            # THE SKILL (this dir is what you install)
  SKILL.md           # trigger + loop procedure + rewrite rubric
  scripts/           # cli (unified `untell`) · score · tells · preserve · quality · sentences · run · verify
  detectors/         # base protocol + tiered adapters (8 local + 7 commercial incl. LLM-as-judge)
  rewriter/          # optional rewriters: hosted (Anthropic/OpenAI) · surgical (no-key) · local LoRA policy
  attacks/           # surgical substitution · homoglyph · scrub · back-translation
  references/         # thresholds.md · prompt-rubric.md · ai-tells.md
eval/                # benchmark · ceiling (free evasion) · compare_humanizers (vs technique classes) · eval_policy
training/            # GPU moat: RL-against-ensemble (GRPO+LoRA) · surrogate distillation
tests/               # unit tests (lite runs with zero ML)
docs/                # humanizer-comparison · free-ceiling report + measured · why-we're-best · competitive audit
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

CI runs a **lite** matrix (ruff + pytest, no downloads) across Python 3.9/3.11/3.12 **and** a **full-tier**
job (Ubuntu, CPU torch + `.[full,eval]`) that loads the real RoBERTa / Fast-DetectGPT / GPT-2 detectors and
runs the torch-gated tests. See **[CONTRIBUTING.md](CONTRIBUTING.md)** to get involved and
**[ROADMAP.md](ROADMAP.md)** for what's next (the GPU RL-against-ensemble moat).

---

## Environment variables

Every `UNTELL_*` variable the code reads. Sixteen of these were undocumented until 2026-08-08 —
including the server's auth key and two switches that disable a meaning gate — so the
configuration existed but could not be discovered. `untell-audit` now fails if a new one is added
without a row here.

| variable | what it does |
|---|---|
| `UNTELL_API_KEY` | bearer token the REST server requires; unset means no auth |
| `UNTELL_HOST` / `UNTELL_PORT` | bind address for `untell-server` (default `127.0.0.1:8000`) |
| `UNTELL_RATE_LIMIT` | requests per minute per client for the REST server |
| `UNTELL_CORS_ORIGINS` | comma-separated origins the REST server allows with credentials; unset = any origin may call, credentials NOT allowed (the spec-legal wildcard) |
| `UNTELL_BROWSER_SITES` | comma-separated free web detectors for `--browser` |
| `UNTELL_LITE_NO_TORCH` | force the pure-stdlib lite path even when torch is installed. The two paths differ by 11.5x in false positives, so this is how you pin which one you are measuring |
| `UNTELL_SELECT` | what best-of-N ranks candidates on: `max` (default, the shipped objective), `mean`, or `dropout` (rank on a random 60% subset of the tier, resampled each iteration, so a candidate cannot win by exploiting a member absent from the subset that judged it). Anything else falls back to `max`. Read per call, so a sweep needs no reload |
| `UNTELL_DISABLE_MAGE` | skip the MAGE detector (large download) |
| `UNTELL_ENABLE_RADAR` | opt into the RADAR detector in the benchmark |
| `UNTELL_ENABLE_LOCAL_JUDGE` / `UNTELL_JUDGE_MODEL` | enable and select the local LLM judge. Defaults to `Qwen/Qwen2.5-1.5B-Instruct`; `Qwen/Qwen2.5-7B-Instruct` is the larger option (`untell.detectors.local_judge.suggested_models()`). The judge is **heavy tier at either size** — 3.7s per call against 0.03–0.06s for every other detector, for AUROC 0.514 on 40 labelled HC3 pairs. The 7B is unmeasured here; measure it before believing it. |
| `UNTELL_DISABLE_NLI` | **turns off the NLI entailment gate.** Meaning is then unverified — the loop can adopt a rewrite that contradicts the source |
| `UNTELL_DISABLE_ROLES` | **turns off the predicate-argument veto.** "The company sued the regulator" may come back reversed |
| `UNTELL_TIER` · `UNTELL_THRESHOLD` · `UNTELL_MAX_ITERS` · `UNTELL_REWRITER` · `UNTELL_STYLE` · `UNTELL_BEST_OF` | defaults for `untell humanize`, overriding the shipped ones. Same six keys `untell.yaml` and `[tool.untell]` accept, and the precedence is CLI flag → env → config file → shipped default. Out-of-range and unknown values are refused with a message naming the value and what was used instead — a silently clamped setting would be its own bug. |
| `UNTELL_POLICY_DIR` / `UNTELL_POLICY_BASE` / `UNTELL_POLICY_4BIT` / `UNTELL_POLICY_MAXTOK` / `UNTELL_POLICY_NO_SYSTEM` | local trained-policy rewriter: adapter directory, base model, 4-bit loading, token cap, and whether to send a system prompt |
| `UNTELL_POLICY_WHOLE_DOC` | send the local policy rewriter the whole document in one call instead of sentence by sentence. The trained adapter always works whole-document; this forces the same for the untuned base model, where per-sentence prompting is what keeps it from summarising |
| `HUMANIZE_BROWSER_SITES` / `HUMANIZE_ENABLE_RADAR` | pre-rename spellings of the two `UNTELL_*` switches above, still honoured. Either name works; the `UNTELL_*` one is preferred and the `HUMANIZE_*` one is kept so existing setups do not break silently |
| `UNTELL_REWARD_FAST` | model-free stdlib reward for training runs |
| `UNTELL_SURROGATE_DIR` | distilled surrogate detector used as the training reward |

The two `DISABLE` switches are called out because they remove a guarantee the README makes
elsewhere. Nothing warns at runtime when they are set.

## Troubleshooting

**Full-tier detectors come back as `null`, you see `failed_detectors`, or a "NumPy 2.x" warning.**
The supervised detectors load `torch`/`transformers`; older builds of those were compiled against
NumPy 1.x and crash on import when NumPy 2.x is present. untell **excludes** any detector that fails to
load — it never fakes a neutral `0.5` that would silently pin your score — lists it under
`failed_detectors`, and honestly downgrades the reported `tier` (so a broken full-tier run reports
`lite`, not a fake `full`). To get the full ensemble back, align the versions, ideally in a fresh venv:

```bash
python -m venv .venv && . .venv/Scripts/activate     # (. .venv/bin/activate on macOS/Linux)
pip install -e ".[full]"            # pulls torch/transformers matched to your NumPy
# …or pin NumPy down in an existing env:
pip install "numpy<2"
```

**`mage` is always `null`.** `yaful/MAGE` ships a config current `huggingface_hub` rejects (`id2label`
validation). It's auto-excluded and the rest of the ensemble runs normally — nothing you need to fix.

**Full tier feels slow.** Each `untell-score` call loads the models fresh, and the first run downloads
~0.5 GB of weights (cached after that). For a multi-iteration run prefer the single-process headless
loop — `untell-loop` loads the models once — over many one-off score calls. The **lite** tier needs
no downloads at all. (The [web UI](docs/demo.html) is a front-end for the REST API, so it inherits
whatever tier the server it talks to is running — it does not score in the browser.)

## Honest caveats

- **Proxy ≠ commercial.** The local detectors approximate; they aren't Originality.ai / Turnitin. The
  ensemble is a *signal*, not a verdict. "Passes all checkers" is unprovable against detectors you don't run.
- **Local proxies do NOT predict GPTZero / Originality.** Measured: a rewrite the bundled local ensemble rates
  *low* can still score **100% AI on GPTZero**, which runs dedicated anti-humanizer ("AI Paraphrasing")
  detection. A low local `max` means "passed the weak local proxies," **not** "undetectable." The only way to
  optimize for a specific commercial detector is to put **it** in the loop (`--tier commercial` + its API key)
  — and even then GPTZero/Originality are the hardest and nobody beats them reliably.
- **lite is a demo.** The zero-install heuristic shows the loop; it's not an evasion claim. The full tier is
  the honest baseline; Binoculars (GPU) is the strongest proxy.
- **Claude is the rewriter.** Output quality and evasion depend on the running model.
- **Ethics.** Detector false-positives disproportionately harm non-native writers. This is a research/eval
  harness and a defense against that — not a plagiarism or academic-dishonesty aid.

## Contributing

PRs, detector adapters, and new free-checker selectors are welcome — see
**[CONTRIBUTING.md](CONTRIBUTING.md)**, the **[good first issues](https://github.com/ssamba1/untell/issues)**,
and our **[Code of Conduct](CODE_OF_CONDUCT.md)**. Found a security issue? See **[SECURITY.md](SECURITY.md)**.

If this saved you from a false AI flag — or you just think it's the most honest humanizer on GitHub —
a ⭐ helps others find it.

## License

[MIT](LICENSE). Free to use, modify, and distribute.
