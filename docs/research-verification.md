# Verification ledger — every research claim this repo publishes, and how far it was checked

Compiled 2026-09-01. This is the audit trail behind
[`ai-writing-research.md`](https://github.com/ssamba1/untell/blob/main/ai-writing-research.md) and
[`research-to-build.md`](research-to-build.md). It exists because those two documents were written
from search-engine snippets, and a snippet is not a source.

## What could and could not be reached

Outbound access in the compiling environment is governed by an organization egress policy. **These
hosts are blocked at the gateway** and were reported rather than routed around, per the proxy's own
instructions: `arxiv.org`, `export.arxiv.org`, `aclanthology.org`, `api.semanticscholar.org`,
`huggingface.co`, `nature.com`, `science.org`, `link.springer.com`, `europepmc.org`,
`digital-strategy.ec.europa.eu`, `artificialintelligenceact.eu`.

**A second pass found a third channel that closed most of the gap.** The ACL Anthology publishes its
complete paper metadata — including abstracts — as XML in its own GitHub repository, and
`raw.githubusercontent.com` is reachable by both WebFetch and curl. Downloading
`data/xml/{2024.acl,2025.acl,2026.acl,2025.naacl,2026.eacl}.xml` (≈18 MB) and parsing out the
relevant entries moved **seven papers from Tier B to Tier A**. This is the Anthology's own
distribution of its own metadata on a permitted host — not a mirror or a proxy around a denial.
Several arXiv-only papers were then confirmed through their authors' own GitHub repositories.

**These channels are open and were used as primary sources:**

- **PubMed / PMC via MCP** — full metadata, and full text for open-access records. This covers
  *Nature Human Behaviour*, *Trends in Cognitive Sciences*, *Patterns*, *Science Advances*,
  *PeerJ CS* and more, which is most of the prevalence and fairness literature.
- **github.com via WebFetch** — author repositories, dataset cards, reference implementations.
- **ACL Anthology XML via raw.githubusercontent.com** — official abstracts for every ACL, NAACL and
  EACL paper.
- **Web search** — indexes abstracts, so a claim quoted identically by several independent indexes
  is corroborated but not confirmed.

## Verification tiers

| Tier | Meaning |
|---|---|
| **A — read at source** | Full text or publisher abstract retrieved directly (PubMed/PMC or the authors' own repository). Quotable. |
| **B — corroborated** | Same figure returned by two or more independent indexes quoting the abstract. Very likely right; not quotable as verbatim. |
| **C — single/secondary** | One snippet, or a blog/vendor/press source. Directional only. |
| **✗ — corrected** | Checking changed the claim. The correction is recorded below and applied to the documents. |

---

## Tier A — confirmed at source

| Claim as published | Verified value | Source |
|---|---|---|
| Kobak et al.: ≥13.5% of 2024 biomedical abstracts LLM-processed, >15M abstracts 2010–2024 | **Verbatim.** "more than 15 million biomedical abstracts from 2010 to 2024… at least 13.5% of 2024 abstracts were processed with LLMs." **Plus a figure we did not have: "reaching 40% for some subcorpora."** | PubMed PMID 40601754, PMC12219543, [DOI](https://doi.org/10.1126/sciadv.adt3813) |
| Liang et al.: 61.3% average FPR on non-native TOEFL essays; 97.8% flagged by ≥1 detector | **Verbatim**, plus exact design: 7 detectors, 91 TOEFL essays, 88 US 8th-grade ASAP essays; 19.8% unanimously flagged | PubMed PMID 37521038, PMC10382961, [DOI](https://doi.org/10.1016/j.patter.2023.100779) |
| Sourati et al.: 21–50% reduction in writing-complexity variance, 7 datasets, >880,000 texts | **Verbatim**, incl. "(P ≤ 0.05)" and "three studies" | PubMed PMID 42637911, [DOI](https://doi.org/10.1038/s41562-026-02550-0) |
| DetectGPT measured at 54.6% real-world accuracy — "no better than random" (a claim **already published** in `humanizer-research-report.md`) | **Verbatim.** "despite claiming a 99% accuracy rate, performed the worst in practice, achieving merely 54.63% accuracy. This makes it virtually no better than random guessing." | PubMed PMID 40989485, PMC12453642, [DOI](https://doi.org/10.7717/peerj-cs.2953) |
| Beemo composition: 6.5k + 13.1k texts, ten instruction-tuned LLMs, expert + LLM edits | Confirmed on the authors' repository, incl. editor models (GPT-4o, Llama 3.1-70B) and the 20–40% edit budget | [github.com/Toloka/beemo](https://github.com/Toloka/beemo) |
| SynthID-Text ships a no-training Weighted Mean detector and a trained Bayesian detector, integrated in HF Transformers | Confirmed — **plus a build-relevant caveat we did not have:** the DeepMind repo is "not intended for production use" and points to the HF Transformers implementation instead | [github.com/google-deepmind/synthid-text](https://github.com/google-deepmind/synthid-text) |

## Tier A — the ACL Anthology pass (second round)

Read from the Anthology's own XML. Abstracts quoted here are the published ones.

| Paper | Claim as published | Result |
|---|---|---|
| **MCP / RealDet** (2025.acl-long.601, Zhu, Ren, Cao, Lin, Fang, Li) | Conformal prediction bounds FPR; MCP recovers the accuracy that plain CP costs; ships RealDet | ✅ **Confirmed.** "most existing detection methods focus excessively on detection accuracy, often neglecting the societal risks posed by high false positive rates… directly applying CP constrains FPRs, [but] also leads to a significant reduction in detection performance." ✗ **But the published abstract never says "length-conditioned"** — that detail came from a secondary summary and is demoted to Tier B, as are RealDet's 15-domain / 22-LLM / 847k-text dimensions |
| **Beemo** (2025.naacl-long.357) | 6.5k + 13.1k texts, ten instruction-finetuned LLMs, 33 detector configurations, expert editing evades detection | ✅ **Confirmed verbatim**, including "benchmarking 33 configurations" and "expert-based editing evades MGT detection, while LLM-edited texts are unlikely to be recognized as human-written". The repo's "11 detectors" is the initial release; both numbers are right |
| **RAID** (2024.acl-long.674) | Benchmark scale and the robustness finding | ✅ **Confirmed verbatim**: "over 6 million generations spanning 11 models, 8 domains, 11 adversarial attacks and 4 decoding strategies", evaluating "8 open- and 4 closed-source detectors". The shipped dataset on GitHub is larger (>10M docs, 11 domains, 12 attacks) — cite the release you mean |
| **Feature-inversion trap / StyloBench** (2026.acl-long.1998, ACL 2026 **Oral**, incl. Preslav Nakov) | Features flip sign under personalization | ✅ **Confirmed**, plus a number we lacked: StyloCheck "predicts both the direction and magnitude of cross-domain performance shifts with an **85% correlation** to actual outcomes" |
| **DetectRL-X** (2026.acl-long.1773) | 8 languages, 6 domains, four commercially-available LLMs, polish/expand/condense | ✅ **Confirmed verbatim**, including "8 dimensions" and the multilingual paraphrase/perturbation attack framework |
| **M4GT-Bench** (2024.acl-long.218) | Three tasks incl. human–machine boundary detection | ✅ **Confirmed** — and it carries a finding that supports our thesis directly: "obtaining good performance in MGT detection usually requires an access to the training data from the same domain and generators" |
| **LitBench** (2026.eacl-long.362) | 43,827 training pairs, 2,480-pair test set, Claude-3.7-Sonnet 73%, trained RMs 78% | ✅ **Confirmed verbatim** |

### Author-repository confirmations

| Paper | Result |
|---|---|
| **Adversarial Paraphrasing** ([chengez/Adversarial-Paraphrasing](https://github.com/chengez/Adversarial-Paraphrasing), **NeurIPS 2025**) | ✅ Confirms the figures **already published in `humanizer-research-report.md`**: average **T@1%F reduction of 87.88%** under OpenAI-RoBERTa-Large guidance, and **98.96% on Fast-DetectGPT** |
| **SynGuard / SynthID robustness** ([githshine/SynGuard](https://github.com/githshine/SynGuard)) | ✅ Exact degradation table, which we only had as prose: SynthID-Text F1 **1.000 → 0.842** (paraphrase), **0.788** (copy-paste), **0.714** (re-translation); SynGuard recovers to 0.923 / 0.891 / 0.775 |
| **Base Models Look Human** ([YixuanEvenXu/humanization-by-iterative-paraphrasing](https://github.com/YixuanEvenXu/humanization-by-iterative-paraphrasing)) | Repo confirms authorship (Xu, Zhong, Raghunathan, Fang, Kolter) but publishes **no numbers**. The empirical claim stays Tier B — and the paper states it qualitatively, so **no figure may be quoted** |

### ✗ Karr et al. — published, and our numbers were imprecise

*Why AI Detection Fails for Academic Integrity* is **not** a bare preprint: it is Karr, Khvatskii,
Hua and Chawla (University of Notre Dame), in the **Proceedings of the ACM AI Leadership Summit
(AILS '26)**, 30 Aug – 2 Sep 2026, Atlanta. That is peer-reviewed, and it raises the weight this
result carries.

The numbers are sharper than the range we published. We wrote "light edits flagged at 38–80%". The
paper splits by detector: **light edits flagged at 64–80% by Pangram and 38–49% by GPTZero** — and
adds the half we were missing entirely: **after humanization, more than 96% of AI-labeled rewrites
evade both detectors.**

**That asymmetry is the most quotable sentence in this whole literature, and it is now Tier A:
detectors punish legitimate light editing at 64–80% (Pangram) and 38–49% (GPTZero) while letting more
than 96% of deliberately humanized synthetic text through.** They are hardest on exactly the people
not cheating.

> ✗ **Round twenty-three fixed this sentence.** It used to read "38–80%" — the collapsed range that
> the paragraph **three lines above it** corrects. The most rhetorically load-bearing line in these
> documents restated the very number its own correction had just retired, and then that line was
> copied into `research-to-build.md`.

## Tier A — findings that were *not* in our documents and change the plan

These came out of reading sources rather than snippets, and they are the reason this pass was worth
doing.

**1. The false-positive rate is not a property of a detector.** *AI Detectors Fail Diverse Student
Populations* (arXiv:2603.20254) reframes the theory: existing analyses model detection as a binary
test between *one* human distribution and *one* AI distribution. In a real institution there is no
single human distribution — the null is composite ("this was written by student *i*, whose
distribution is unknown"). Applying total-variation bounds to a composite null yields the result
that **any text-only, one-shot detector with useful power must produce false accusations at a rate
governed by the overlap between that population's writing and AI output — a constraint arising from
population diversity, logically independent of AI model quality, that cannot be overcome by better
detector engineering.** This is stronger than the AUROC→0.5 ceiling the repo currently cites: it
does not require the distributions to converge, only the population to be diverse.

> ⚠️ **Weight this correctly, because we made it the strategic keystone.** It is Tier B, and the
> weakest Tier-B item the strategy leans on: arXiv-only, **single-authored** (N. A. Garland, Griffith
> University), from outside the NLP community. It is a mathematical argument, so it stands or falls
> on its logic rather than on refereeing, and its conclusion is independently corroborated by three
> Tier-A empirical results — Liang's two-directional intervention, Pratama's per-subgroup ODR, and
> Karr's asymmetry. Use it as the framing that *explains* those results, not as a theorem the field
> has ratified. If one item in this ledger deserves an independent read before it carries a strategy,
> it is this one.

**2. A detector can have a 0% false-positive rate and still be the most biased one.** In Pratama's
data GPTZero scored 97.22% accuracy with **0.00% FPR** on clean human-vs-AI — and then showed the
*strongest* bias against non-native authors on AI-**assisted** text (Welch's t = −2.115, p = 0.036),
with an over-detection rate of **25% for non-native authors against 11% for native**. Clean-split
accuracy does not predict fairness on the realistic case. Any audit that stops at human-vs-AI misses
the failure entirely.

**3. Two peer-reviewed ensemble metrics we should be using and are not.** Same paper:
**FAR (False Accusation Rate)** — fraction of genuine human documents flagged by *at least one*
tool — measured at **44.44%**; and **MFAR (Majority False Accusation Rate)** — flagged by a
majority — at **4.17%**. FAR is exactly what untell's `max` aggregation computes, and there is a
published name and precedent for it.

**4. Which assistant polished the text changes the risk more than who wrote it.** Gemini-2.0-Pro-
enhanced abstracts scored far higher as AI than ChatGPT-o1-enhanced across all three tools
(GPTZero mean 55.50% vs 19.79%, t = −5.97, p < 0.001). Nobody reports this, and it is measurable.

**5. Vendor thresholds are not even internally consistent.** ZeroGPT labelled abstracts AI-generated
at scores below 30% while other tools use 50%, "a lower, less transparent threshold."

**6. The dataset is MIT-licensed and public.** Pratama's abstracts, per-tool scores and analysis code
are at [github.com/ahmadrpratama/ai-text-detection-bias](https://github.com/ahmadrpratama/ai-text-detection-bias)
— 72 abstracts stratified 36 native / 36 non-native across three discipline groups, in original,
AI-generated and AI-assisted form. Small, but it is a ready-made fairness corpus with ground truth.

**7. Prior art for the calibration item.** [FPRCal](https://github.com/cisco-ai-defense/fpr-model-calibration)
(Cisco AI Defense) already calibrates detector scores to a fixed-FPR scale as a scikit-learn
pipeline fitted on benign scores. It is a security-domain tool, not a text-detection one, so the
application is still open — but it is prior art and should be cited rather than reinvented.

**8. The institutional auditing protocol is already specified in the literature** — assemble
stratified human-written corpora by subgroup (first language, programme, year, task type), run the
detector per stratum, record per-subgroup FPR — **and nobody ships it.**

## Tier B — corroborated, not read at source

Everything sourced only from a blocked host. Multiple independent indexes returned the same figures.

| Claim | Note |
|---|---|
| Holzwarth et al., 89% of PubMed Central papers show LLM-vocabulary excess by end-2025; Discussion 68% vs Methods 32% | arXiv:2608.10715. Named author and sectional split newly obtained |
| Karr et al.: light "refine abstract only" edits flagged at **64–80% by Pangram and 38–49% by GPTZero** (corrected from the collapsed "38–80%" in round twenty-three); unmodified 2023–25 originals at **9–15%**; non-STEM ≫ STEM (p<0.001); scores track long-token and Academic Word List density | arXiv:2608.11256 — the closest published work to untell's thesis |
| MCP conformal FPR control; RealDet = 15 domains, 22 LLMs, 847k+ texts, 113k+ human, bilingual EN/ZH, with adversarial variants | arXiv:2505.05084, ACL 2025. Far larger than we described |
| Adversarial Paraphrasing, StealthRL, DIPPER, ARB, StyloBench/feature-inversion, DetectRL-X, SHIELD, M4GT-Bench | All arXiv/ACL — host blocked |
| Base models judged human by GPTZero and Pangram; HIP works across Llama and Qwen families | arXiv:2605.19516 (Xu, Zhong, Raghunathan, Fang, Kolter). **No numeric FPR is claimed — do not invent one** |
| EU AI Act Art. 50(2) in force August 2026; three structural compliance gaps; machine-verifiable marks "fragile under standard data processing" | arXiv:2603.26983 (Schmitt et al., LREC 2026). Independently corroborates the August 2026 date |

## Tier C — secondary, and labelled as such wherever used

Legal cases (Adelphi, Minnesota, Washington State), vendor benchmark blogs, adoption surveys
(Gallup/Lumina, HEPI, Muck Rack), the 2026 ACL Pindrop 16-detector fairness study, and the "2–3×"
ESL flag-rate figures. Directional only.

---

## ✗ Corrections applied

| What we published | What is true | Where |
|---|---|---|
| "human writing increased collective semantic diversity 2–8× vs base GPT-4 essays" attributed to the *Trends in Cognitive Sciences* paper | **Misattributed.** The TiCS paper (PMID 41820108, [DOI](https://doi.org/10.1016/j.tics.2026.01.003)) is a **Review** whose abstract contains no numbers at all. The 2–8× figure is not traceable to it. Claim removed | `ai-writing-research.md` §2 |
| "**H2L** — nobody publishes what detectors do to human text an LLM rewrote" | **False.** Pratama (PeerJ CS, June 2025, Tier A) ran exactly that experiment and reports per-subgroup ODR/UDR; Karr et al. (2608.11256) quantify it at 38–80%. ARB remains valuable for scale and matched design, but it is not first | `research-to-build.md` §2, ROADMAP §7 |
| "MGTEVAL ships **26** detectors, 12 attacks" | The authors' repo says "**25+** detectors" and "**12+** attack families" — and reports **bootstrap CI, ECE, Brier, risk-coverage** and a **humanization** attack family, which is more overlap with untell than we credited | `research-to-build.md`, ROADMAP §7 |
| Beemo "33 detector configurations" | Reconciled, not wrong: **11 detectors across 33 configurations** | `research-to-build.md` §2 |
| RAID "6M generations, 8 domains, 11 attacks" (ACL abstract) | The shipped dataset is larger: **>10M documents, 11 domains, 12 attacks**, incl. Czech, German and Python. Both are true of different releases — cite the release | ledger only; no doc quoted these |
| "FPR as a function of stylistic distance from the model centroid — nobody has done it" | **Overstated.** Liang et al. ran the *intervention* in both directions in 2023 (enhancing non-native vocabulary cut FPR 61.3%→11.6%; simplifying native essays raised misclassification), and Karr et al. tie scores to Academic Word List density. What is genuinely open is narrower — a *continuous, centroid-referenced* distance measure, across subgroups, with modern detectors | `research-to-build.md`, chat claims |
| Karr et al. cited as a preprint; "light edits flagged at **38–80%**" | **Both imprecise.** It is peer-reviewed — Karr, Khvatskii, Hua & Chawla, **ACM AILS '26**, Notre Dame. And the range collapses two detectors: **64–80% Pangram, 38–49% GPTZero**. We also missed the other half entirely: **>96% of humanized rewrites evade both** | `research-to-build.md`, ROADMAP §7 |
| MCP described as deriving "**length-conditioned** quantile thresholds"; RealDet as "15 domains, 22 LLMs, 847k texts" | Neither appears in the published ACL abstract, read at source. Both demoted to Tier B and hedged. The FPR-bounding claim itself is ✅ confirmed, as is the trade-off MCP exists to fix | `research-to-build.md`, ROADMAP §7 |
| "Your Brain on ChatGPT" characterised as small and non-peer-reviewed | **Correct, and now citable:** still a preprint, with a formal published Comment (arXiv:2601.00856, Stanković et al.) faulting sample size, EEG methodology, reproducibility, reporting consistency and transparency | `ai-writing-research.md` §6 |

## Claims that survived unchanged

- No peer-reviewed quantification of neurodivergent-writer false-positive rates exists. Checked
  from three directions; sources actively warn that circulating numbers trace to no study.
- Detection is unreliable and beatable; paraphrase attacks transfer; watermarking only covers
  cooperating generators; retrieval defence works but needs provider-side logging.
- ~~Humans cannot reliably detect AI text (experts ~70%, students 59%, ESL teachers 61%).~~
  **✗ Retired in round nine.** Most cannot; frequent LLM users voting as a panel of five
  misclassified 1 of 300 articles and beat most detectors even under evasion. See below.


---

## Sensitivity analysis — does any decision actually hinge on an unverified claim?

The residual Tier-B set is small and it is all arXiv-only preprints on a host blocked by policy.
Rather than leave that as an open worry, this is the check that matters: **for each roadmap item,
what is the weakest source it rests on, and would a plausible error there change the decision?**

| Roadmap item | Weakest load-bearing source | If it were wrong |
|---|---|---|
| **23 — AI-assisted arm, FAR/MFAR, stratification** | Karr's exact percentages (Tier B, though the paper is peer-reviewed) | **No change.** Pratama is Tier A, read in full, and on its own establishes the whole case: 0.00% FPR on the clean arm, 25% vs 11% over-detection on the assisted one, with FAR/MFAR defined and measured. Karr sharpens the argument; it does not carry it |
| **18 — calibrated thresholds** | MCP's "length-conditioned" detail (Tier B) | **No change.** The load-bearing part — CP bounds FPR, plain CP costs accuracy, MCP recovers it — is ✅ Tier A from the published abstract. Conformal prediction is textbook statistics and does not need this paper to be correct; the length question is an implementation choice we would settle by measurement anyway |
| **19 — Beemo + ARB** | ARB's design details (Tier B) | **No change.** Beemo is ✅ Tier A verbatim and justifies the item alone. ARB is a dataset we would inspect before wiring it in, at which point its details verify themselves |
| **20 — base-vs-instruct arm** | *Base Models Look Human* (Tier B, and qualitative even in the paper) | **No change, by construction.** The item is to run *our own* measurement. We deliberately quote no number from it. If the paper is wrong, our arm is what shows that — which is a result worth having either way |
| **21 — SynthID / Article 50** | The August 2026 date | **Timing only.** The degradation figures are now ✅ Tier A from the authors' repo, and the date is corroborated by two independent sources and is trivially checkable against the regulation itself |
| **22 — confidence intervals** | Nothing external | **No change.** Arithmetic over data we already hold |
| **The composite-null keystone** | arXiv-only, single-authored | **Framing changes; strategy does not.** Its conclusion — that a false-positive rate is a property of a detector *and a population* — is what Liang (✅), Pratama (✅) and Karr independently measure. Losing the proof would cost us the clean theoretical statement, not the mandate to measure per-subgroup on the user's own corpus |

**Result: no roadmap item flips on any Tier-B claim.** Following this analysis the roadmap was
rewritten so that the point is structural rather than incidental: §7's strategic core is now built
from four Tier-A results only (Liang, Pratama, M4GT-Bench, Beemo), and every Tier-B item — the
composite-null framing, Karr's asymmetry, ARB's design, base-vs-instruct — is demoted to an
explicitly labelled *lead* that no decision depends on. **The verified set and the load-bearing set
are now the same set.** Every item is either grounded in a Tier-A
source, or is itself a measurement that would expose the error it depends on. That is the strongest
honest statement available here — not "everything is verified", which the egress policy forbids, but
**"nothing we plan to do would change if the unverified parts turned out wrong."**

### What would still be worth an outside check

Three things, in order, for anyone with unrestricted access:

1. **arXiv:2603.20254** — the composite-null argument. It is load-bearing for the framing and it is
   the weakest-sourced item here. Read the proof.
2. **arXiv:2608.11256** — Karr et al. Confirm 64–80% / 38–49% and the >96% humanized-evasion figure
   directly; they are the numbers this roadmap quotes most.
3. **arXiv:2607.29539** — ARB. Confirm the four-way matched design before we build a loader against it.

Everything else either reads at source from PubMed, the ACL Anthology or an author's repository, or
does not carry a decision.

---

# Round three — a systematic pass over the ACL Anthology

The first two rounds spot-checked papers we already knew about. That is not the same as knowing what
the field contains. This round downloaded **16 Anthology volumes** (ACL, EMNLP, NAACL, EACL, COLING,
LREC, TACL and *Computational Linguistics*, 2024–2026; ≈48 MB), parsed **20,875 abstracts**, and
classified the **334** that concern machine-generated-text detection.

## The field's own priorities, counted

Of those 334 detection papers, the number addressing each topic. MEASURED by
`python -m eval.litreview --download --json` at the 16-volume stage; superseded by round six and
corrected again in round fifteen, both below:

| Topic | Papers |
|---|---|
| Robustness / paraphrase / evasion | **102** |
| Human–AI mixed or edited text | 32 |
| Watermarking | 29 |
| Education / academic integrity | 20 |
| Calibration / thresholds / operating points | 18 |
| **Fairness or non-native bias** | **5** |
| **False positives or false accusation** | **6** |

**Roughly 30% of the field's detection effort goes to making detectors harder to evade, and under 2%
to what happens when they are wrong about a person.** That is untell's gap, and it is now a count
over the primary literature rather than an assertion.

## What this pass found that changes our positions

### ✅ Tier A replacements for claims that were Tier B

- **The H2L case is fully covered, peer-reviewed, with a public dataset.** *Almost AI, Almost Human:
  The Challenge of Detecting AI-Polished Writing* ([2025.findings-acl.1303](https://aclanthology.org/2025.findings-acl.1303/))
  evaluates **twelve detectors** on **APT-Eval**, 15K samples at varying AI-involvement levels, and
  finds detectors "frequently flag even minimally polished text as AI-generated, struggle to
  differentiate between degrees of AI involvement, and exhibit biases against older and smaller
  models." We no longer need Karr or ARB to carry this item.
- **The multi-attribute fairness study is real and is Tier A.** *Identifying Bias in Machine-generated
  Text Detection* ([2026.acl-long.109](https://aclanthology.org/2026.acl-long.109/)): student essays,
  **16 detection systems**, four attributes — gender, race/ethnicity, English-language-learner status,
  economic status — with regression and subgroup analysis. Biases are "generally inconsistent across
  systems", **ELL essays are more likely to be classified machine-generated**, and **non-White ELL
  essays are disproportionately classified as machine-generated relative to their White counterparts**.
  This was previously in our documents as a Tier-C lead; it is now read at source.
- **And its most useful finding is one nobody quotes: humans are worse at this task but fairer.** The
  same paper's human annotation shows people "perform generally poorly at the detection task" yet
  "show no significant biases on the studied attributes." A human reader is the *less accurate and
  less discriminatory* option — which is a different argument from the one usually made in either
  direction.
- **Detector failure under domain shift has a peer-reviewed theoretical account.** DivScore
  ([2025.emnlp-main.971](https://aclanthology.org/2025.emnlp-main.971/)) shows zero-shot detector
  failure in specialized domains "is fundamentally linked to the KL divergence between human,
  detector, and source text distributions." That is the composite-null intuition, published and
  refereed, and it lets the roadmap drop its reliance on the arXiv-only preprint.
- **Our own bundled detectors are named in a practical evaluation.** *A Practical Examination of
  AI-Generated Text Detectors* ([2025.findings-naacl.271](https://aclanthology.org/2025.findings-naacl.271/))
  tests RADAR, Fast-DetectGPT and Binoculars — three we ship — on unseen domains, and reports
  **TPR@1%FPR as low as 0%**.

### ✗ Two of our positions are wrong or overstated

**1. The non-native bias result is not universal.** *Different Time, Different Language: Revisiting the
Bias Against Non-Native Speakers in GPT Detectors*
([2026.eacl-srw.20](https://aclanthology.org/2026.eacl-srw.20/)) repeats the Liang test in Czech and
finds **the perplexity of non-native Czech text is not lower than native**, **no systematic bias across
three detector families**, and that contemporary detectors "operate effectively without relying on
perplexity." It is a student-research-workshop paper on one language, so it does not overturn Liang —
but our documents present non-native bias as a settled universal, and it is not. It is
**language-, era- and detector-specific.**

That is a disconfirmation, and it makes the argument *stronger* rather than weaker: if bias appears in
English TOEFL essays and ICNALE data but not in Czech, then bias is a property of a particular
population meeting a particular detector — which is exactly why it has to be measured locally instead
of assumed from a citation. This is the first Tier-A evidence we have for the composite-null
conclusion arriving from a *negative* result.

**2. Watermark removal is harder than we implied.** *Sandcastles in the Storm: Revisiting the
(Im)possibility of Strong Watermarking* ([2025.acl-long.1436](https://aclanthology.org/2025.acl-long.1436/))
tests the random-walk erasure argument empirically: mixing is **slow** — 100% of perturbed texts retain
traces of origin after hundreds of edits — quality oracles misjudge edits (77% accuracy), and automated
attacks remove watermarks **just 26% of the time, dropping to 10% under human quality review**.

Reconciled with SynGuard's Tier-A degradation table, the honest position is a distinction we were not
drawing: **watermark *detectability degrades* under ordinary editing (F1 1.000 → 0.714 under
re-translation), while *complete removal* is much harder than theory predicts.** Those are different
claims and both are true. It makes the Article 50 audit *more* attractive, not less — a mark that
mostly survives is worth measuring precisely.

**3. And no detector wins everywhere.** *Watermark vs. Automatic Detection*
([2026.acl-industry.9](https://aclanthology.org/2026.acl-industry.9/)) sweeps six Qwen sizes, six
watermarking schemes, two automatic detectors, three obfuscation methods and two datasets: "there is no
detector that consistently outperforms on all scenarios."

## Corpora this pass found that we did not have

| Corpus | What it is | Source |
|---|---|---|
| **APT-Eval** | 15K samples at graded AI-polishing levels, 12 detectors | [2025.findings-acl.1303](https://aclanthology.org/2025.findings-acl.1303/) |
| **MixSet** | First dedicated mixed human/AI corpus (AI-revised HWT and human-revised MGT) | [2024.findings-naacl.29](https://aclanthology.org/2024.findings-naacl.29/), [code](https://github.com/Dongping-Chen/MixSet) |
| **FAIDSet** | Multilingual, multi-domain, multi-generator; human / LLM / collaborative, plus generator family | [2026.eacl-long.151](https://aclanthology.org/2026.eacl-long.151/), [code](https://github.com/mbzuai-nlp/FAID) |
| **HERO's four-way split** | human / machine-generated / machine-**polished** / machine-translated, length-robust | [2025.findings-emnlp.812](https://aclanthology.org/2025.findings-emnlp.812/) |
| **CoCoNUTS** | 315,535 peer reviews, six human-AI collaboration modes; 3.89% FPR on permissible polishing | [2026.acl-long.1240](https://aclanthology.org/2026.acl-long.1240/) |
| **ICNALE-based bias study** | Gender, CEFR proficiency, academic field, language environment, ANOVA + WLS | [2025.acl-long.1292](https://aclanthology.org/2025.acl-long.1292/) |
| **Multi-dialectal hybrid corpus** | 693 participants, five English dialects, paired within-individual over four weeks | [2026.lrec-1.882](https://aclanthology.org/2026.lrec-1.882/) |

That last one also nuances §2 of the map: it finds LLM assistance **raises lexical diversity without
raising syntactic complexity** — homogenization is not uniform across linguistic dimensions.

**Net effect on the verification problem:** the strategy no longer depends on any arXiv-only preprint.
Every load-bearing claim now has a peer-reviewed source read at source. The unreachable preprints
remain listed as leads, and nothing rests on them.

---

# Round four — the PubMed pass, and the number that settles the argument

Round three covered NLP venues. It did not cover the medical, education and publishing literature,
where these tools are actually deployed. This round searched PubMed systematically and read the
high-precision intersection at source.

## Measured false-positive rates on genuine human writing, all Tier A

Assembled from studies that each report a false-positive rate on text known to be human:

| Setting | Detectors | Measured FPR on human text | Source |
|---|---|---|---|
| Undergraduate anatomy essays, **4 detectors in aggregate** | 4 | **~0%** | PMID 40105702, [DOI](https://doi.org/10.1152/advan.00235.2024) |
| Same study, individual detectors | 4 | **1.3%** | same |
| Same study, **human raters** | 9 raters | **5.0%** | same |
| *J. Craniofacial Surgery* manuscripts from **2014** — necessarily pre-LLM | ZeroGPT | **8.6%** | PMID 41474280, [DOI](https://doi.org/10.1097/SCS.0000000000012366) |
| Behavioral-health articles 2016–18, free detector | 1 | **27.2%** (median) | PMID 38516933, [DOI](https://doi.org/10.1080/08989621.2024.2331757) |
| Scholarly abstracts, **flagged by ≥1 of 3 tools** (FAR) | 3 | **44.44%** | PMID 40989485, [DOI](https://doi.org/10.7717/peerj-cs.2953) |
| TOEFL essays by non-native writers | 7 | **61.3%** | PMID 37521038, [DOI](https://doi.org/10.1016/j.patter.2023.100779) |

**That is the same technology, on genuine human writing, ranging from about 0% to 61%.** Not a
disagreement between studies — every row is a correct measurement of a different population, domain,
detector set and aggregation rule.

**This is the argument for this repo, and it no longer needs a theory to make it.** A published
false-positive rate is not transferable. An institution that reads "1.3%" in a physiology journal and
deploys against ESL applicants has imported a number from the wrong end of a 47× range.

## The most actionable finding in four rounds: aggregation is the lever

Hyatt et al. (PMID 40105702, [DOI](https://doi.org/10.1152/advan.00235.2024)) tested 190 students'
hand-written essays against AI-generated answers to the same prompt. Individual detectors produced
1.3% false positives; **used in aggregate — requiring consensus — the false-positive rate fell to
nearly 0%**, validated against human-rater-labelled false positives.

✗ **This cuts against how untell currently reports.** Our `max` aggregation is the *union* rule: it
flags if **any** detector flags, which is precisely the FAR that Pratama measured at 44.44%. It is the
correct choice as the rewrite loop's *stop target* — beating the hardest detector is the honest bar —
and it is the **worst possible choice as a verdict**, because it maximises false accusations by
construction.

**What untell should report is the spread, not a number:**

| Rule | Meaning | Published anchor |
|---|---|---|
| **FAR** — union | flagged by ≥1 detector | 44.44% (Pratama) |
| **MFAR** — majority | flagged by most detectors | 4.17% (Pratama) |
| **Consensus** — unanimous | flagged by all | ~0% (Hyatt) |

The gap between those three rows *is* the institution's policy decision, and no tool currently puts
it in front of them. That is a concrete product change, derived from refereed measurement.

## A ground-truth probe we should steal

Bohler et al. (*J Craniofac Surg*, [DOI](https://doi.org/10.1097/SCS.0000000000012366)) analysed
**1,490 manuscripts**, 659 from **2014** and 831 from 2024. Because 2014 text
is necessarily pre-LLM, **its detector score is pure false-positive signal: a mean of 8.6% detectable
AI content per manuscript** (SD 9.8). ✗ Round twenty corrected this line: an earlier version called
it "a pure false-positive rate", which it is not — it is the mean *percentage of text within a
manuscript* scored as AI, not the share of manuscripts flagged. The authors
conclude the modest rise to 10.7% "likely reflect[s] detection software behavior and evolving writing
structure rather than widespread use of generative AI."

Two things follow. First, **scoring a pre-2022 corpus is the cleanest FPR probe available** — no
labelling, no ambiguity, unfalsifiable ground truth — and untell should ship it as an arm. Second,
**it puts a caveat under §1 of the literature map**: prevalence estimates derived from detectors are
partly measuring the detector, which is why the excess-vocabulary method (Kobak) is the more
trustworthy family.

## The evidence is not uniformly anti-detector, and saying so matters

Round three found a Czech replication showing no non-native bias. This round finds detectors at 1.3%
individually and ~0% in aggregate on STEM student writing, **outperforming human raters at 5.0%**, and
expert radiology editors identifying AI-written editorials only 58–70% of the time (PMID 39288967,
[DOI](https://doi.org/10.3174/ajnr.A8505)) while showing a positive bias toward text they believed
human-written.

A document that only collected anti-detector findings would have missed all of this. The honest
position — and the stronger one — is that **detectors are neither reliable nor useless in general,
because "in general" is not a property they have.** Everything depends on the deployment, which is
exactly what this repo exists to measure.

---

# Round five — the AI-writing side, which the first four rounds never mined

Rounds three and four searched the corpus for *detection*. The original question was about **AI
writing**, and that half had only been covered by targeted search. Re-mining the same 28,120 abstracts
found **174** papers on writing assistance and **509** touching diversity or creativity; the 25 that
report diversity, ownership or cognitive *effects* were read.

## ✅ The finding that should frame the entire product

*Human Bias in the Face of AI: Examining Human Judgment Against Text Labeled as AI Generated*
([2025.findings-acl.1329](https://aclanthology.org/2025.findings-acl.1329/)). Three experiments —
rephrasing, news summarization, persuasive writing:

- In the **blind** test, raters **could not tell the two apart**.
- Shown labels, they favoured text marked "Human Generated" over "AI Generated" by a preference score
  of **over 30%**.
- **The same pattern held when the labels were deliberately swapped.**

**The label drives the judgment, not the text.** A detector's output *is* a label. So a false positive
does not merely risk being wrong — it changes how every subsequent human reads that work, in a
direction the text itself cannot correct.

This retires the standard mitigation. "A human will review the flag" is not a safeguard, because the
reviewer has already been anchored by the flag. And it sharpens round three's result that humans are
poor detectors but show *no significant bias*
([2026.acl-long.109](https://aclanthology.org/2026.acl-long.109/)): **humans are unbiased until you
show them a label — which is exactly what deploying a detector does.**

For this repo that is the ethical case for the whole enterprise, stated by someone else's experiment:
the cost of a false positive is not a corrected mistake, it is a permanently altered reading.

## ✅ Homogenization, measured inside our own field — and a genuine disagreement

*What Are LLMs Doing to Scientific Communication?* ([2026.lrec-1.142](https://aclanthology.org/2026.lrec-1.142/))
builds a naturalistic corpus of **over 37,000 ACL Anthology papers (2020–2024)** plus 3,000
human-written passages with LLM improvements. LLM-modified texts contain "more complex and longer
words and **a lower lexical diversity**." A pilot study with **20 domain experts** rates LLM-improved
text as **more understandable and exciting** while the same experts express negative qualitative
attitudes toward LLMs.

*Quantifying the Risks of LLM- and Tool-assisted Rephrasing to Linguistic Diversity*
([2025.findings-emnlp.1228](https://aclanthology.org/2025.findings-emnlp.1228/)) takes the same
question to a multi-domain corpus, measuring semantic and vocabulary change from rephrasing tools
across a large user base rather than for individuals.

⚠️ **These do not agree with the dialect corpus.** [2026.lrec-1.882](https://aclanthology.org/2026.lrec-1.882/)
(693 participants, five English dialects, paired within-individual over four weeks) found LLM
assistance **raises** lexical diversity without raising syntactic complexity. Two refereed studies,
opposite signs on lexical diversity.

The likely reconciliation is level-of-analysis — an individual's vocabulary can widen while the
*population's* collective vocabulary narrows, which is precisely the individual-vs-collective
distinction the *Nature Human Behaviour* study draws. But that is our inference, not a published
finding, and §2 of the literature map should stop presenting homogenization as a single settled
direction. It is settled at the population level and contested at the individual level.

## Also worth having

- **ScholaWrite** ([2026.acl-long.1606](https://aclanthology.org/2026.acl-long.1606/)) — ~62K LaTeX
  edits from five CS preprints over four months, annotated with cognitive writing intentions. Real
  end-to-end human writing process data, and current LLMs "struggle to provide meaningful support
  throughout" it.
- **Keystroke logging of English learners** ([2024.lrec-main.938](https://aclanthology.org/2024.lrec-main.938/))
  — process-level data, which is the one evidence type that could establish authorship without a
  detector at all.


---

# Verification standard — decided, not defaulted

Five rounds established what this environment can and cannot reach. The residual — five arXiv-only
2026 preprints behind an organization egress policy — was put to the repository owner on 2026-09-01
with the options of accepting the standard, unblocking arXiv access, extending coverage elsewhere, or
moving to implementation.

**Decision: accept the current standard.** So this is the bar these documents are held to, and a
future contributor should hold them to the same one rather than guessing:

1. **Every claim a decision rests on is read at source** — a publisher, PubMed/PMC, the ACL
   Anthology's own metadata, or the authors' repository. The verified set and the load-bearing set
   are the same set.
2. **Corroborated-but-unread claims are marked and carry no decision.** They appear as leads, with
   the tier stated inline.
3. **Disconfirming evidence is recorded beside the evidence it disconfirms.** Five separate results
   in these rounds cut against positions the repo had taken, and all five are in the documents: the
   Czech non-bias replication, Sandcastles on watermark durability, aggregate detectors beating human
   raters, the individual-vs-population disagreement on lexical diversity, and the two corrections to
   claims we had already published.
4. **Coverage is stated as a boundary, never as completeness.** What was searched: 28 ACL Anthology
   volumes (28,120 abstracts, 2023–2026) and PubMed. What was not: arXiv-only preprints, and any
   venue indexed by neither.

## The survey is a tool, not a claim

The count this document argues from — under 2% of ACL detection papers on false positives or
fairness, against ~30% on evasion robustness — ships as
[`eval/litreview.py`](https://github.com/ssamba1/untell/blob/main/eval/litreview.py) rather than as a
number a reader has to trust:

    python -m eval.litreview --download          # fetch Anthology volume metadata (~67 MB)
    python -m eval.litreview                     # reproduce the table
    python -m eval.litreview --topic fairness    # list the papers behind one row

It reproduces `28120 abstracts indexed; 397 detection-related` with robustness at 29.2% and false
positives and fairness at 1.8% each. `tests/test_litreview_reproduces_the_published_counts.py` pins
the classifier so an edited pattern cannot silently turn a real count into an honest-looking zero.

**This is the answer to the coverage limit, and the reason the bounded standard is defensible.**
Coverage here stops at the Anthology and PubMed because of an egress policy. Shipping the method
means the next person to run it — on a machine without those restrictions, over more venues, or with
a different topic taxonomy — *extends* the survey instead of repeating it. A bounded survey that can
be re-run and widened is worth more than an unbounded claim that cannot be checked at all.

### The PubMed half, reproducible as data rather than as code

`eval/litreview.py` makes the Anthology survey re-runnable. The PubMed half cannot ship the same way:
`eutils.ncbi.nlm.nih.gov` is blocked here too, so a PubMed code path could be written but **not
tested**, and this repo does not ship unverified code. The reproducible form is therefore the queries
themselves, together with the result each one MEASURED against PubMed on 2026-09-01, so anyone can
re-run them and see whether the corpus has moved:

| Query | Returned | Screened to |
|---|---|---|
| `excess vocabulary LLM-assisted writing biomedical abstracts Kobak` | 1 | PMID 40601754 |
| `GPT detectors biased against non-native English writers` | 1 | 37521038 |
| `shrinking landscape linguistic diversity large language models` | 1 | 42637911 |
| `homogenizing effect large language models human expression thought` | 1 | 41820108 |
| `accuracy bias trade-offs AI text detection tools fairness scholarly publication` | 1 | 40989485 |
| `AI detection risks undermining academic integrity` | 4 | 42443434, 40420142, 39939423 |
| `(AI-generated text detection OR AI detector OR ChatGPT detection) AND (accuracy OR false positive OR reliability)`, 2024– | **1408** | too broad to screen exhaustively — narrowed below |
| `"AI detector"[Title/Abstract] AND (bias OR fairness OR "false positive")[Title/Abstract]` | 3 | 40105702, 39288967, 38516933 |
| `detection of AI-generated text[Title] AND (tools OR detectors OR classifiers)`, 2024– | 2 | 41474280, 39628838 |

**The 1,408 is the honest edge of this half.** A broad query returns more than can be read, so the
PubMed pass is high-precision rather than exhaustive: tight queries, every hit read at source. That
is a screening strategy, not a systematic review of PubMed, and it is labelled as one here so nobody
mistakes the difference.

### Proof that the remaining channel is closed, not merely untried

"I could not reach it" is a claim like any other, so it was tested rather than asserted. Twelve
routes, all refused:

| Route | Result |
|---|---|
| `arxiv.org`, `export.arxiv.org` — WebFetch and curl | 403 at the gateway |
| `aclanthology.org`, `nature.com`, `science.org`, Springer, `europepmc.org` | 403 |
| `api.semanticscholar.org`, `api.openalex.org`, `api.crossref.org`, `core.ac.uk`, `openreview.net` | 403 |
| `huggingface.co`, `digital-strategy.ec.europa.eu`, `artificialintelligenceact.eu` | 403 |
| `eutils.ncbi.nlm.nih.gov` (direct E-utilities) | 403 |
| `*.github.io` | unreachable |
| `api.github.com` | gated to session-scoped repositories |
| GitHub code search | requires authentication |
| arXiv daily-mirror repositories on GitHub | stale or off-topic (time-series, CV) |
| Awesome-list / survey reading-list repositories | do not carry the papers |
| **PyPI / npm (they bypass the proxy entirely, per `noProxy`)** | **reachable — 200** |
| **The official `arxiv` PyPI client, installed and run** | **installs, then `ProxyError` on `export.arxiv.org`** |

That last pair is the decisive test. Package registries *are* reachable, so a client can be
installed — and it still cannot fetch, because the block is on the destination host rather than on
the tooling. **No client, library or package can route around it**, which is also why none should be
attempted: the proxy's own documentation says to report policy denials rather than work around them.

The channel is closed. What was reachable — PubMed/PMC, the ACL Anthology's own metadata, and
authors' repositories — was used to exhaustion instead.

The three papers worth an outside read if anyone ever has unrestricted access remain, in order:
**arXiv:2603.20254**, **arXiv:2608.11256**, **arXiv:2607.29539**.

**What this standard is not.** It is not a claim to have validated the world's research on AI
writing. No process does that, and a document claiming it would be exactly the kind of unfalsifiable
assertion this repository exists to argue against. It is a claim that the strategy in
[`../ROADMAP.md`](https://github.com/ssamba1/untell/blob/main/ROADMAP.md) rests only on evidence that
was read, that the evidence against it was sought and kept, and that the boundary of the search is
written down.


---

## Limitation on everything measured in this session

The measurements added alongside this research — the pre-LLM false-positive probe, the length curve,
the assisted-fairness arm, the calibrated threshold — were all produced with **exactly one detector
live**. `perplexity_burstiness` is the only member that runs without model weights, and the ML
detectors fetch theirs from HuggingFace, which this environment's egress policy blocks. `--tier full`
therefore resolved to the same single detector as `--tier lite` throughout.

So: **every rate reported from this session is a single-detector rate**, and the aggregation spread
that the strategy identifies as the highest-leverage output has not been measured here even once.
The tools say so themselves — `probe` reports `detectors_scoring`, and the renderer prints an
explicit note that three identical rows are one measurement printed three times rather than
consensus — but a reader meeting the numbers second-hand would not know it, so it is stated here too.

This does not weaken the argument; it is an instance of it. A false-positive rate is a property of a
detector, a population, a domain and an aggregation rule, and "measured on our ensemble" is one of
those coordinates. Re-run on a machine with the full tier installed before quoting any of these as
ensemble figures.


---

## Regression check on the work shipped alongside this research

Claiming "no regressions" without measuring it would be the same error this document exists to
catch. Measured by running every module that fails in this environment against both this branch and
`main`, in a `git worktree`, under an identical dependency set, and diffing the failing test IDs:

    BRANCH ids: 32
    BASE ids:   32
    only on branch (regressions): (none)
    only on base  (fixed here):   (none)

The failing set is identical, so the changes introduce nothing and repair nothing. Those 32 are
environmental — meaning gates and back-translation need models from a blocked host.

**The check earned its cost immediately.** It caught one real defect: a row here describing
DetectRL-X's generators as `<digit> commercial LLMs` tripped `test_docs_claims`, whose regex reads a
number followed by that word as a claim about *this repo's* own detector count. Reworded rather than
loosening the regex — that guard catches genuinely stale counts, and widening it for one document's
convenience would trade a real check for a comfortable one.

**And then this paragraph tripped it too.** Describing the incident reproduced the trigger, because
the pattern spans a line break and `\s` matches newlines — so the sentence documenting the fix
re-broke the guard. It is written with a placeholder above for that reason. A guard strict enough to
catch its own post-mortem is working, and the correct response is still to write around it rather
than to widen it.

### And an environment audit that should have come first

A large share of the suite was never running. `rich`, `fastapi`, `httpx`, `huggingface_hub` and
`spacy` are all installable from hosts this environment permits — PyPI bypasses the proxy entirely,
and spaCy's models are on GitHub releases. Installing them took collection errors from 11 to 4 and
**activated roughly 413 named-entity tests that had been skipping silently** — MEASURED as the
difference in collected tests before and after the install.

Every measurement reported above was correct for the environment it ran in. The environment was just
narrower than assumed, and nothing checked. `CONTRIBUTING.md` now documents the trap.

---

# Round six — the venue I missed, and what it changes

The survey sampled 28 Anthology collections. **The Anthology holds roughly 1,700.** Probing venue
names rather than assuming took it to **98 volumes, 33,053 abstracts, 536 detection papers**
(MEASURED by `python -m eval.litreview --download --json`; two of those volume names turned out not
to exist — see round fifteen) — a
3.5× expansion — and among the additions was **`2025.genaidetect`: an entire COLING workshop on
detecting AI-generated content**, 45 papers, the single most on-topic venue that exists. Missing it
was the largest coverage failure in this whole effort.

**The headline ratio survived the expansion**, which is the strongest evidence yet that it is real
rather than an artefact of which volumes were sampled:

| topic | round 3 (28 vols) | round 6 (98 vols) |
|---|---|---|
| robustness / paraphrase | 102 (30.6%) | **139 (25.9%)** |
| false positives | 6 (1.8%) | **13 (2.4%)** |
| fairness / non-native bias | 5 (1.5%) | **8 (1.5%)** |

## ✅ The finding that most directly concerns this repo

**SilverSpeak** ([2025.genaidetect-1.1](https://aclanthology.org/2025.genaidetect-1.1/)) attacks
seven detectors with homoglyph substitution ('A' → Cyrillic 'А') across five datasets. The detectors
include **Binoculars, Fast-DetectGPT, DetectGPT, Ghostbuster, OpenAI's detector and watermarking** —
two of which this repo ships. The result: **mean Matthews correlation falls from 0.64 to −0.01**,
with detectors driven to classify *every* text as one class.

Two consequences, and the second is the one we had not stated:

1. It is peer-reviewed confirmation that `untell/attacks/unicode_tricks.py` implements an attack that
   dismantles the detectors in our own tier list.
2. **It makes the hidden-character scrubber a precondition for auditing, not a side feature.** If a
   handful of homoglyphs can pin a detector to a constant, then any false-positive rate measured on
   unscrubbed text is measuring the text's encoding as much as the detector. The README sells
   scrubbing as a Trojan-Source hygiene feature; it is also the thing that makes every other number
   in an audit meaningful.

## ✅ And the evidence that cuts hardest *against* the pessimistic reading

**GenAI Content Detection Task 3** ([2025.genaidetect-1.45](https://aclanthology.org/2025.genaidetect-1.45/))
ran on RAID across many domains and generators, all seen during training: **multiple teams exceeded
99% accuracy while holding a 5% false-positive rate.** Task 2
([2025.genaidetect-1.37](https://aclanthology.org/2025.genaidetect-1.37/)) saw top systems above
**0.98 F1** on academic essays in English and Arabic.

Detection *in distribution* is close to solved. Which is exactly the thesis, stated from the other
side: these systems were trained on the domains and generators they were tested on, and the failures
this repo documents all live outside that condition — unseen generators, edited text, homoglyphs,
another population. **"Does this detector work?" has no answer; "does it work here?" has a good one.**

## ✅ Two more that change existing text

- **DAMAGE is peer-reviewed**, not the preprint our earlier notes called it
  ([2025.genaidetect-1.9](https://aclanthology.org/2025.genaidetect-1.9/)): 19 humanizer tools
  studied, many detectors shown to fail on humanized text, and a detector that survives an attack
  the authors mount against their own model.
- **Humans are below chance when they are not the interrogator.**
  [2025.genaidetect-1.7](https://aclanthology.org/2025.genaidetect-1.7/) ran displaced and inverted
  Turing tests: displaced human judges *and* GPT-3.5/GPT-4 judges were **less accurate than
  interactive interrogators and below chance overall**, and all three judged the best GPT-4 witness
  human *more often than they judged actual humans human*. Combined with round five's label-effect
  result, "a person will review the flag" is not a safeguard in either direction: reviewers are
  below chance, and once they see a label they follow it.
- **Fingerprints explain the generator-bound result.**
  [2025.genaidetect-1.6](https://aclanthology.org/2025.genaidetect-1.6/) finds n-gram and
  part-of-speech classifiers robust in *and* out of domain, with per-model-family fingerprints that
  transfer within a family (13B LLaMA ≈ 65B LLaMA) and not across.

**Method note.** `eval/litreview.py` now carries all 98 volumes, so the expanded survey re-runs with
`python -m eval.litreview --download`. The lesson is the ordinary one: the gap was not in the
literature or in the access policy, it was in assuming a sample was the population.

---

# Round seven — the census, and three claims it retires

Round six sampled 98 volumes and called that thorough. It was still a sample. A partial clone of the
Anthology (`git clone --filter=blob:none --sparse`, then `sparse-checkout set data/xml`) gives the
**complete file list: 1,718 volumes, 181 MB**. Surveying all of it:

**82,352 abstracts. 763 detection papers.** Not a sample of the ACL Anthology — the whole of it,
1952 to 2026.

| topic | papers | share |
|---|---|---|
| robustness / paraphrase | 164 | 21.5% |
| human–AI mixed / edited | 73 | 9.6% |
| education / integrity | 49 | 6.4% |
| watermark | 33 | 4.3% |
| **false positives / accusation** | **20** | **2.6%** |
| calibration / thresholds | 19 | 2.5% |
| **fairness / non-native bias** | **13** | **1.7%** |

The ratio has now survived three expansions (28 → 98 → 1,718 volumes) and barely moved. **Across the
entire published history of the field, twenty papers concern detector false positives and thirteen
concern fairness.** That is a census, not an estimate.

## ✗ Three "nobody does this" claims, retired

Reading the newly visible papers cost this repo three differentiators it had been claiming. All three
were stated in earlier rounds and all three were wrong.

**1. "The stratified auditing protocol is specified in the literature and nobody ships it."**
**BAID** ([2026.customnlp4u-1.1](https://aclanthology.org/2026.customnlp4u-1.1/)) is a bias-assessment
benchmark for AI detectors with targeted datasets across **seven categories — demographics, age,
educational grade level, dialect, formality, political leaning and topic** — evaluating four
open-source detectors and offering itself explicitly as "a scalable, transparent approach for
auditing AI detectors". That is the audit, built. What remains ours is narrower and should be stated
narrowly: **BAID is a fixed benchmark with its own corpora; untell points at yours.** A benchmark
tells an institution how detectors behave on BAID's texts, which by this repo's own central argument
is not transferable to that institution's population.

It also carries a finding that runs against our framing: the disparity it measures is **low recall
for underrepresented groups** — under-detection — not only the over-flagging the ELL literature
emphasises. Bias in these systems is not all in one direction.

**2. "Bounded per-subgroup false-positive rates are an idea nobody has formalised."**
[2025.aimecon-sessions.13](https://aclanthology.org/2025.aimecon-sessions.13/) proposes exactly that:
a detection objective based on **bounded group-wise false alarm rates**, derives the optimal
detection policy under it, and compares it to a standard likelihood-ratio test. It comes from test
security and psychometrics rather than NLP, which is why our NLP-shaped searches never surfaced it.
It is the formal statement of what §7's calibration item builds informally, and it should be cited
rather than reinvented.

**3. "Calibrating on pre-LLM text is a probe we should steal from a medical-journal study."**
[2024.wikinlp-1.12](https://aclanthology.org/2024.wikinlp-1.12/) does it properly and earlier: it
calibrates GPTZero and Binoculars **to a 1% false-positive rate on pre-GPT-3.5 Wikipedia articles**,
then reports that **over 5% of newly created English Wikipedia articles** trip the resulting
threshold, with lower rates in German, French and Italian. That is our `eval/pre_llm_fpr.py` method,
independently, with the calibration step included — and it is a better citation for the technique
than Bohler et al., because it calibrates rather than merely measuring.

## ✅ One finding that sharpens a claim rather than retiring it

[2025.aimecon-sessions.11](https://aclanthology.org/2025.aimecon-sessions.11/) trains eight detectors
on standardized English-proficiency essays across GPT-3.5 and GPT-4 generations. Detectors trained on
one generator **misclassify the other generator's essays as human — false negatives — but do not
produce more false positives on human essays.**

So generator mismatch costs *recall*, not precision. That is a real constraint on how far the
"detection is generator-bound" argument reaches: an unseen generator makes a detector miss AI text,
it does not by itself make it accuse more humans. Our §7 wording should not blur the two.

**Method note.** The complete-corpus route is a partial clone rather than the volume list in
`eval/litreview.py`, which remains the reproducible sample. Both are documented; the clone is the
census.

---

# Round eight — screening all 763 detection papers against *this repo's* claims

Earlier rounds read papers by topic cluster, which is a way of finding what you went looking for. This
round screened every one of the 763 detection papers in the census against the claims **this
repository makes**, rather than against generic topics:

| claim this repo makes | papers bearing on it |
|---|---|
| ensembles / aggregation effects | 63 |
| paraphrase or rewriting defeats detection | 51 |
| evasion transfers to unseen detectors | 41 |
| perplexity and burstiness are the signal | 16 |
| em-dash and lexical tells | 16 |
| short text is unreliable | 15 |
| watermarks are fragile | 15 |
| commercial detector claims | 10 |
| humans cannot detect | 3 |

## ✅ A claim already published here, confirmed verbatim — and upgraded

`humanizer-research-report.md` cites MASH from preprint 2601.08564 as "92% ASR across 5 detectors /
6 datasets, beat 11 baselines, quality preserved, no white-box access."

It is **peer-reviewed** — [2026.findings-acl.1487](https://aclanthology.org/2026.findings-acl.1487/) —
and the published abstract confirms every part: "across 6 datasets and 5 detectors… over 11 baseline
evaders… an average Attack Success Rate (ASR) of 92%… while maintaining superior linguistic quality."
It adds one figure we did not have: **it beats the strongest baseline by an average of 24%.** The
citation is updated from preprint to venue.

## ⚠️ The finding that most constrains how this repo states its headline

untell's headline negative result is that its loop "moves the detectors it optimises against, and
**does not move a detector it has never seen**." That is measured and true *of untell*. The screen
shows it must not be read as a statement about evasion in general, because transfer is repeatedly
demonstrated by stronger methods:

- **RAFT** ([2024.emnlp-main.939](https://aclanthology.org/2024.emnlp-main.939/)) — a grammar-error-free
  black-box word-level attack that "effectively compromises **all detectors** in the study across
  various domains **by up to 99%**", is **transferable across source models**, and whose outputs human
  raters found "realistic and indistinguishable from original human-written text."
- **MASH** — 92% ASR black-box across 5 detectors, no white-box access.
- **Evasive soft prompts** ([2023.findings-emnlp.94](https://aclanthology.org/2023.findings-emnlp.94/))
  — explicitly exploits "the transferability of soft prompts to transfer the learned evasive soft
  prompt from one PLM to another."

So the honest framing, which the README mostly keeps and should keep strictly: **non-transfer is a
property of this repo's CPU-only black-box loop, not a property of evasion.** Anyone reading
"does not move a detector it has never seen" as evidence that detectors are safe from transfer
attacks has been misled, and the three results above are the correction.

RAFT also reports the constructive half, which belongs beside it: its adversarial examples **can be
used to train adversarially robust detectors.**

---

# Round nine — reading the clusters I had only counted

Round eight screened all 763 papers against this repo's claims and then read one cluster. This round
reads the rest. Four results change what this repository says.

## ✗ "Humans cannot reliably detect AI text" — the strongest correction in this ledger

Every round so far has repeated some form of it, citing ~70% for experts, 59% for students, 61% for
ESL teachers, and round six added displaced Turing-test judges performing below chance.

[2025.acl-long.267](https://aclanthology.org/2025.acl-long.267/) — *People who frequently use ChatGPT
for writing tasks are accurate and robust detectors of AI-generated text* — makes that framing
untenable as a general claim. 300 non-fiction English articles, generated by GPT-4o, Claude and o1,
labelled by hired annotators:

- Annotators who **frequently use LLMs for writing** excel at the task, "even without any specialized
  training or feedback."
- **The majority vote among five such annotators misclassifies 1 of 300 articles.**
- That "significantly outperform[s] most commercial and open-source detectors we evaluated **even in
  the presence of evasion tactics like paraphrasing and humanization**."

So the honest statement is not "humans cannot detect" but **"most humans cannot; frequent LLM users
voting as a panel outperform every detector tested, including under evasion."** The variable is
familiarity, not humanity.

**And note what makes the panel work: majority vote.** The same aggregation rule that takes detector
false accusations from 44.44% to 4.17% takes human error to 1-in-300. This repo has been arguing that
the aggregation rule matters more than the detector; it turns out to matter more than the *species*.

The earlier findings survive alongside it rather than being replaced — displaced judges are still
below chance ([2025.genaidetect-1.7](https://aclanthology.org/2025.genaidetect-1.7/)), the label
still drives the verdict ([2025.findings-acl.1329](https://aclanthology.org/2025.findings-acl.1329/)),
and professional translators were "inconclusive" on average with 16.2% significantly right and
nearly as many significantly wrong ([2026.eamt-1.35](https://aclanthology.org/2026.eamt-1.35/)). What
changes is that "a human will review the flag" fails for an *arbitrary* reviewer and can succeed for a
panel of the right ones.

## ✅ The repo's `ai_vocab` measurement, independently confirmed — and explained

`untell/scripts/tells.py` measures `ai_vocab` — the "delve / leverage / tapestry" cluster this whole
product category is famous for — at **0.615 precision on HC3 and 0.585 on RAID**: a coin flip.

[2025.bea-1.71](https://aclanthology.org/2025.bea-1.71/) evaluates GPTZero's *AI Vocabulary* feature
on the Ghostbuster essays and finds it works on ChatGPT-generated text but **drops to near-random on
Claude-generated essays**, concluding it "may not generalize well to texts generated by LLMs other
than ChatGPT."

That both confirms our number and supplies the mechanism we lacked: the cluster is not weak in
general, it is **generator-specific**, and HC3 and RAID span generators. It also hands us a concrete
method note — the paper finds that checking **presence rather than frequency** of AI terms performs
best, which is not how a rate-per-100-words catalogue counts them.

## ⚠️ Tell catalogues decay once published — including ours

[2025.findings-acl.657](https://aclanthology.org/2025.findings-acl.657/) — *Human-LLM Coevolution* —
tracks arXiv abstracts and reports a **marked drop in "delve" beginning soon after it was publicised
as an AI marker in early 2024**, while other ChatGPT-favoured words such as "significant" kept rising.
Authors are selecting and editing outputs in response to what is known about detection.

The consequence for this repo is direct and uncomfortable: **a published tell catalogue accelerates
its own obsolescence.** `tells.py` documents 29 patterns in public. The measured lifetime of the most
famous one, after publicity, was months. Two implications worth carrying into the roadmap: tell
precision figures need a *date* attached, not just a corpus, and the categories that matter longest
are the ones nobody has advertised.

It also qualifies §1 of the literature map: excess-vocabulary prevalence estimates measure "LLM output
that authors did not edit away", which drifts downward as awareness spreads, independent of actual
usage.

## ✅ Perplexity is generator-bound too

[2024.nlpaics-1.10](https://aclanthology.org/2024.nlpaics-1.10/) finds perplexity useful as a
classification signal on M4 but "constrained by the differences among the LLMs used in the training
and test sets" — the same generator-boundedness M4GT-Bench reports for detection generally, now
established for the specific signal this repo's lite tier is built on.

---

# Round ten — auditing the citations themselves

Every round so far checked what papers *say*. None checked that the papers this repo cites **exist**.
A citation that does not resolve looks like evidence, survives review, and cannot be checked without
the corpus — the same failure as an unattributed number, one level down, and nothing guarded against
it while the research documents accumulated 122 external references.

Enumerated across every Markdown file and Python docstring in the repo:

| kind | distinct citations | verifiable here |
|---|---|---|
| ACL Anthology ids | **39** | ✅ all of them — the corpus is local |
| arXiv ids | 71 | ✗ host blocked; verified only where a venue version exists |
| DOIs | 12 | ✅ via PubMed for the indexed ones |

**Result: 39 of 39 cited Anthology identifiers resolve to real papers**, checked against an index of
**127,839 papers** built from the complete Anthology. No fabricated citation, no transposed digit.

That is now a standing check rather than a one-off:

    python -m eval.litreview --verify-citations --cache <anthology-xml-dir>

`tests/test_cited_papers_resolve.py` pins the extraction (the part that would silently break and make
the check vacuously green) and resolves for real when `UNTELL_ANTHOLOGY_CACHE` points at the volumes.
The test that matters most is the one asserting a plausible-but-fake id — `2025.acl-long.99999` — is
reported unresolved, because a checker that cannot fail is not a checker.

**What this does not cover, stated plainly:** the 71 arXiv-only citations cannot be resolved from this
environment, so "39/39" is a complete result for one citation class and silence about the larger one.
Anyone with unrestricted access can extend `verify_citations` to arXiv in a few lines; the extraction
already collects the ids.


---

# Round eleven — recovering published versions of preprint citations

Round ten resolved the 39 Anthology citations and left the 71 arXiv ones unverifiable. That was a
boundary, not a wall: **a preprint cited here may have been published since**, and the venue version
sits in the local index even though the preprint host does not.

Matching cited arXiv ids against paper titles in their surrounding text, across the 125,598-title
index, recovered two — and both were considerably thinner in our documents than in their published
form.

**1. arXiv:2605.14240 → [2025.naacl-srw.46](https://aclanthology.org/2025.naacl-srw.46/)**

Our one-line citation said it "frames the core result as a performance-vs-resilience dichotomy",
which the abstract confirms verbatim. What we did not have is the part that names our own stack: the
paper evaluates fine-tuned RoBERTa, **Binoculars**, and feature analysis with Random Forest
ensembles, and finds **"Binoculars-inclusive ensembles yield the strongest results, but they also
suffer the most significant losses during attacks."**

untell ships Binoculars. So the single strongest member of our tier is also the most attack-fragile,
by an external measurement, which is exactly the trade the dichotomy describes and a reason the
holdout arm in `eval/holdout.py` matters more than its size suggests.

**2. arXiv:2510.18774 → [2026.acl-long.663](https://aclanthology.org/2026.acl-long.663/)**

Cited here as a single clause about disclosure. Read at source it is an audit of **186K articles from
1.5K American newspapers**, and it carries four findings we had none of:

- **~9%** of newly published articles are partly or fully AI-generated, concentrated in smaller local
  outlets and in weather and technology.
- **Opinion pieces are 6.4× more likely to contain AI content than news** from the same three
  mastheads, many under prominent bylines.
- A manual audit of 100 flagged articles found **five disclosures**.
- **AI-generated articles are 8.2× more likely to contain hallucinated claims** than human-written
  news.

That last one matters beyond the citation. Everything else in this ledger connects AI authorship to
*style* — perplexity, burstiness, lexical fingerprints, register. This connects it to **factual
error**, which is a different and more consequential claim, and it is the only measurement of that
kind anywhere in these documents.

**Method note.** The match is title-in-context, so it produced three false positives from a table row
where several arXiv ids sat near one title; those were discarded by checking adjacency by hand. A
tighter implementation would bound the window. The remaining 69 arXiv citations have no Anthology
version findable this way — which means either they are unpublished, published outside the Anthology,
or published under a changed title. Only the first is verifiable from here.


---

# Round twelve — the citation-status audit, stated as numbers

The honest completeness picture for this repo's external references, rather than a sentence about
what could not be reached.

| citation class | count | status |
|---|---|---|
| ACL Anthology ids | 39 | ✅ **39/39 resolve** to real papers, checked against a 127,839-paper index |
| DOIs | 12 | ✅ resolved via PubMed where indexed; each read at source |
| arXiv ids | 66 | ✅ **16 verified through a reachable channel**; 50 not |

**The 16 are verified because the paper exists somewhere this environment can reach** — an Anthology
venue version, PubMed, or the authors' own repository:

Beemo, RAID, MCP/RealDet, the feature-inversion trap, DetectRL-X, M4GT-Bench, LitBench, Adversarial
Paraphrasing (NeurIPS 2025 + repo), SynGuard (repo, with its degradation table), Base Models Look
Human (repo; no figure quoted from it), DAMAGE, Liang et al. (PubMed), Who Writes What, paraphrase
resilience, the US-newspapers audit, shrinking diversity and the homogenizing-effect review (both
PubMed), plus *Your Brain on ChatGPT* whose preprint status was itself the thing verified.

**The 50 remaining are arXiv-only from here.** Not "unchecked out of carelessness" — checked and
found to have no reachable published version. Two of them were only recovered in round eleven by
noticing they *had* been published since we cited them, which is a reason to re-run the check
periodically rather than treat this table as final.

## ✗ A defect in the audit tool itself

The arXiv extractor scans Python files and treated **`arXiv:2301.00000`** as a citation. It is not —
it is a **format example** in `untell/scripts/preserve.py`, illustrating the modern arXiv identifier
shape so the citation-locking regex can be tested against it, and `tests/test_preserve.py` uses the
same string as a fixture.

An extractor that reports a documented regex example as an unresolvable citation would, if shipped,
generate exactly the kind of false alarm that gets a checker ignored — a failure this repo has
written about before in `untell/scripts/audit.py`. The shipped `cited_acl_ids` is unaffected because
it matches Anthology URLs only; any future arXiv extension needs a placeholder guard, and this note
is here so that lands as a requirement rather than as a surprise.

## And one consistency defect the audit caught

*Who Writes What* was cited as **arXiv:2502.12611** in `research-to-build.md` and as
**2025.acl-long.1292** in this ledger — the same paper, two identifiers, in one repository. Now cited
by venue in both places. That is the mundane defect a citation audit is actually for, and nothing
would have found it by reading.

---

# Round thirteen — the systematic PubMed screen, and the sharpest fairness result yet

Earlier PubMed work was high-precision querying. This round screened the field-specific literature
systematically. According to PubMed, a tightened query — AI-generated-text / AI-detector terms
crossed with false-positive, bias, fairness, accuracy or reliability — returns **128 records**, a
tractable set rather than the 1,408 the broad query gave.

**A finding about that corpus first: most of it is commentary, not measurement.** Editorials and
narrative reviews on publication ethics dominate the top results. The measurement papers are a
minority, which is why targeted querying found them and a broad sweep mostly returns opinion.

## ✅ The strongest statement of the H2L effect anywhere in this ledger

Du & Koga (*JAAD International*, [DOI](https://doi.org/10.1016/j.jdin.2025.10.017)), reporting on
Wang et al.'s cohort study of human-authored letters:

> "At baseline, **97% to 100% of originals were classified as human**; however, after polishing,
> **75% to 85% were flagged as AI-generated, including 15% to 25% at high confidence.**"

Karr et al. put light edits at **64–80% for Pangram and 38–49% for GPTZero** (this ledger's own
correction table says so, and an earlier version of this very sentence repeated the collapsed
"38–80%" it corrects — fixed in round twenty-two). This is **75–85%, from near-perfect baseline
accuracy**, on the same documents. Polishing your own writing is, on this measurement, close to a
coin flip away from being called a machine — and the detector was *right about those same documents*
before the polish.

## ✅ And the fairness observation that reframes the whole problem

From the same letter (Du & Koga, *JAAD International*,
[DOI](https://doi.org/10.1016/j.jdin.2025.10.017)), reading Wang et al.'s figures:

> "the AI-generated probability for **non-English-speaking authors in 2020** may exceed that for
> **U.S. authors in 2024**, a difference that predates the post-2022 rise in AI-assisted writing and
> points to a baseline pattern rather than a new effect."

**A non-native author writing in 2020 — before ChatGPT existed — can score as more AI-like than a US
author writing in 2024.** The bias against language background is larger than the signal the detector
exists to measure. Every other fairness result in this ledger reports a *rate* difference; this one
says the confound exceeds the effect.

The letter adds that at baseline, original letters from non-native authors receive fewer "human
(high)" labels than US-authored ones despite all being human-written — "consistent with sensitivity
to nativeness or fluency rather than AI-like features."

## ⚠️ A methodological warning aimed squarely at our stratification design

The same authors criticise using **US institutional affiliation as a proxy for native-English
status**: "many U.S.-affiliated authors trained or grew up in non-English environments, affiliation
alone may not capture language background," and they call for "a pre-specified sampling frame."

`eval/assisted_fairness.py` stratifies on exactly that proxy, because Pratama's corpus is built from
institutional country. **So our per-subgroup numbers inherit a misclassification the literature has
already flagged**, and the module should say so rather than presenting `Status` as ground truth about
language background. That is a documentation fix in the module, not a reason to drop the arm.

## ✅ Another pre-LLM baseline study, corroborating our probe design

Erol et al. (*Acta Neurochirurgica*, [DOI](https://doi.org/10.1007/s00701-025-06622-4)) score 250
human-authored articles **from the pre-ChatGPT era** against 750 ChatGPT-generated texts across four
neurosurgery journals, using GPTZero, ZeroGPT and Corrector App. **AUC 0.75–1.00, and "none of the
detectors achieved 100% reliability"**, with the authors noting "false positives pose risks to
researchers."

Independent use of the same design as `eval/pre_llm_fpr.py` — pre-ChatGPT text as unfalsifiable human
ground truth — now in a third field, after Wikipedia and craniofacial surgery.

---

# Round fourteen — where these tools are actually pointed at people

The education/admissions string returns 27 records and is exhausted. Reading it produced the most
consequential cluster in this ledger, because unlike almost everything else here it is not a
benchmark: **these are detectors being run against real applicants in real selection processes.**

According to PubMed:

**1. Surgical residency, 1,490 personal statements** (Subillaga et al., *J Surg Educ*,
[DOI](https://doi.org/10.1016/j.jsurg.2025.103566)). GPTZero and Copyleaks on the same documents
across two match cycles:

| | GPTZero | Copyleaks | **both agreeing** |
|---|---|---|---|
| 2022–23 | 10.2% | 2.6% | **1.7%** |
| 2023–24 | 36.6% | 22.5% | **21.2%** |

**That is the union-versus-consensus spread, measured in a live admissions process.** One tool flags
36.6% of applicants; requiring two to agree flags 21.2%. Which tool a program happened to license
changes the accused population by fourteen points.

And the flagged group differs from the unflagged one in ways that are not authorship: **non-English
native language characteristics 38.7% vs 19.6% (p<0.001)**, shorter statements, shorter sentences.

**2. Fellowship applications, 421 personal statements** (Stern et al., *J Arthroplasty*,
[DOI](https://doi.org/10.1016/j.arth.2025.07.072)). ✗ **Round twenty-one corrected how this was
stated.** The figures are **mean GPTZero scores**, not shares of statements: the pre-ChatGPT cohort
averaged **99.5% human (SD 1.9)** and the post-ChatGPT cohort **83.8% human (SD 29.9)**. The second
standard deviation is the point — **29.9 on a mean of 83.8 means the statements are not clustered
around 84% human**, but split between a majority scoring near-human and a minority scoring heavily
AI. **An average of 83.8% human does not mean 16% of statements were AI-written**, and the earlier
phrasing invited exactly that reading. And: "international medical graduates and applicants from non-US residencies
demonstrated a higher proportion of AI-generated text in their PSs compared to US applicants
(P < 0.001)."

**3. The one that should stop a deployment** (Cumbo et al., *Cureus*,
[DOI](https://doi.org/10.7759/cureus.88969)). Three detectors on 25 samples of ~700 words.
Human-written personal statements **from before ChatGPT existed** were scored as
**64–100% AI-generated**. The authors still conclude programs "may be able to detect AI use," while
noting that "the use of invalidated tools may harm honest applicants."

A pre-2022 human document scoring 64–100% AI is not a marginal false positive. It is the measurement
`eval/pre_llm_fpr.py` exists to take, arrived at independently, in the setting where the cost of being
wrong is somebody's career.

**4. And humans, again, doing well** (Goodman et al., *J Phys Ther Educ*,
[DOI](https://doi.org/10.1097/JTE.0000000000000396)). Two raters on 50 human and 50 Gemini-generated
statements: **97% and 99% accuracy, κ = 0.92**. ✗ **Round twenty-two removed a comparison here.** An
earlier version called this "above the GPTZero-derived parameters measured on the same corpus" — but
the study reports GPTZero's parameters as **areas under the ROC curve > 0.875** (and RQA at 0.768 and
0.859), and an accuracy is not an AUC. The two cannot be ranked against each other. What the study
supports is the standalone claim: **two human raters reached 97% and 99% accuracy with κ = 0.92.**
Consistent with round nine: the right humans are very good at this.

## What this cluster changes

Everything else in this ledger is a benchmark result. This is deployment, and it shows the three
things this repo argues, happening at once, to applicants who did not consent to being measured:
detector choice changes the accused population by more than a factor of two; the flagged group skews
non-native; and text that predates the technology scores as the technology.

**It is also the clearest statement of who untell is for.** Not researchers comparing detectors — the
program director who licensed one tool rather than another and has no way to know what that choice
did to their applicant pool.

**The humanizer literature is absent here.** The dedicated query returns **one** record. The arms-race
research this repo's own `humanizer-research-report.md` surveys has essentially no presence in the
biomedical and education literature, while deployment against applicants is well represented — the
people running these tools are not reading the work showing they can be evaded.

---

# Round fifteen — a documented number that no longer reproduced

Re-running `eval/litreview.py` to check a figure quoted in `docs/index.md` found three separate
defects, none of which any test would have caught.

**1. The published figure was two rounds stale.** `docs/index.md` told readers the survey re-derives
"28,120 abstracts; 102 papers on evasion robustness against 6 on false positives". Those are round
*five's* numbers — the 28-volume sample. Round six expanded the tool to 98 volumes and updated
ROADMAP and this ledger but not the index, and ROADMAP's own description of the pass still said
"16 volumes, 20,875 abstracts". **Three documents, three different counts, one tool.** All three now
carry the figure the tool actually prints.

**2. Two of the 98 volumes never existed.** MEASURED against the Anthology repository:
`2025.naacl-srw` and `2026.aacl` 404 on every run —
checked directly against the Anthology repository, while `2025.naacl` and `2025.aacl` return 200. The
volume list was a guess at names that was never verified against the source, so the tool claimed 98
volumes and could only ever fetch 96, printing two skip warnings on every run. Both are removed.
Round six's recorded **33,053 abstracts / 536 detection papers is therefore not reproducible**; the
count over the 96 volumes that exist is **31,387 abstracts / 526 detection papers**, MEASURED by
`python -m eval.litreview --download --json`. The ratio is
unchanged, which is the third time this ratio has survived a change to the corpus under it.

**3. A truncated download was silently counted as a whole volume.** The first re-run lost
`2025.findings` to an `IncompleteRead` and printed **27,993 abstracts** — a plausible-looking total
that was **3,394 abstracts short** of the 31,387 the same command MEASURED once the volume
downloaded intact — with the loss visible only as one warning line above the JSON. The
200-byte floor did not catch it because a partial read of an 8.7 MB volume is far larger than that.
`download` now retries transient failures and reports 404s without retrying, and the reason is
written into the docstring so it is not optimised away later.

**What this round is really about.** Every number in this ledger was verified against its source when
it was written down. Nothing verified that the numbers *this repository generates itself* still
reproduce — and the one that carries the strategy had drifted across three documents, rested on two
volumes that do not exist, and could be silently shortened by a network hiccup. **The tool was built
so the count would not have to be trusted, and then the count was trusted anyway.**

The current reproducible figure, from `python -m eval.litreview --download --json`:

| | count |
|---|---|
| volumes | 96 |
| abstracts | 31,387 |
| detection papers | 526 |
| robustness/paraphrase | 139 |
| human-AI mixed/edited | 52 |
| watermark | 33 |
| education/integrity | 40 |
| calibration/thresholds | 13 |
| false positives/accusation | 13 |
| fairness/non-native bias | 8 |

The full-Anthology census (1,718 volumes: 164 robustness, 20 false positives, 13 fairness) is a
separate partial clone and is unaffected.

---

# Round sixteen — a systematic review, and a fairness axis that is empty

Two PubMed queries, both exhausted (7 records and 2 records respectively). One produced the
strongest single piece of evidence in this ledger; the other produced a hole.

## ✅ The non-native finding is no longer one study

According to PubMed, Ndacyayisenga, Kidega & Aciro Can (*BMC Med Educ*, 2026,
[DOI](https://doi.org/10.1186/s12909-026-09303-7)) is a **PRISMA 2020 systematic review** of
generative-AI assessment equity for non-native English speakers in English-medium medical, nursing,
pharmacy and dental programmes: 1,213 records screened, **27 studies included**, quality assessed
with MMAT and AXIS, synthesised under Kane's validity framework. It reports:

> "Six experimental research studies concluded that AI detectors falsely labeled NNES writing as
> AI-created in **50.2%–61.3%** of all cases (compared to **less than 5% among native writers**)."

Plus a second bias channel this ledger had not recorded at all: **four automated-scoring studies
found a systematic downward bias of 0.5–1.2 SD** against NNES students — detectors are not the only
AI in the assessment pipeline, and the grader is biased in the same direction as the detector.

**Why this outranks everything else here.** Every other fairness result in this ledger is a single
study on a single corpus. This is a registered-protocol systematic review that finds **six
independent experiments** converging on the same range, *and* supplies the comparator the single
studies mostly omit: **under 5% for native writers.** Liang's 61.3% is the top of a reviewed range,
not an outlier.

**And it sharpens the Czech disconfirmation rather than being contradicted by it.** Round six's
*Different Time, Different Language* ([2026.eacl-srw.20](https://aclanthology.org/2026.eacl-srw.20/))
found no systematic bias in Czech, and this ledger has since refused to state non-native bias as a
universal. That refusal stands and is now more precise: the effect is **robust and heavily replicated
in English-medium assessment of non-native English writers**, which is the setting detectors are
actually deployed in, and is not a claim about every language. The review's own conclusion is the
protocol this repo builds: "equity requires multilingual validation, **bias audits**, transparent
governance, and human supervision."

⚠️ **One caveat, stated because the review does not.** Its 50.2–61.3% is a range across six studies
with different corpora, detectors and thresholds — the same aggregation the 0-to-61% table warns
about, one level up. It is strong evidence that the effect is real and large in this setting. It is
not a number any institution should adopt as its own expected rate.

## ✗ The fairness axis nobody has looked at

Checked in **both** reachable corpora, because PubMed alone would not settle it — it indexes
biomedical literature and under-covers the CS and education venues where detection work appears.

**PubMed.** A query for AI-text detection against autistic, neurodivergent, ADHD, dyslexic or
disabled writers returns **two records, and both are false positives** — studies of AI *diagnosing*
autism and ADHD ([DOI](https://doi.org/10.1002/aur.70279),
[DOI](https://doi.org/10.1186/s11689-024-09578-1)), not of detectors judging disabled people's
writing.

**The ACL Anthology.** MEASURED over the 526 detection papers in the cached 96-volume corpus, the
terms `autis*`, `neurodiver*`, `ADHD`, `dyslex*`, `disabilit*`, `disabled` occur in **zero** titles
or abstracts. This is not a one-off grep: it ships as a topic row, so
`python -m eval.litreview --download --json` prints `"disability/neurodivergence": 0` alongside every
other count, and a reachability test proves the pattern can match text that does discuss it — the
same rule this repo applies to any registered tell or detector, so an honest zero cannot be confused
with a dead regex. The only matches the pattern finds at all are `accessible` (12), `accessibility` (3)
and `assistive` (1), every one of them incidental — "publicly accessible", not accessibility as a
subject.

**So across both corpora, the count of studies on whether AI detectors flag neurodivergent or
disabled writers is zero.**

And it is not that the community lacks the expertise or the populations. The same Anthology publishes
autism detection in speech, ADHD proxy detection from social media, a Korean speech corpus for
children with ASD, and sign-language accessibility work. **The people and the data are there; nobody
has pointed detector-fairness work at them.**

That is not a small gap. The traits detectors key on — formulaic phrasing, low burstiness, regular
sentence length, restricted vocabulary, template adherence — are documented features of some autistic
writing and of writing produced with assistive tools and accommodations. The ACL census found 13
fairness papers in the Anthology's entire history, and this ledger has established that essentially
all of the fairness evidence concerns language background. **An entire protected class is
unmeasured**, in a technology already deciding admissions (round fourteen).

This is the clearest open question this research has produced, and unlike most of the others it is
one the repo's own tooling could answer: `eval/assisted_fairness.py` already stratifies arms by
subgroup; the obstacle is corpora with disability metadata and consent, not method.

## ✗ And nothing on what happens to the accused

The due-process query — accusation, appeal, sanction, misconduct — returns **7 records**, of which
one is the review above, one is a perspective on integrity tooling
([DOI](https://doi.org/10.3389/frai.2025.1644098)), and the rest concern plagiarism practice rather
than AI detection (e.g. [DOI](https://doi.org/10.1186/s41073-024-00149-5)). The qualitative half of
the review names the tension — "the danger of false misconduct accusations" — but **no study in this
corpus follows an accused student through an appeal.** The literature measures the flag and stops
before the consequence, which is the same shape as round fourteen's finding that the humanizer
literature is absent where deployment is dense.

---

# Round seventeen — checking my own unsourced claim, and finding it backwards

Round sixteen justified status row 28 with this sentence:

> "The traits detectors key on — formulaic phrasing, low burstiness, regular sentence length,
> restricted vocabulary, template adherence — are documented features of some autistic writing."

**That was asserted, not sourced.** It passed `untell-audit` only because a DOI for a different claim
happened to fall inside the attribution window — a checker limitation, not a verification. It is
load-bearing (it is the entire argument for row 28), so it had to be checked. According to PubMed it
is **wrong as stated**, and the correct version is a better argument.

## What the literature actually reports

| Study | Population | Finding |
|---|---|---|
| Finnegan & Accardo, **meta-analysis** of 13 studies ([DOI](https://doi.org/10.1007/s10803-017-3385-9)) | ASD vs typically developing | Differences in **length, legibility, handwriting size, speed, spelling, overall structure** |
| Baixauli et al. ([DOI](https://doi.org/10.3389/fpsyg.2021.646849)) | 30 autistic vs 26 TD adolescents | Lower **productivity, lexical diversity, and overall coherence** |
| Shevchuk-Hill et al. ([DOI](https://doi.org/10.1007/s10803-022-05516-z)) | 19 autistic vs 23 non-autistic **university** students | "Writings were **more similar than different**"; autistic stories at a **higher reading level** (p = .013) and with **fewer grammatical errors** (p = .02); less likely to include a climax (p = .026) |
| Gillespie-Lynch et al. ([DOI](https://doi.org/10.1177/1362361320929453)) | Autistic vs non-autistic university students | "Autistic university students in our study were **better writers** than nonautistic students" |

**The specific list I published — burstiness, sentence-length regularity, template adherence — appears
nowhere.** Most of the meta-analytic differences are *mechanics and motor production*: handwriting
size, legibility, speed. Those do not survive into typed application text at all, which is the only
kind a detector ever sees.

## Why the corrected version is stronger

Two of the measured differences **are** documented detector signals, and they point the same way:

- **Fewer grammatical errors** (p = .02, university students). Error-freeness is one of the oldest
  machine-text cues.
- **Higher reading level** (p = .013), and **lower lexical diversity** in the adolescent sample.

So the risk is real — but it is *not* the deficit story my sentence implied. In the population that
actually matters here, applicants and university students, **autistic writers were rated equal or
better.** Gillespie-Lynch et al. say better outright; Shevchuk-Hill et al. say more similar than
different.

**That is the point, and it is the DivScore argument again** ([2025.emnlp-main.971](https://aclanthology.org/2025.emnlp-main.971/)):
detector failure tracks the *distance* between a writer's distribution and the detector's human
reference, not the *quality* of the writing. A writer who is cleaner and more precise than the
reference population is further from it, and cleanliness is the direction machine text also lies in.
**Writing well is a risk factor.** That is a sharper and more uncomfortable claim than the one I
originally made, and unlike that one it follows from measurements.

⚠️ **Tier, honestly.** The meta-analysis is Tier A but concerns mechanics. The two university studies
are the on-point ones and they are **small — n = 19 vs 23 and a participatory design** — so they are
Tier B: enough to retire my sentence and to justify row 28 as an open question, **not** enough to
assert that detectors do flag autistic writers. Nobody has run that experiment; that is still the
finding.

## The correction

Row 28's justification in ROADMAP §7 now states what these studies measured, and no longer asserts a
trait list that no source supports.

---

# Round eighteen — checking every cited figure against the paper it is credited to

Round seventeen found an unsourced claim by reading one paragraph carefully. That does not scale, and
the failure it belongs to has bitten twice now: **Beemo was published here as "11 detectors across 33
configurations" when its abstract says only 33** (the 11 came from the authors' repository), and the
citation resolved perfectly the whole time. `verify_citations` proves a paper exists. Nothing proved
the *number* beside it was one that paper reports.

`eval/litreview.py --cross-check` is the mechanical version. For every paragraph citing exactly one
Anthology paper, it compares each bolded figure against that paper's cached abstract and reports the
ones absent.

## Two defects in the checker, found before trusting it

**1. It compared figures against titles.** The first run reported essentially the whole corpus as
unsupported — including the journalism audit, whose numbers this document quotes verbatim.
`paper_index` returns *titles*; the check needed abstracts. **A checker that reports everything is
worse than no checker**, because the one real finding is invisible in the noise. `abstract_index` is
now a separate function whose docstring says why it exists.

**2. It treated a markdown table as one attribution unit.** A table has no blank lines, so a single
Anthology link anywhere in it captured every row's figures. That is how MASH
([2026.findings-acl.1487](https://aclanthology.org/2026.findings-acl.1487/)) came to be checked
against **−87.88%**, **97.6%**, **70.3% → 4.6%** — four numbers belonging to a different paper cited
in its own row two lines away. Each row carries its own citation, so each row is now its own unit.
Fixing these took the report from **35 findings to 25**, and every removed one was the checker's
fault, not the document's.

## The triage, recorded

All 25 remaining were read. **None is a misattribution.** They fall into three groups:

| Cluster | Figures | Verdict |
|---|---|---|
| Beemo paragraph, ROADMAP §7 | 64–80%, 38–49%, 9–15% | **Benign.** Credited in the same sentence to *Karr et al.*, by name. The checker only reads Anthology URLs, so an author named in prose is invisible to it |
| `2024.acl-long.674` bullet | 5 of 30, CI 7.3%–33.6%, CI 40.9%–92.9% | **Benign.** Our own `wilson_interval` output over our own README figures; the bullet says so outright |
| `2025.acl-long.1292` bullet | 26.7%, 16.9%, 61.3% → 11.6% | **Benign.** Our own `eval.pre_llm_fpr --by-length` measurements, with the command named on the line above, plus Liang's intervention figures |

**So the answer is that every figure this repository credits to an Anthology paper is either in that
paper's abstract or is explicitly credited elsewhere in its own sentence.** That is a real result and
it is the first time it has been checked rather than assumed.

## What it is, and what it is not

It is a **review list, not a pass/fail check**, and that is deliberate. A paragraph legitimately
mixes a cited paper's numbers with our own measurements and with figures credited to another author
by name — three things a regex cannot tell apart. Making it fail the build would force the prose to
be rewritten around the checker, which is the failure mode round fifteen's checker fixes were
careful to avoid. A hit means *confirm a reader cannot misattribute this*, not *this is wrong*.

Its limits, stated: it only sees **Anthology** citations, so DOIs and PMIDs are unchecked; it only
sees **cached** volumes; it only reads **abstracts**, so a figure from a paper's body reads as
unsupported; and it cannot see attribution by author name, which is the largest source of the 25.
`tests/test_cited_figures_appear_in_the_paper.py` pins the mechanics, including that a fabricated
figure is caught and that a verbatim quotation is not.

---

# Round nineteen — extending the cross-check to the half of the citations it could not see

Round eighteen closed with a stated limit: `--cross-check` reads **Anthology** citations only, so the
24 DOIs and every PMID in these documents were unchecked. That is not a small remainder. **The
false-positive table — the most load-bearing table in the strategy — is almost entirely DOI-cited.**
This round checks it.

## ⚠️ A methodological trap, found immediately

Resolving the DOIs and reading the abstracts produced an alarming first result: **the two most-cited
sources in this repository have abstracts containing no numbers at all.**

- Liang et al. ([DOI](https://doi.org/10.1016/j.patter.2023.100779)): the PubMed abstract is two
  sentences and states no figure. The repo cites it for **61.3%**, **61.3% → 11.6%**, **19.8%**,
  **97.8%**, in five places.
- Pratama ([DOI](https://doi.org/10.7717/peerj-cs.2953)): the abstract says "results reveal notable
  trade-offs in accuracy and bias" and nothing numeric. The repo cites it for **44.44%**, **4.17%**,
  **97.22%**, **0.00%**, **25% vs 11%**, in eight places.

**Had the Anthology check been ported to PubMed unchanged, it would have reported the entire
evidence base as unsupported.** The reason is structural and worth writing down: an ACL abstract
carries the paper's headline numbers, and a biomedical abstract frequently does not. **The unit of
verification for a PubMed source is the full text, not the abstract** — which is why this round used
`get_full_text_article` rather than porting round eighteen's tool.

That is the second time in two rounds a checker would have produced a spectacular false finding
(round eighteen's compared figures against titles). Both were caught by asking "is this result too
dramatic to be true?" before believing it.

## ✅ Liang et al., confirmed verbatim from the full text

According to PubMed, PMC10382961 ([DOI](https://doi.org/10.1016/j.patter.2023.100779))
contains every figure this repository attributes to it:

| Claim as published here | In the full text |
|---|---|
| 7 detectors | "seven widely used GPT detectors" |
| 91 TOEFL, 88 ASAP essays | "91 TOEFL … essays from a Chinese forum and 88 US eighth-grade essays from the Hewlett Foundation's ASAP dataset" |
| **61.3%** average FPR | "average false-positive rate: 61.3%" |
| **19.8%** unanimous | "All detectors unanimously identified 19.8%" |
| **97.8%** flagged by ≥1 | "at least one detector flagged 97.8% of TOEFL essays" |
| **61.3% → 11.6%** intervention | "dropping by 49.7% (from 61.3% to 11.6%)" |
| Simplifying native essays raises misclassification | "simplifying the vocabulary in US eighth-grade essays … led to a substantial increase in misclassification" |

Every one verbatim. The ledger's round-one entry — "**Verbatim**, plus exact design" — was correct,
and is now confirmed against the source rather than against a search result.

## ⚠️ And a tier nuance the ledger did not carry

**PubMed types this article as `News`.** Reading it, the reason is plain: it is a *Patterns*
perspective in which the authors summarise their own study — "In our recent preprint, we exposed an
alarming bias…". The numbers are published, peer-reviewed and quoted here correctly. But the
peer-reviewed artefact is a **commentary reporting the authors' preprint**, not the full study with
methods and tables.

This does not demote the result — it is the same authors reporting their own figures in a refereed
venue, and it remains Tier A. It does sharpen what "Tier A" means for the single most-cited fairness
result in this strategy: **the design details we quote (91 essays, 88 essays, seven detectors) come
from a summary of a study whose full methods live in a preprint this environment cannot reach.**
Anyone rebuilding this analysis should know that before treating the sample sizes as fully
documented.

## What is now checked, and what is not

| Citation class | Count | Status |
|---|---|---|
| Anthology ids | 30+ | ✅ resolve, and figures cross-checked against abstracts (round eighteen) |
| DOIs | 24 | ✅ resolved; the two most-cited verified against **full text** this round |
| Remaining DOIs | 22 | Resolved and read at abstract level in earlier rounds; not re-verified against full text |
| arXiv-only | 5 | ⛔ unreachable, and no ✅ claim rests on one (enforced by a test since round sixteen) |

The honest summary: **the two sources carrying the most weight are now verified at full-text depth,
and the structural trap that would have made a naive port of round eighteen's tool report a
catastrophe is documented so the next person does not fall into it.**

---

# Round twenty — the load-bearing table was mixing two different quantities

Round nineteen verified the two most-cited DOIs and left 22 unchecked. This round worked through the
ones carrying the false-positive table, and found **the table itself was wrong** — not in any
individual number, but in what it was a table *of*.

## ✅ What verified cleanly

According to PubMed, verbatim from the abstracts:

- **Hyatt et al.** ([DOI](https://doi.org/10.1152/advan.00235.2024)): "Approximately **1.3%** and
  **5.0%** of the essays were detected as false positives … by AI detectors and human raters,
  respectively" and "Using AI detectors in aggregate reduced the likelihood of detecting a false
  positive to **nearly 0%**." All three rows confirmed.
- **Subillaga et al.** ([DOI](https://doi.org/10.1016/j.jsurg.2025.103566)): **1490** statements,
  GPTZero **10.2% → 36.6%**, Copyleaks **2.6% → 22.5%**, concordance **1.7% → 21.2%**, non-English
  native language characteristics **38.7% vs 19.6%**. Every figure in round fourteen confirmed.
- **Bohler et al.** ([DOI](https://doi.org/10.1097/SCS.0000000000012366)): **1490** manuscripts,
  **659** from 2014 and **831** from 2024, **8.6% → 10.7%**. Confirmed.
- **Popkov & Barrett** ([DOI](https://doi.org/10.1080/08989621.2024.2331757)): **27.2%**, **100**
  articles from 2016–2018. Confirmed.

## ✗ And the defect: two of those rows are not rates

Read the exact wording of the last two:

> Bohler: "**Mean detectable AI content** increased from **8.6%** (SD 9.8) in 2014 to 10.7%"
>
> Popkov: "The free AI detector showed a **median of 27.2%** for **the proportion of academic text**
> identified as AI-generated"

**Neither is a share of documents flagged.** Both are per-document *scores* — the average percentage
of text inside a manuscript that a detector marks as AI — averaged or medianed across a corpus. The
other rows (1.3%, 5.0%, 44.44%, 61.3%, 10.2%, 2.6%, 1.7%) are shares of documents. **Two different
quantities, in one table, under one heading, feeding one "0% to 61%" range.**

This is the exact conflation the section containing that table warns institutions about, and it is
the same error this ledger caught itself making twice before — the Cumbo 64–100% figures were kept
*out* of the table in round fourteen for precisely this reason, and the SD of 9.8 on Bohler's 8.6%
should have been the tell. **It sat in the headline table for nineteen rounds, through every previous
audit, because nothing checks the units of a number — only its provenance.**

Both rows are removed from the rate table and the distinction is stated beneath it. The 0-to-61%
range is unaffected: it was always a range of rates, and both removed figures sat inside it.

## Two consequences that followed

**1. A comparison that meant nothing.** ROADMAP claimed our own pre-LLM measurement — "15.8% of 120
abstracts flagged" — was "roughly double the 8.6% Bohler measured". A share of documents against a
mean share of text: no ratio between them means anything. Corrected.

**2. A sample size that was the wrong one.** ROADMAP said Hyatt found 1.3% false positives "on 190
students' essays". The abstract: 190 was the *participant* count; the detectors saw a randomly
selected **50** essays and the nine human raters a separate **48**. Corrected.

## What this round is really evidence of

Every previous check in this ledger asked *does this number have a source* and *does the source say
it*. Both answers were yes here — the figures are quoted correctly from papers that report them. The
defect was in **what kind of number it is**, which no provenance check can see. `untell-audit` counts
445 attributed claims and would count these among them.

That is a limitation worth stating plainly rather than fixing with a regex: **units and quantity type
are not mechanically checkable from prose, so a table of numbers from different studies needs a human
to confirm every row measures the same thing.** The table now says which quantity it holds, in its
own heading, so the next row added has to answer the question.

---

# Round twenty-one — the same question asked of the rest

Round twenty found the false-positive table mixing *rates* with *per-document scores*. That is not a
provenance error, so no existing check could see it, and the obvious next move was to ask the same
question of every remaining figure rather than to assume it was a one-off.

## ✗ It was not a one-off

**Stern et al.** ([DOI](https://doi.org/10.1016/j.arth.2025.07.072)) was published in round fourteen
as "Pre-ChatGPT cohort scored 99.5% human; post-ChatGPT 83.8%". According to PubMed the abstract
reads:

> "The pre-PS cohort had an **average GPTZero score** of **99.5% (SD 1.9) human**, 0.4% (SD 0.8) AI …
> while the post-PS cohort had scores of **83.8% (SD 29.9) human**, 15.1% (SD 28.9) AI"

These are **mean detector scores across statements**, not shares of statements — the third instance
of this quantity after Bohler and Popkov. Our phrasing was ambiguous rather than wrong, and ambiguity
here reads in exactly one direction: *83.8% human* sounds like *16% of applicants used AI*.

**And the standard deviation is the real finding.** SD 29.9 on a mean of 83.8 means the statements
are **not** clustered near 84% human — they split between a majority scoring near-human and a
minority scoring heavily AI. The pre-cohort's SD of 1.9 shows what a tight distribution looks like by
comparison. A mean over a bimodal distribution is close to meaningless as a description of any
individual applicant, which matters because applicants are judged individually.

## ✅ What verified cleanly

- **The systematic review** ([DOI](https://doi.org/10.1186/s12909-026-09303-7)) — and it is a rate,
  so its place in the corrected table is right: detectors "falsely labeled NNES writing as AI-created
  in **50.2%–61.3% of all cases** (compared to **less than 5%** among native writers)". Also
  confirmed verbatim: **27** studies from **1,213** screened, the **0.5–1.2 SD** downward scoring
  bias, and the survey arm (**n = 8**, total **2,847**; **79%**, **63%**, **71%**).
- **Erol et al.** ([DOI](https://doi.org/10.1007/s00701-025-06622-4)): **250** pre-ChatGPT
  human-authored articles against **750** ChatGPT texts, three detectors, **AUC 0.75–1.00**, "none of
  the detectors achieved 100% reliability", "false positives pose risks to researchers". Verbatim.

## The count, and the standing rule

Three of the studies this repository cites report a **mean or median detector score per document**
(Bohler, Popkov, Stern); the rest report **shares of documents flagged**. All three are now labelled
as what they are, and none sits in the rate table.

**The rule this leaves behind:** before a figure joins a table or a comparison, ask what it is the
proportion *of*. Provenance checks cannot answer that — `untell-audit` counted all three among its
attributed claims, and every one was quoted correctly from a paper that reports it. Only reading the
sentence around the number answers it.

---

# Round twenty-two — the DOI sweep, finished

All 24 DOIs cited in these documents have now been checked against their source. This round covered
the last of them, asking round twenty's question — *what is this a proportion of?* — of every figure.

## ✅ Verified verbatim

- **Sourati et al.** ([DOI](https://doi.org/10.1038/s41562-026-02550-0)): "Across **three studies**
  spanning **seven datasets** … over **880,000 texts** … reducing writing-complexity variance by a
  statistically significant **21-50%** across datasets and models (**P ≤ 0.05**)." Correctly typed as
  a variance reduction.
- **Ozkara et al.** ([DOI](https://doi.org/10.3174/ajnr.A8505)): "**Fifty-eight percent** of unpaired
  articles were correctly classified … increased to **70%** in the paired setting", and editors
  "strongly preferred publishing the article they perceived as human-written (**82%**)". Our
  "58–70% of the time" is right, and these are classification accuracies, correctly described.
- **Du & Koga** ([DOI](https://doi.org/10.1016/j.jdin.2025.10.017)) — a **Letter with no abstract in
  PubMed**, so this was read from the PMC full text. Both quotations confirmed word for word,
  including the Wang et al. figures ("**97% to 100%** of originals … classified as human … after
  polishing, **75% to 85%** … including **15% to 25%** at high confidence").
- **Goodman et al.** ([DOI](https://doi.org/10.1097/JTE.0000000000000396)): "Human raters
  demonstrated high agreement (**κ = 0.92**) and accuracy (**97% and 99%**)."

**A corroboration worth noting.** Du & Koga independently make the criticism this repo had already
written into `eval/assisted_fairness.py`: "Using U.S. institutional affiliation as a proxy for native
English status risks misclassification. Since many U.S.-affiliated authors trained or grew up in
non-English environments, affiliation alone may not capture language background." The tool's warning
was added on our own reading of the data; it now has a published source.

## ✗ Two corrections

**1. A fourth quantity conflation, this one inside a comparison.** Goodman's human raters were
described here as scoring "above the GPTZero-derived parameters measured on the same corpus". The
study reports GPTZero's parameters as **AUC > 0.875** and RQA at **0.768** and **0.859**. **An
accuracy is not an AUC**, and the two cannot be ranked against one another. The comparison is
removed; the standalone finding — 97% and 99% accuracy, κ = 0.92 — stands.

**2. A correction this ledger recorded but never applied.** Its own table of retractions says the
Karr et al. range "38–80%" is imprecise and "collapses two detectors: 64–80% Pangram, 38–49%
GPTZero". A paragraph 700 lines later still said **38–80%**. **A correction that is written down but
not propagated is not a correction** — it just moves the wrong number somewhere harder to find. Fixed,
and worth treating as a class of defect rather than a one-off: the retraction table should be checked
against the body, not only appended to.

## The sweep, closed

| | Checked | Result |
|---|---|---|
| Anthology citations | 30+ | Resolve; figures cross-checked (round eighteen) |
| DOIs | **24 of 24** | All verified against abstract or full text |
| Quantity-type audit | every cited figure | **4 conflations found** — Bohler, Popkov, Stern, Goodman |
| arXiv-only | 5 | ⛔ unreachable; no ✅ claim rests on one, enforced by test |

Four of the quantity errors were found by asking one question that no automated check performs. That
is the durable lesson of rounds twenty to twenty-two: **provenance checking is mechanisable and was
already green on every one of these; knowing what a number counts is not.**

---

# Round twenty-three — the retractions that never propagated

Round twenty-two ended by naming a class of defect and not acting on it: *"a correction written down
but not propagated is not a correction … the retraction table should be checked against the body, not
only appended to."* One instance had been found. Nobody had asked how many there were.

Sweeping every retracted form in this ledger against every research document found **three more**,
and the worst is embarrassing in a useful way.

## ✗ The corrected number survived in the sentence this ledger calls its best

Round two retracted the collapsed Karr range (Karr, Khvatskii, Hua & Chawla, ACM AILS '26; measured
on their light-edit arm), writing: *"We wrote 'light edits flagged at 38–80%'. The paper splits by
detector: 64–80% by Pangram and 38–49% by GPTZero."*

**Three lines below that correction**, the same round wrote what it called "the most quotable
sentence in this whole literature": *"detectors punish legitimate light editing at 38–80% while
letting more than 96% of deliberately humanized synthetic text through."*

The retired number, in the most rhetorically load-bearing line in these documents, directly beneath
its own retraction. **And it propagated**: `research-to-build.md` had copied that sentence verbatim,
which is where round twenty-two found it. The correction was written, published, and then ignored by
the paragraph next to it.

## ✗ And two more

- The round-two verification table still recorded the *verified* Karr claim (ACM AILS '26,
  arXiv:2608.11256) as "flagged at **38–80%**" — the table asserting the claim was checked carried
  the version the same round had just corrected.
- `research-to-build.md`'s dataset table listed RealDet's "15 domains, 22 LLMs, 847k+ texts" **in
  bold and unhedged**, though the ledger had demoted those dimensions to Tier B because none of them
  appears in the published abstract. Now marked Tier B, with the reason on the row.

All three fixed.

## The guard

`tests/test_retracted_claims_do_not_survive_elsewhere.py` now pins the retired forms that have
actually escaped — the Karr range, MGTEVAL's "26 detectors", Bohler's "pure false-positive rate",
Hyatt's "190 students' essays", the Goodman AUC comparison, and the autistic-writing trait list.

The rule it encodes is not "this string must never appear": **a ledger has to quote what it retracts
or it cannot document anything.** The rule is that a retired form may appear only within a few lines
of a marker saying it is being corrected. Two mistakes in writing that check were instructive in
themselves — the first version reported every correction in this document as a violation, because it
read one line at a time and these documents hard-wrap at 100 columns, so "✗ An earlier draft said…"
routinely sits two lines above the number it corrects; the second still failed on the one place the
ledger blockquotes a retracted sentence and corrects it *underneath*.

**What this round is evidence of.** Every correction in this ledger was accurate when written. The
failure was downstream of accuracy: a correction is only worth as much as its propagation, and
nothing was checking that. Twenty-two rounds of verification produced a document that contradicted
itself three lines apart, in its most-quoted sentence, and no provenance check, citation check or
attribution check could see it — because every version of the number had a source, and the source
said it.

---

# Round twenty-four — the sweep that was actually a spot-check

Round twenty-three built a guard against retracted claims coming back, and pinned six retired forms.
**Those six were the ones I happened to remember.** The guard was as good as my recall, which is the
same weakness the guard exists to fix, one level up.

So this round enumerated the retractions instead of recalling them: **39 correction markers across
the four research documents**, read one by one. About a dozen are genuine claim retractions with a
retired form that could still be alive somewhere; the rest are section headings, legend rows, or
*external* results cutting against us, which are not our retractions. Six retired forms were not in
the guard at all.

## ✗ One more escape, the same shape as the last

`research-to-build.md` states, as fact: *"MCP's **length-conditioned quantiles** are the principled
version of the `verdict_threshold` split."* Eleven lines above it, the same document says:

> ✗ Two details this document previously asserted are **not in the published abstract**: that the
> quantiles are *length-conditioned* …

**The correction and the uncorrected restatement, in one document, eleven lines apart** — exactly the
Karr pattern from round twenty-three, in a different document, about a different paper. Now hedged:
the conformal bound is what the paper supports, and the length-conditioning is named as the Tier B
claim it is, with the note that **the bound does not depend on it.**

## ✅ And one thing the sweep got wrong

It also flagged `| humans cannot detect | 3 |` in the ledger. That is a **census row counting how
many surveyed papers assert the claim** — not the ledger asserting it. Reading a count as an
assertion would force the census to be reworded to satisfy a checker, which is the failure mode round
fifteen was careful to avoid. The guard now skips two-column count rows, and **that suppression is
itself pinned**: a three-column findings row, or one carrying a percentage rather than a count, is
still read.

## Where the guard stands

Eleven retired forms are pinned, not six: the Karr range, MGTEVAL's "26 detectors", Bohler's "pure
false-positive rate", Hyatt's "190 students' essays", the Goodman AUC comparison, the
autistic-writing trait list, MCP's "length-conditioned", the TiCS "2–8×" figure, and the three
"nobody does this" primacy claims (H2L, the stratified audit, stylistic distance). Fifteen tests.

⚠️ **And the guard failed on this very entry**, which is worth keeping. Listing the pinned forms
above put "26 detectors" and "2–8×" into a paragraph the checker did not read as a correction,
because its marker vocabulary knew *retract* but not *retired*. The fix was the regex, not the prose:
a checker that forces a document to avoid the words it needs is the failure mode round fifteen
warned about, and the third time in this ledger that the first version of a checker was wrong before
the thing it checked was.

**The honest summary of two rounds:** the propagation problem has now produced escapes in three
separate places — Karr twice, MCP once — and each was found only by looking for it deliberately. The
first search was scoped by memory and missed a third of the retractions. **A guard built from recall
inherits the failure of recall**, and the fix was to enumerate the source of truth rather than to
remember it.

---

# Round twenty-five — the check I had not run, and the three regressions it found

Twenty-four rounds of checking documents, and the thing I had *not* done was run the test suite.
Every round since fifteen shipped code — `LIVE_DOCS` and two new rules in `untell/scripts/audit.py`,
and `_fetch`, `_attribution_units`, `abstract_index`, `unsupported_figures`, a new `TOPICS` row and
two removed volumes in `eval/litreview.py` — verified only against targeted subsets. A full run
against `main` in a worktree, the same method used earlier in this session, found **three
regressions, all mine.**

MEASURED by `python -m pytest tests/ -q -p no:randomly --continue-on-collection-errors`, run once on
this branch and once on a `git worktree` at `main` (b054e67):

| | branch | base (`main`) |
|---|---|---|
| failed | **77** | 74 |
| passed | 8,920 | 8,803 |

## ✗ 1–2. The API told clients something untrue

`/score` has returned an **`agreement`** object since early in this session — the union / majority /
unanimous spread, the single feature this whole strategy argues nobody ships. **It was never declared
in the response schema.** Two tests caught it, one against the published schema and one against
`/openapi.json`:

> `/score returns fields the schema does not list: ['agreement']`

So a client generated from the OpenAPI document had no entry for the field this repository exists to
surface. The schema now declares it and every sub-field, including `degenerate` — the flag that says
only one detector scored, so the three rules are arithmetically identical and the spread is not
measurable on that run.

**This is the sharpest instance of the pattern these rounds keep finding.** Twenty-four rounds
verified what the *documents* say about other people's numbers. Meanwhile the repository's own API
was shipping an undeclared field, and no amount of citation checking would ever have looked there.

## ✗ 3. Lint, on files I added

`ruff check .` failed on `tests/test_cited_papers_resolve.py` (two semicolon-joined statements) and
`tests/test_litreview_download_survives_a_truncated_transfer.py` (a quoted type annotation that no
longer needs quoting). Trivial, and it would have failed CI on push.

## What this round is evidence of

The guards built in rounds sixteen to twenty-four all check **claims against sources**. None of them
runs the code. A repository that audits detectors for a living had, in its own tree, an undeclared
API field and a lint failure — both found in one command that costs an hour of wall time and had not
been run in twenty rounds.

**The rule: after any round that touches code, run the suite against base before believing the round
is finished.** Targeted tests confirm the thing you were thinking about. Only the full run catches
what you were not.

---

# Round twenty-six — applying rounds twenty to twenty-two to our own headline number

Four published studies were caught reporting a **mean per-document detector score** inside a table of
**false-positive rates**. The repository criticises that conflation in `ROADMAP.md` §7. It was also
committing a milder version of it.

`ai_percent` is the headline number this tool shows, and until this round its entire published
description was **"max * 100"**. That is accurate and says nothing about *what kind of number it is*.
A reader who sees `ai_percent: 84` has two wrong readings immediately available — *84% of this text
is AI-written*, and *84% of documents like this are AI*. Neither is what the field means (it is one
detector's probability for one document), and the schema ruled out neither. Stern's
"83.8% human" became "16% of applicants used AI" by exactly that route, and the consumer of this API
is the same program director the strategy document says we are built for.

**Fixed at all three surfaces**, in the same words:

- `max` — "highest P(AI) across detectors for THIS ONE DOCUMENT … A per-document score, not a rate:
  it is not the fraction of the text that is AI-written, not the share of a corpus that would be
  flagged, and not a false-positive rate."
- `mean` — named as an average *over detectors for one document*, since a mean is otherwise assumed
  to be over a corpus.
- `ai_percent` — the same, plus the two misreadings named explicitly.
- The MCP `score` tool carries the identical warning, because two surfaces disagreeing about the same
  operation is a defect this repo has already shipped once.

`tests/test_the_headline_number_says_what_kind_of_number_it_is.py` pins it, including the other half
of the invariant: **if the score is a score, the false-positive measurement must be a genuine rate**,
so it also checks that `eval/pre_llm_fpr.probe` still divides flagged documents by documents scored.
A description is exactly the kind of thing a later edit trims for brevity.

## ⚠️ And a process failure in this round, recorded

The full-suite parity run from round twenty-five was **still in flight** when these edits landed, so
its result would have mixed old and new code. It was killed rather than reported. **This is the
second time in this session that editing during a long run contaminated it** — the first was
installing spaCy mid-suite. The rule that follows: a long verification run makes the tree read-only
until it finishes, and the discipline costs nothing compared with trusting a mixed result.

---

# Round twenty-seven — the corpus knew things the strategy did not

The cached Anthology corpus has been used to *check* claims. This round used it to *look* — reading
the papers under each topic that this repository had never cited. Six of them change something.

## ✗ 1. "Nobody audits whether that marking survives ordinary use" is false

ROADMAP §7 said exactly that of Article 50 watermark marking. **WaterPark**
([2025.findings-emnlp.1148](https://aclanthology.org/2025.findings-emnlp.1148/)) is a unified
platform integrating **10 watermarkers and 12 removal attacks**, built to answer "what are the
strengths/limitations of various watermarkers, especially their attack robustness?" That is the audit
the claim said did not exist. **This is the fourth "nobody does this" claim in this ledger to fail on
contact with the corpus**, after H2L, the stratified audit and stylistic distance.

## ✗ 2. And the item's *design* was wrong for a third-party auditor

Row 21 said "build against the HF Transformers implementation" of SynthID's detector. That detector
needs the provider's key or scheme. **TTP-Detect**
([2026.findings-acl.990](https://aclanthology.org/2026.findings-acl.990/)) states the consequence
better than we had:

> "existing secret-key schemes tightly couple detection with injection, requiring access to keys or
> provider-side scheme-specific detectors for verification. **This dependency creates a fundamental
> barrier for real-world governance, as independent auditing becomes impossible without compromising
> model security or relying on the opaque claims of service providers.**"

That is this repository's own thesis, published, about watermarks. **An auditor holding the vendor's
key is not a third party.** TTP-Detect's architecture — decouple detection from injection, reframe it
as relative hypothesis testing against a proxy model — is what row 21 should be built to. The item is
not cancelled; its blueprint changed.

**WaterSeeker** ([2025.findings-naacl.156](https://aclanthology.org/2025.findings-naacl.156/)) adds
the realistic case: watermarked *segments* inside large human documents, not wholly-marked texts.
That maps onto `untell/scripts/sentences.py` rather than onto document-level scoring.

## ✗ 3. The fine-grained arm we position around is already a shipped tool

`LLM-DetectAIve` ([2024.emnlp-demo.35](https://aclanthology.org/2024.emnlp-demo.35/)) is a
demonstrated system with **four categories: human-written; machine-generated; machine-written then
machine-humanized; human-written then machine-polished.** Those are the humanizer arm and the
assisted arm, shipped, in 2024. Our positioning has to narrow accordingly: what remains ours is not
fine-grained *classification* but **per-subgroup false-positive measurement at a caller's threshold,
with the aggregation spread** — none of which LLM-DetectAIve reports.

It also supplies the normative sentence this strategy needed: machine-polishing of human text is
"typically acceptable in academic writing, but not in education." **The acceptability of assistance is
set by the institution, not the detector** — which is the argument for reporting arms separately
rather than collapsing them into one verdict.

## ✅ 4. A public three-way corpus for the assisted arm — in hiring

[2026.lrec-1.581](https://aclanthology.org/2026.lrec-1.581/) releases **the first corpus annotated
authentic / AI-enhanced / fully AI-generated**: 420 resumes, balanced across the three classes, five
IT job descriptions, authentic resumes anonymised, released for reuse. Row 19 named Beemo and ARB as
the corpora for this arm; this is a third, in a **second high-stakes deployment domain** after
admissions.

**And it benchmarks two commercial detectors on it.** Originality reaches **55.7% accuracy overall**
(71/140 authentic, 81/140 AI-generated, 82/140 AI-enhanced correct); Writer reaches **25.0%**, "with
the largest failures on AI-enhanced resumes, highlighting domain shift and cautioning against
uncalibrated deployment."

⚠️ **A derived figure, labelled as derived.** From their per-class counts, **69 of 140 authentic
resumes — 49.3% — were misclassified by Originality.** The paper does not state that number; it
states the counts and an overall accuracy of 55.7%, which the same counts reproduce exactly
((71+81+82)/420 = 55.7%), so the arithmetic is checked against their own total. In a three-way task a
misclassified authentic resume is called AI-enhanced or AI-generated, and for an applicant both are
an accusation. Read as a share of documents, it belongs in the false-positive table; it is entered
there as a derived quantity.

Its style analysis independently reproduces the homogenization finding from the other direction:
**authentic text has the widest variance across all features**, AI-generated the shortest and most
uniform sentences.

## ✅ 5. The accused *can* be shown evidence — the technical half of round sixteen's gap

Round sixteen found no study following an accused student through an appeal, and concluded the
literature "measures the flag and stops before the consequence". That stands for *process*. It is
wrong about *technique*, and two refereed systems say so:

- **ExaGPT** ([2026.findings-acl.380](https://aclanthology.org/2026.findings-acl.380/)) opens on this
  repository's own ethical claim — detection errors risk "undermining student's academic dignity" —
  and argues detection "needs to ensure the interpretability of the decision, which can help users
  judge how reliably correct its prediction is." It returns, per span, the similar human-written and
  LLM-generated spans that drove the decision, and a **human evaluation shows this helps people judge
  correctness better than existing interpretable methods.**
- **DAMASHA** ([2026.findings-eacl.326](https://aclanthology.org/2026.findings-eacl.326/)) segments
  mixed-authorship text, releases an adversarial benchmark, and adds **Human-Interpretable
  Attribution overlays** with a human study of their usefulness.

**This is the strongest available answer to the label effect.** Round five established that a bare
label changes how a reader judges the text, and that "a human will review the flag" therefore fails.
A label plus checkable per-span evidence is a different object from a label, and it is the only
mitigation in this literature that acts on the reviewer rather than on the accused.

**Consequence for this repo:** `untell/scripts/sentences.py` already targets per sentence. Reporting
*why* a span scored as it did is the same shape as what it already computes, and it is now a
refereed requirement rather than a nicety.

## ✅ 6. Sentence-level hybrid detection has a benchmark

**SenDetEX** ([2025.emnlp-main.268](https://aclanthology.org/2025.emnlp-main.268/)) builds a
dedicated sentence-level benchmark for "complex human-AI hybrid content, where human-written text and
AI-generated text alternate irregularly", noting mainstream detectors "target document-level long
texts and struggle to generalize to sentence-level short texts". That is the same finding as our own
length-conditioned curve — **26.7% flagged at ≤50 words against 15.6% at 50–100** — arrived at
independently, and it supplies a corpus for the case.

## What this round is evidence of

Every earlier round asked *is what we wrote true?* This one asked *what is in the corpus we already
downloaded?* — and found a shipped tool covering two of our arms, a public corpus for a third, a
published statement of our own governance thesis, and a fourth false "nobody" claim. **The corpus had
been treated as a fact-checking instrument and never as a source.** Reading the uncited papers under
each topic took one pass and changed two roadmap items.

## The cross-check caught this round's own defect

Running `--cross-check` after writing round twenty-seven took it from 25 flagged figures to 40, and
one of the new ones was mine. Inserting the WaterPark citation into row 21 made it **the only
Anthology citation in that paragraph**, so SynGuard's SynthID numbers — **1.000 → 0.842** under
paraphrase, **0.788**, **0.714** — sat next to it and could be read as WaterPark's. The SynGuard
repository link was still on the line beneath, so nothing was *unattributed*; it was newly
*confusable*, which is a weaker fault and still worth fixing. The two are now separate paragraphs and
the numbers say whose they are in the sentence that states them.

The other new flags are the checker behaving correctly on two things it cannot see:

- **The derived 49.3%** is not in the resume paper's abstract, because the paper does not state it —
  that is precisely why the roadmap labels it derived and shows the arithmetic.
- **26.7% and 15.6%** are our own length-band measurements, MEASURED by
  `python -m eval.pre_llm_fpr --by-length`, in a sentence noting SenDetEX reached the same conclusion
  independently. Attribution is by the words "our own", which reads only to a human.

**Worth stating plainly: the tool built in round eighteen caught a fault introduced in round
twenty-seven, minutes after it was written.** That is the first time a guard in this ledger has
caught something in the round that created it rather than an inherited defect, and it is the only
evidence that any of these checks pay for themselves going forward rather than only backwards.

## The parity result, complete this time

Round twenty-five compared truncated logs — both runs had been piped through `tail -50`, so the
failure-ID diff was taken over the last fifty lines of each and could not have been trusted. Both
suites were re-run capturing **every** failure ID. MEASURED by
`python -m pytest tests/ -q -p no:randomly --continue-on-collection-errors`, branch against a
`git worktree` at `main` (b054e67):

| | branch | base |
|---|---|---|
| failing ids | **81** | 82 |
| passed | 8,933 | 8,803 |
| **only on branch (regressions)** | **none** | — |
| only on base (fixed by branch) | — | `test_docs_claims.py::test_why_best_test_count_is_not_stale` |

**The regression set is empty and the branch fixes one failure base has** — the documented test count
stopped being stale once this session's tests were added. The three regressions round twenty-five
found are gone, and nothing replaced them.

The methodological note is the reusable part: **a truncated log cannot support a difference claim.**
Round twenty-five's `tail -50` was a convenience that quietly reduced a set comparison to a comparison
of two arbitrary windows, and it produced a diff with entries on both sides that were artefacts of
where each window happened to start. The counts were right; the diff was noise.

---

# Round twenty-eight — building the thing round twenty-seven found

Round twenty-seven established that interpretability is a **refereed requirement**, not a nicety:
ExaGPT ([2026.findings-acl.380](https://aclanthology.org/2026.findings-acl.380/)) shows in a human
study that per-span evidence helps people judge whether a detection decision is correct, and DAMASHA
([2026.findings-eacl.326](https://aclanthology.org/2026.findings-eacl.326/)) ships attribution
overlays for the same reason. Round five is why it matters here: a bare label changes how a reader
judges text **even when the label is wrong**, so "a human will review the flag" fails when the flag is
all the human gets.

`untell-sentences --evidence` now names the catalogue tells found inside each sentence, with the
literal strings:

```
[AI 0.83] It is important to note that the framework leverages robust methodology.
          evidence · ai_vocab: robust
          evidence · cliche: It is important to note
[ok 0.00] Rain fell.
```

Built from machinery that already existed — `score_tells(include_matches=True)` and the per-sentence
targeting in `untell/scripts/sentences.py` — so it needs no network, no model weights and no new
dependency, which matters in an environment where the ML detectors cannot load at all.

## The hard part was refusing to overclaim

**The tells catalogue is not the detector.** `ai` comes from the detector ensemble — perplexity and
burstiness, or ML weights — which never consults the catalogue. ExaGPT's evidence *is* its decision
procedure; ours is a separate heuristic run over the same sentence. So a sentence can score high with
no tells, and carry tells while scoring low.

Presenting corroboration as explanation would be **a fabricated rationale for a number produced by
something that never saw the evidence** — which is worse than offering no evidence, and is precisely
the class of error this ledger has spent nine rounds correcting in other people's work and its own.
The output says so in the note, the CLI prints the note, and a test asserts the wording still denies
it:

> "These CORROBORATE a score, they do not explain it: `ai` comes from the detector ensemble …, which
> never consults this catalogue."

Eight tests pin both halves — that the evidence appears, names strings that genuinely occur in the
sentence, invents nothing for a clean sentence, is sourced from the catalogue rather than derived
from the score, and that the disclaimer survives. **The one that matters is the last.** A future edit
trimming that note for brevity would turn an honest feature into a lie, and nothing else in the suite
would notice.

Shipped as status row 29. Row 28 kept its number deliberately: three entries in this ledger refer to
"row 28" as the disability arm, and renumbering would have silently invalidated them — the same
propagation failure round twenty-three is about, one level up.

## The same feature on every surface

`--evidence` shipped on the CLI first, and for one commit that is all it was. `untell/mcp_server.py`
carries comments about `tier` and `threshold` having once disagreed between REST and MCP — the same
named operation answering differently depending on which door a caller used — so shipping this on one
surface would have rebuilt a defect this repository had already written down.

`POST /sentences` and the MCP `sentences` tool now take `evidence` too, and both carry the
corroboration caveat in their own words rather than by reference. Four more tests hold the three
surfaces together, including one that reads the MCP docstring, because a caveat that exists only in
the REST schema is not a caveat a Claude client ever sees.

⚠️ **And declaring the field broke two schema tests, which is the system working.** `evidence_note`
appears only when the caller asks for it, so "every documented field is returned" failed the moment
it was documented. The fix was to add it to `CONDITIONAL`, the allowlist of fields that can be absent
on a normal call — **not** to leave it out of the schema. Leaving it out is exactly the round-25
defect, where `/score` returned `agreement` for several releases with nothing in the schema saying
so, and a client generated from `/openapi.json` had no entry for the one field this tool exists to
surface. **The cheap way to make those two tests pass was to reintroduce the bug they did not
cover.**

---

# Round twenty-nine — the largest unread topic, and a variable the thesis was missing

The `education/integrity` row of the survey holds 40 papers and **30 of them had never been cited
here** — the biggest unread block in the corpus. Reading them produced one addition to the central
claim of this strategy and one refereed critique of a feature shipped two rounds ago.

## ✅ The thesis sentence was incomplete

This roadmap's load-bearing sentence said a false-positive rate is a property of "a detector, a
population, a domain, an editing history and an aggregation rule." *How You Prompt Matters!*
([2024.findings-emnlp.841](https://aclanthology.org/2024.findings-emnlp.841/)) supplies a sixth, and
it is not a small one:

> "even task-oriented constraints — constraints that would naturally be included in an instruction
> and **are not related to detection-evasion** — cause existing powerful detectors to have a large
> variance in detection performance … **up to an SD of 14.4 F1-score**"

and that variance is **larger than the variance from generating the text multiple times or
paraphrasing the instruction.** The domain they chose is student essay writing.

**Two students prompting the same model with equally innocent, differently-worded instructions face
materially different odds of being flagged.** Nothing in the prompt is about hiding anything — the
paper is explicit that these are ordinary quality-oriented constraints. That is a fairness axis
nobody in this ledger had named, it is invisible to every audit design here, and it is invisible to
the institution too, because the instruction is the one artefact a submitted document does not carry.

The sentence now reads "…an editing history, an aggregation rule **and the instruction that produced
the text**".

## ⚠️ A refereed critique of what round twenty-eight shipped

*Machine-Generated Text Localization*
([2024.findings-acl.495](https://aclanthology.org/2024.findings-acl.495/)) calls itself "the first
in-depth study" of localizing machine-generated portions of a document, and its central obstacle is
the one this repo hit independently:

> "short spans of text, e.g., a single sentence, provides little information indicating if it is
> machine generated due to its short length"

**We measured the same wall from the other side** — per-sentence AUROC **0.513** on the stdlib path,
and **26.7%** of pre-LLM human text flagged at **≤50 words** against **15.6%** at 50–100. Their fix
is to predict over **several sentences at once**, so that *changes* in style and content carry the
signal that a lone sentence cannot, worth **4–13% mAP** over prior work.

`score_sentences` scores each sentence independently. So this is a **named, measured improvement path
rather than an open question** — and it makes round twenty-eight's evidence feature more useful, not
less: if the per-sentence *score* is weak, the per-sentence *markers* are the part a human can
actually check, which is the argument that feature was built on.

⛔ Implementing and evaluating it needs model weights this environment cannot load, so it is recorded
with its citation rather than built and left unmeasured.

## Also read, and not acted on

- **AIG-ASAP** ([2023.emnlp-main.644](https://aclanthology.org/2023.emnlp-main.644/)) builds an
  adversarial student-essay corpus and finds detectors "can be easily circumvented using
  straightforward automatic adversarial attacks" — word and sentence substitution. Consistent with
  the evasion literature already covered; adds a student-essay corpus to the list.
- **Ghostbuster** ([2024.naacl-long.95](https://aclanthology.org/2024.naacl-long.95/)) was discussed
  in these documents by name but never by citation, which is why an id-based check reported it
  missing. Nothing was wrong; the check was looking for the wrong thing, and that is worth knowing
  before trusting the next id-based sweep.

---

# Round thirty — the instrument that produced the headline ratio was 40% noise

Checking the three uncited papers in the `fairness` row found all three off-topic: political bias in
pretraining data, cross-lingual misinformation, and persona-prompt stereotypes. **None is about
AI-text-detector fairness.** That is a fault in the instrument, not the corpus, and the instrument is
the one that produces the ratio this whole strategy argues from.

## ✗ The root cause

`DETECTION` carried a bare `|detector` alternative, so it matched **any** detector — Chinese spelling
correction, hallucination detection in machine translation, sarcasm, out-of-distribution detection,
multi-modal retrieval. MEASURED: **213 of 526 matches — 40% — contained no machine-generated-text
phrase at all** and arrived purely through that word.

## ✅ The result that matters: the ratio does not depend on the filter

Three filters were run over the same 31,387 abstracts — the old bare-`detector` one, a phrase-only
strict one, and the proximity filter now shipped:

| filter | detection papers | robustness | false positives | fairness |
|---|---|---|---|---|
| old (bare `detector`) | 526 | 26.4% | 2.5% | 1.5% |
| **new (proximity)** | **565** | **27.1%** | **1.9%** | **2.1%** |
| strict (phrases only) | 313 | 28.8% | 2.6% | 1.6% |

**Robustness stays between 26% and 29%; false positives between 1.9% and 2.6%; fairness between 1.5%
and 2.1%.** The counts move by up to 80% between filters (313 to 565 papers, MEASURED in the table
above); the shares barely move at all. **This is the fourth time
the ratio has survived a change to the corpus beneath it**, and the first time it has survived a
change to the *definition* rather than the sample. The strategy quotes shares from here on, with the
counts as supporting detail.

## Two bugs found while fixing it, both by the tests

**1. A word-boundary bug I introduced.** The first tightened pattern let a Chinese-spelling-correction
paper through on the phrase "detector or corrector and training" — because with `re.I` a bare `AI`
alternative matches **inside "tr*ai*ning"**, and equally inside "domain" and "certain". `\bAI\b` now.

**2. A tightening that made precision worse.** Adding `detect(?:or|ion)` with loose company terms
(`machine|neural|generated`) took the count to **607, above the 526 it was meant to improve on**, by
sweeping in hallucination and fake-news detection. The proximity terms are now restricted to the
AI-authorship senses.

**The phrase-only filter was tested and rejected**, despite the best precision: it drops
[2026.eacl-srw.20](https://aclanthology.org/2026.eacl-srw.20/), the Czech result that **disconfirms
part of our own thesis**. For a ratio, recall loss is worse than residual noise — noise is roughly
flat across topics, while losing on-topic papers biases them unevenly, and losing the one paper that
argues against us biases the corpus toward agreeing with us. Both directions are now pinned by tests:
nine papers the strategy cites must keep counting, four off-topic ones must not.

## ✅ And the finding that unblocks row 28

The new filter returns **one** paper under `disability/neurodivergence` where the old returned zero.
It is *Centering the Margins* ([2023.emnlp-main.579](https://aclanthology.org/2023.emnlp-main.579/)),
about **toxicity** detection — so the published claim survives, now stated precisely: zero studies on
whether **AI-text** detectors flag neurodivergent or disabled writers.

**But its method is the one row 28 needed.** It draws on disability studies — "people farther from
the norm face greater adversity" — and operationalises the margins **by outlier detection**, finding
text about people whose attributes are distant from the norm rather than asking anyone to declare a
protected attribute. Error is **up to 70.4% worse** for those outliers.

Row 28 has been open since round sixteen on the grounds that the blocker was "a consented corpus with
disability metadata, not method." **That was true and is now false**: this measures the same harm
without subgroup labels, on the deployment's own corpus. It is also DivScore's argument reached from
the opposite direction — distance from the reference distribution is the risk — the second time in
this roadmap that a fairness result and a detection-theory result have landed on the same quantity.

**Worth noting how it was found.** Not by searching for it. By checking three papers that a topic row
had miscounted, and following the miscount to its cause.
