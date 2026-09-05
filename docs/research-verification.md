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

That is not a small gap. This entry originally continued: `formulaic phrasing, low burstiness,
regular sentence length, restricted vocabulary, template adherence` are `documented features of some
autistic writing`. ⚠️ **Round seventeen retracted that — no source supports it — and round seventy
found it still standing here**, in backticks now, as a mention of what was withdrawn rather than a
claim. The ACL census found 13
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
length-conditioned curve — 26.7% flagged at ≤50 words against 15.6% at 50–100 — arrived at
independently, and it supplies a corpus for the case. *(Those were the figures at the time. Round
thirty-one re-measured them on the restored corpus as **30.0%** and **21.7%**; the shape of the curve
is unchanged and steeper.)*

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
- `26.7%` and `15.6%` were our own length-band measurements, MEASURED by
  `python -m eval.pre_llm_fpr --by-length`, in a sentence noting SenDetEX reached the same conclusion
  independently. Attribution is by the words "our own", which reads only to a human. Both were
  superseded in round thirty-one.

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

---

# Round thirty-one — the most defensible number in this repo could not be reproduced

Building the outlier fairness arm required the pre-LLM corpus. It did not exist.

## ✗ `eval/pre_llm_fpr.py` returned zero abstracts

`pre_llm_abstracts` selects Anthology text published **no later than 2021**. `VOLUMES` began at
**2023**. MEASURED: **0 pre-LLM abstracts** available to the shipped tool, and the command exits with
"no pre-2022 abstracts in .anthology-cache".

That corpus is the ground truth behind the number this roadmap calls "**the most defensible
false-positive number this repo has, because its ground truth cannot be argued with**" — 15.8% of 120
pre-LLM abstracts, CI [10.4%, 23.4%] — and behind the whole length-conditioned curve. **None of it
could be re-derived by anyone who cloned this repository.** The measurement was real when it was
taken, against a cache that held older volumes; the shipped configuration then stopped producing
them, and nothing noticed, because every test of that module uses synthetic text.

**Thirteen pre-2022 volumes are now in `VOLUMES`**, verified to resolve — note the Anthology uses
year-only ids at that vintage (`2021.acl`, not `2021.acl-long`, which 404s). The corpus is **6,811
pre-LLM abstracts**. They add 13 detection papers to the survey and nothing to its ratio, which is
expected: they predate the field.

## The re-measured numbers, and they moved

| | published | re-measured |
|---|---|---|
| pre-LLM FPR, n = 120 | 15.8% [10.4%, 23.4%] | **19.2% [13.1%, 27.1%]** |
| ≤50 words | 26.7% | **30.0% [22.5%, 38.7%]** |
| 50–100 | 15.6% | **21.7% [15.2%, 29.8%]** |
| 100–200 | 16.9% | **18.5% [12.3%, 26.9%]** |
| 200+ | 0.0% on n=5 | **13.3% on n=15 [3.7%, 37.9%]** |

The intervals overlap throughout, so nothing is *contradicted* — but the point estimates all moved
up, the shape of the length curve is unchanged and steeper, and the published figures were describing
a corpus that no longer exists. Every quotation of them across `ROADMAP.md` and
`research-to-build.md` is updated.

**This is round fifteen's defect in the repository's own headline measurement**, and it is worse than
round fifteen's: that was a survey count drifting between documents, this is a number whose *input*
had silently disappeared while the number stayed published as reproducible.

## ✅ And the arm itself: `eval/outlier_fairness.py`

*Centering the Margins* ([2023.emnlp-main.579](https://aclanthology.org/2023.emnlp-main.579/)) finds
the margins of a dataset by **outlier detection** rather than by subgroup label. This is that method
pointed at AI-text detection, which as of round thirty nobody has published. Five stdlib stylometric
features, a **median/MAD** distance from the corpus centre — robust statistics on purpose, since with
mean and standard deviation an outlier inflates the scale it is measured against and reports itself
as ordinary — then the false-positive rate for the furthest 20% against the rest, with Wilson
intervals on both.

MEASURED on 150 pre-LLM abstracts at lite tier:

| group | n | FPR | 95% CI |
|---|---|---|---|
| margin (furthest 20%) | 30 | 13.3% | [5.3%, 29.7%] |
| centre | 120 | 12.5% | [7.7%, 19.6%] |

**Gap +0.8%, and the intervals overlap, so this is not evidence of a disparity.** That is the honest
result and the tool says it in those words. One weak detector on academic abstracts is close to the
least likely place to find one; the arm exists so the question can be asked on a deployment's own
corpus, where it matters.

**What it must never claim.** Outlier status is not a protected attribute. "Further from the norm"
collects non-native writers, disabled writers, unusual subject matter and anyone with a strong
idiolect — the method's whole value is that it does not need to know which, and its whole risk is
sounding like it does. A test asserts the report still denies it.

Shipped as status row 29. Row 28 stays open and its blocker line is rewritten: the obstacle was never
method, it was that we had not read the paper that solved it.

---

# Round thirty-two — the guard that would have caught round thirty-one, and what it found

Round thirty-one's defect was not that a number was wrong. It was that **every unit test of
`eval/pre_llm_fpr.py` passed while its corpus was empty**, because they all use synthetic text. A
module can be fully covered and completely unable to run.

`tests/test_every_corpus_the_evals_need_can_still_be_built.py` tests the thing those did not: that
the shipped configuration can still build the corpora the published measurements rest on. It skips
when the cache is absent — a contributor should not need a 180 MB download to see green — but a
present cache that yields nothing is the round-thirty-one failure, and it fails.

Two of its checks need no cache at all, because **the defect was in the configuration, not the
download**: `VOLUMES` must span the `max_year` cut-off that `pre_llm_abstracts` reads (taken from the
function's own signature, so the two cannot drift), and there must be at least five volumes below it,
since round fifteen found two volume names that never existed and a single point of failure here is
not hypothetical.

## ✗ It failed on its first run, on volumes added the round before

`2018.acl`, `2018.emnlp`, `2019.acl` and `2019.naacl` were **cached and yielded nothing**. MEASURED
directly against the Anthology repository, they return **HTTP 200 with a 743-byte stub containing
zero papers** — the Anthology used the old `P18-1001` id
scheme at that vintage, in differently-named files. The 200-byte floor in `_fetch` passed them,
because 743 > 200.

**So round thirty-one's fix for a missing corpus itself shipped four volumes that contribute nothing**,
and the guard written to catch that class of defect caught it one round later on the round that
created it. That is now twice — round twenty-seven's cross-check did the same.

## The fix is in the tool, not the list

`download` now parses each volume before caching it and rejects one that yields **zero papers** or is
not XML at all. A byte floor cannot tell a stub from a volume; a paper count can. The four dead names
are gone, and three tests pin the behaviour — a stub is rejected, an HTML error page served as 200 is
rejected, and **a real volume still passes**, because a floor that rejected everything would empty
the corpus silently, which is round thirty-one with extra steps.

Fixing that also exposed an unrealistic fixture: the shared `VOLUME` used by the download tests was
`<collection>` wrapped around 500 x's, with no paper in it. It had been standing in for a real volume
while being exactly the shape the new check rejects.

## Where the corpus now stands

MEASURED by `python -m eval.litreview --download --json` and
`python -c "from eval.pre_llm_fpr import pre_llm_abstracts; ..."`:

| | before round 31 | now |
|---|---|---|
| volumes | 96 | **108** |
| abstracts | 31,387 | **38,231** |
| detection papers | 565 | **578** |
| pre-LLM abstracts | **0** | **6,811** |

Thirteen detection papers across twelve added volumes, which is the expected shape: they predate the
field, and they are here for the false-positive ground truth rather than the survey. **The ratio is
unmoved.** All quotations updated.

---

# Round thirty-three — measuring at the scale the corpus now allows, and reading the pre-ChatGPT field

Round thirty-one restored a corpus of **6,811 pre-LLM abstracts** where the shipped tool had been
building zero. The headline numbers were still being published from **n = 120**, which was the size
that had been available. There was no longer any reason for that.

## ✅ The false-positive rate, at n = 599

| | n = 120 | **n = 599** |
|---|---|---|
| pre-LLM FPR | 19.2% | **20.5%** |
| 95% CI | [13.1%, 27.1%] | **[17.5%, 24.0%]** |
| interval width | 14.0 points | **6.5 points** |

The point estimate barely moved and the interval more than halved. **This is now the best-supported
number in the repository**: known-human text by construction, 599 documents, and a command anyone can
re-run.

## ⚠️ The outlier arm at n = 600 — a gap that grew and still does not clear the bar

| group | n | FPR | 95% CI |
|---|---|---|---|
| margin (furthest 20%) | 120 | **21.7%** | [15.2%, 29.9%] |
| centre | 480 | **16.9%** | [13.8%, 20.5%] |

**Gap +4.8%, up from +0.8% at n = 150 — and the intervals still overlap.** Writers whose prose sits
furthest from the corpus norm were falsely accused at 21.7% against 16.9% for everyone else, on text
that predates the models entirely.

**That is not a finding, and it is important not to round it into one.** The margin interval runs from
15.2% to 29.9% and the centre's upper bound is 20.5%; they overlap, so the honest statement is that
the direction is consistent with *Centering the Margins* and the magnitude is now large enough to be
worth chasing, on one weak detector, in a single domain. The tool prints "the intervals OVERLAP, so
this gap is not evidence of a disparity" and that sentence is the result.

What makes it worth recording rather than discarding: **the gap grew fourfold when the sample grew
fourfold**, which is what a real effect does and what noise usually does not. It is the first thing
in this repository that would obviously be worth re-running with the full ensemble.

## The field before ChatGPT, now visible for the first time

The 2020–2021 volumes added for ground truth also brought **13 pre-ChatGPT detection papers** into
view. Three are foundational and had never been cited here:

✅ **Detection is easiest exactly when humans are worst.** *Automatic Detection of Generated Text is
Easiest when Humans are Fooled* ([2020.acl-main.164](https://aclanthology.org/2020.acl-main.164/))
benchmarks top-k, nucleus and untruncated sampling and finds that "improvements in decoding methods
have primarily optimized for fooling humans. **This comes at the expense of introducing statistical
abnormalities that make detection easy for automatic systems.**" And: "even multi-sentence excerpts
can fool expert human raters **over 30% of the time**."

**This inverts the usual framing of human review.** Round five established that a label corrupts a
reviewer's judgment; round nine that most humans detect poorly. This adds the mechanism: the two
failure modes are *anti-correlated by construction*, because generators are tuned against human
perception. A human reviewer is least able to help precisely where the detector is most confident,
and most needed where the detector is weakest. **From 2020**, and the strategy had never carried it.

✅ **Untrained human evaluators are at chance on GPT-3.** *All That's 'Human' Is Not Gold*
([2021.acl-long.565](https://aclanthology.org/2021.acl-long.565/)): non-experts "distinguished
between GPT3- and human-authored text at **random chance level**", and three training regimes lifted
accuracy only to **55%**, not significantly across stories, news and recipes. That is the pre-ChatGPT
baseline for "a human will review the flag", and it was already chance-level three years before the
tools this repository audits were deployed.

✅ **The field had a critical survey before the boom.** *Automatic Detection of Machine Generated
Text: A Critical Survey* ([2020.coling-main.208](https://aclanthology.org/2020.coling-main.208/))
surveys the literature and runs "an in-depth error analysis of the state-of-the-art detector."

**What the pre-ChatGPT slice shows.** Thirteen detection papers across two years of the Anthology's
main venues, against 578 in the corpus overall. The field is almost entirely post-2022 — which is the
context for every "nobody has done this" claim in these documents, and part of why four of them have
turned out to be false: a literature that grew this fast is one where the thing nobody had done last
year was published this year.

---

# Round thirty-four — the sensitivity analysis I should have run before publishing the gap

Round thirty-three published one number from the outlier arm: **+4.8%**, the gap at the furthest 20%.
Where that line falls is a **free parameter**, and a gap that appears at one setting of a free
parameter is a choice rather than a finding. `--sweep` now reports it at every cut-off from the
furthest 5% to the furthest 40%, scoring the corpus once and splitting it seven ways.

MEASURED on 600 pre-LLM abstracts, lite tier:

| furthest | margin n | margin FPR | centre FPR | gap | intervals separate? |
|---|---|---|---|---|---|
| 5% | 30 | 23.3% | 17.5% | **+5.8%** | no |
| 10% | 60 | 18.3% | 17.8% | +0.5% | no |
| 15% | 90 | 21.1% | 17.2% | +3.9% | no |
| **20%** | 120 | 21.7% | 16.9% | **+4.8%** | no |
| 25% | 150 | 20.0% | 17.1% | +2.9% | no |
| 30% | 180 | 19.4% | 17.1% | +2.3% | no |
| 40% | 240 | 20.0% | 16.4% | +3.6% | no |

**The gap keeps its sign at all seven cut-offs. No cut-off separates the intervals.**

Both halves matter and they say different things. A sign that survives every cut is not what noise
usually does — the margins are flagged more often than the centre however the margin is defined.
And not one of the seven comparisons clears its confidence intervals, so **none of them is evidence
of a disparity**, and the tool prints that sentence.

## The same sweep at n = 2,400 — four times the corpus

MEASURED on 2,400 pre-LLM abstracts:

| furthest | margin n | margin FPR (95% CI) | centre FPR (95% CI) | gap | separate? |
|---|---|---|---|---|---|
| 5% | 120 | 20.8% [14.5, 28.9] | 19.9% [18.3, 21.6] | +1.0% | no |
| 10% | 240 | 20.4% [15.8, 26.0] | 19.9% [18.2, 21.6] | +0.6% | no |
| 15% | 360 | 22.8% [18.8, 27.4] | 19.4% [17.7, 21.2] | +3.4% | no |
| **20%** | 480 | **24.0% [20.4, 28.0]** | **18.9% [17.2, 20.7]** | **+5.1%** | **no — by 0.3 points** |
| 25% | 600 | 22.2% [19.0, 25.7] | 19.2% [17.4, 21.0] | +3.0% | no |
| 30% | 720 | 21.8% [18.9, 25.0] | 19.1% [17.3, 21.1] | +2.7% | no |
| 40% | 960 | 22.2% [19.7, 24.9] | 18.4% [16.5, 20.5] | +3.8% | no |

**The sign holds at all seven cut-offs again, and still nothing separates** — but at the 20% cut the
intervals now miss each other by **0.3 percentage points**, MEASURED from the table above as the
margin's lower bound 20.4% against the centre's upper bound 20.7%. Quadrupling the corpus moved the 20% gap from +4.8% to +5.1% and shrank
the overlap from wide to almost nothing.

**It is still not evidence of a disparity, and the tool still says so.** "Almost separating" is not a
result; a 0.3-point overlap and a 3-point overlap are both overlaps, and treating the first as nearly
a finding is exactly the reasoning this repository exists to argue against. What can be said: the
effect is stable in sign across seven cut-offs and two sample sizes, its magnitude at the 20% cut is
consistent across a fourfold increase in n, and **one weak detector on 2,400 academic abstracts is
still not enough to establish it.**

## ⚠️ What the sweep says about round thirty-three

**The +4.8% published last round sat near the top of a +0.5% to +5.8% range** — the n = 600 sweep
table above. Publishing it as *the*
gap was mildly flattering to the hypothesis — not wrong, since it was the 20% cut chosen before the
answer was known and the sign held everywhere, but it presented the second-largest of seven available
numbers as the result. The status row now carries the range and the verdict instead of one figure.

**This is the analysis that should have run before the number was published, not after.** Every other
guard in this ledger checks whether a claim matches its source; this one checks whether a claim
survives a choice its author made. Nothing here was testing for that.

## The refactor, and why it is the point

`probe_sweep` scores the corpus **once** and splits it seven ways, and a test asserts `_score_all` is
called exactly once. If the sweep rescored per cut-off it would cost seven times as much and would
quietly stop being run — which is how a sensitivity analysis becomes optional and then absent.
`probe_by_distance` now shares `_split` with it, and a test asserts the two agree at the same
cut-off, because two implementations of one comparison is how a headline and its own sensitivity
check drift apart.

---

# Round thirty-five — the same defect one level down, in the number quoted most

Round thirty-four found that the outlier gap depended on where the margin line was drawn. That
prompted an obvious question nobody had asked: **what other published number here rests on a
parameter chosen once and never varied?**

`pre_llm_abstracts` takes a `min_words` floor, default 60. The headline false-positive rate is
measured on whatever it returns. MEASURED at n = 300 each:

| word floor | FPR | 95% CI |
|---|---|---|
| 30 | 22.0% | [17.7%, 27.0%] |
| **60 — the published setting** | **22.7%** | [18.3%, 27.8%] |
| 100 | 18.3% | [14.4%, 23.1%] |
| 150 | **14.3%** | [10.8%, 18.8%] |

**An 8.4-point swing from a parameter no document mentioned**, and the intervals at 60 and 150 barely
overlap. It is not noise: it is this repository's own length effect — **30.0% flagged at ≤50 words
against 13.3% at 200+** — reaching the headline through the corpus floor. Raising the floor removes
the short documents that drive the rate up.

**So there is no such thing as "the" pre-LLM false-positive rate.** There is one per corpus
definition. The published figure is now stated as *20.5% on documents of 60 or more words*, and that
clause is load-bearing rather than decorative.

## ✗ And the report did not say which corpus it described

A saved JSON result carried `tier`, `n_scored`, `detectors_scoring` and the rates — **and nothing
about the text it had scored.** No word floor, no year cut-off, no seed, no corpus size. Two runs
could not be compared and neither could be reproduced from its own output.

Every report now carries a `corpus` block: `min_words`, `max_year`, `seed`, `n_available`,
`n_requested`. The terminal rendering prints it, **with the sensitivity in the same breath** — "the
word floor moves this number: 22.0% at 30 words against 14.3% at 150" — because someone reading a
number off a terminal is exactly the reader who will not go looking for the caveat.

Five tests hold it, including one that checks the recorded floor is **the one actually used** (a field
that always said 60 would be worse than no field) and one that checks a higher floor really does
exclude texts, because recording a parameter that does nothing is ceremony.

## The pattern across rounds thirty-four and thirty-five

Both defects are the same shape and neither is a factual error. Every number involved was correctly
measured and correctly reported. What was missing is that **each rested on a choice, and the choice
was invisible in the output.**

The guards built in rounds sixteen to thirty-two all ask *does this claim match its source?* That
question cannot see this failure at all — the source is our own tool, and the tool was telling the
truth about a corpus it declined to describe. **The reusable rule: a measured number must ship with
every parameter that would move it, and the ones most worth naming are the ones that were never
chosen deliberately in the first place.**

---

# Round thirty-six — the finding I nearly published, and the control that killed it

The full-corpus sweep finished. At **n = 6,810** the outlier gap looked like a result:

| furthest | margin n | margin FPR | centre FPR | gap | separates? |
|---|---|---|---|---|---|
| 5% | 340 | 22.1% [18.0, 26.8] | 19.3% [18.4, 20.3] | +2.7% | no |
| 10% | 681 | 22.0% [19.1, 25.3] | 19.2% [18.2, 20.2] | +2.8% | no |
| 15% | 1021 | 22.9% [20.4, 25.6] | 18.9% [17.9, 19.9] | +4.1% | **YES** |
| **20%** | 1362 | 23.1% [21.0, 25.4] | 18.6% [17.5, 19.6] | **+4.6%** | **YES** |
| 25% | 1702 | 22.9% [20.9, 24.9] | 18.3% [17.3, 19.4] | +4.5% | **YES** |
| 30% | 2043 | 22.7% [20.9, 24.5] | 18.1% [17.0, 19.2] | +4.6% | **YES** |
| 40% | 2724 | 22.5% [21.0, 24.1] | 17.4% [16.3, 18.6] | +5.1% | **YES** |

Sign consistent at all seven cut-offs, **five of seven separating their intervals**, effect size
around +4.6 points on a base of 18.6% — a quarter more false accusations for writers furthest from
the corpus norm. It would have been the strongest empirical result in this repository and, as far as
round thirty could tell, the first outlier-based false-positive measurement for AI-text detection
anywhere.

## ✗ It is largely a length artefact

The margin is chosen on stylometry, and **stylometry is not length-neutral**. MEASURED on 2,000
pre-LLM abstracts, the furthest 20% has a **median of 124 words against 149** for the centre. Dropping
`words` from the feature set entirely barely changes it — **132 against 148** — because type-token
ratio and sentence-length variation are themselves length-dependent. And this repository has already
measured the length effect: **30.0% flagged at ≤50 words against 13.3% at 200+**.

So the control is to compare margin against centre *inside* word-count bands. MEASURED, n = 2,000:

| band | margin n | margin | centre | gap | separates? |
|---|---|---|---|---|---|
| 60–100 | 43 | 44.2% | 27.3% | **+16.9%** | no |
| 100–150 | 187 | 17.6% | 21.5% | **−3.9%** | no |
| 150–220 | 162 | 19.1% | 15.3% | **+3.9%** | no |
| 220+ | 36 | — | — | too few | — |

**The gap changes sign between bands and no band separates its intervals.** Once length is held
roughly constant the effect does not hold. The unstratified figure was measuring document length and
would have been reported as a disparity.

`--by-length` ships as part of the tool rather than as a footnote, and its rendering says the
conclusion in words: *"The gap CHANGES SIGN between bands — once length is held roughly constant the
effect does not hold, so an unstratified figure is measuring length."*

## ⚠️ A latent alignment bug, found while building the control

The first version of `probe_stratified` re-paired texts with flags **positionally**, which is correct
only while `_score_all` drops nothing. A single document no detector scores shifts every later flag
onto the wrong text — **a wrong answer with no error**, which is the worst shape a bug can take in an
audit tool. `_score_all` now returns the texts it kept, and a test forces the drop and checks the
pairing survives it. Nothing was dropped in the runs above, so the numbers stand; the bug was latent
and is now impossible.

## What this round is

Rounds thirty-four and thirty-five found numbers that rested on invisible choices. **This one found a
result that rested on a confound**, and the difference matters: a sensitivity sweep would never have
caught it, because the gap was robust to the parameter I thought to vary. Seven cut-offs all agreed.
Two sample sizes agreed. The sign was consistent, the magnitude was stable, five of seven comparisons
cleared their intervals — **every check I had built said yes.**

What caught it was asking what else the margin could be selecting for, and the answer was available
in this repository's own published measurements. The reusable rule is not "run a sensitivity sweep";
it is that **agreement among your own checks is not evidence, when every check shares an assumption.**

---

# Round thirty-seven — the same confound, pointed at everything else

Round thirty-six killed a result of ours with a length control. The obvious next question is whether
anything **else** here — or in the literature this strategy quotes — has the same shape.

## ✅ Our other fairness arm was checked, and passes

`eval/assisted_fairness.py` compares native against non-native authors and inherits exactly the risk:
if one group's abstracts are systematically shorter, its higher flag rate is document length, not
author status. MEASURED on the Pratama corpus:

| arm | Native median words | Non-Native median words |
|---|---|---|
| human | 180 | 176 |
| assisted (ChatGPT) | 136 | 135 |
| assisted (Gemini) | 189 | 201 |
| generated (ChatGPT) | 153 | 150 |
| generated (Gemini) | 158 | 156 |

**Worst relative gap 7.8%**, against a threshold of 15% — well below the range over which this repo
has measured the flag rate moving, and the corpus is matched by design at 36 documents per group per
arm. **The arm's disparity is not the length effect in disguise.**

That is a negative result and it is the point: the check was run rather than assumed. It now ships
inside `evaluate`'s report and prints above the rates every run — "Length check: groups ARE
length-matched (worst median gap 7.8%), so these rates are comparable" — because **a confound check
in a separate command is a confound check nobody runs.** Six tests hold it, including one that fails
if the real corpus ever stops being matched, and one that proves an unmatched corpus is actually
caught rather than waved through.

## ⚠️ And the deployment finding this strategy leans on hardest has it

Round fourteen's admissions cluster is the most consequential evidence in this ledger, and the
sentence it turns on is Subillaga et al.'s: the flagged group had **non-English native language
characteristics 38.7% against 19.6% (p<0.001)** — *and* **shorter statements, shorter sentences.**

Those are two correlated facts about one group, and the study reports both plainly without separating
them. Round thirty-six is the reason that matters: our own outlier gap **separated its intervals at
five of seven cut-offs on 6,810 documents and still turned out to be length**. GPTZero and Copyleaks
flag short text more often; the flagged applicants wrote shorter statements; the flagged applicants
were also more likely to be non-native. **Without a length-stratified re-analysis of those 1,490
statements it cannot be said how much of that split is language background and how much is document
length.**

This does not weaken the deployment argument — 36.6% against 21.2% depending on the tool is a fact
about aggregation regardless of what drives the subgroup skew, and a false accusation costs the same
either way. What it changes is the **inference the number invites**: "detectors are biased against
non-native writers" is a stronger claim than the data separates, and this repository has now made
exactly that error once, on its own data, with better statistics than the paper reports.

**The honest position is the one this strategy already argues for everyone else's numbers:** the
disparity is real, its cause is not established, and the only way to find out is to stratify on the
deployment's own corpus. That is what `--by-length` now does for the outlier arm and what
`length_balance` now does for the author-status arm.

---

# Round thirty-eight — the method for the problem rounds thirty-six and thirty-seven found

Two rounds established that **length is the dominant nuisance variable** in every false-positive
comparison this project makes, and that our own strongest result and the deployment literature's
central finding both carry it. Naming a confound is not the same as handling one.

Epidemiology handled it a century ago. Crude mortality is higher in Florida than Alaska because
Florida is older, and **direct standardization** — apply one population's rates to the other's
composition — separates the part worth comparing from the part that is just who lives there.
`eval/length_standardized.py` does that with word counts.

**What it is for.** A program director comparing their flag rate against a published one is comparing
two corpora with different length profiles. The difference between *"our applicants are flagged more
than the study's"* and *"our applicants write shorter statements than the study's"* is the entire
question, and nothing in this repository could answer it before now.

**What it cannot do**, stated in the module and printed in every report: standardization removes the
length composition difference **and nothing else**. Two corpora matched on length still differ by
domain, generator, editing history, prompt and aggregation rule — the other five terms this
repository insists a false-positive rate depends on.

## ✗ The self-check caught the module's own first version

`main` standardizes one half of the pre-LLM corpus against the other. **Two halves of one corpus
should agree**, so the design is a self-check as well as a demonstration. The first version reported
**crude 20.4% against standardized 11.2%** — a nine-point gap that could not possibly be real.

The cause: band rates were drawn from `pre_llm_fpr.probe_by_length`, which **truncates every abstract
to the top of every band it reaches**, so one 150-word abstract contributes a scored sample to 0–50,
50–100 *and* 100–200. The weights, meanwhile, counted each document once, in the band its natural
length falls in. **Rates from one population, weights from another.**

That truncation is right for its own question — *how does this detector behave as length varies,
holding the text fixed* — and wrong for this one. `rates_by_natural_length` now scores each document
**once, whole**, in the band its own length falls in, and a test asserts three 150-word documents
produce exactly three scorings rather than nine.

After the fix, MEASURED by `python -m eval.length_standardized`, standardizing one half of the
pre-LLM corpus against the other:

| documents per half | crude | standardized | gap |
|---|---|---|---|
| 250 | 18.4% | 13.6% | 4.8 points |
| **900** | **20.3%** | **19.0%** | **1.4 points** |

**The gap shrinks toward zero as the sample grows**, which is what a self-check should do and is the
evidence that the residual is per-band sampling noise rather than a second bug: at 250 per half the
50–100 band holds roughly twenty documents, and a rate estimated from twenty documents is not stable
enough to standardize with. At 900 the two halves agree to within 1.4 points.

## What is worth noticing about this round

The bug was found **by a design choice made before the code was written**: standardizing a corpus
against itself has a known answer, so the demonstration doubles as a test with a ground truth. Every
guard built in rounds sixteen to thirty-two compares a claim against a source. This one compares a
computation against **arithmetic that cannot be wrong**, which is the only kind of check that catches
an error in the method rather than in the reporting.

Seven tests hold it, including the identity case — a corpus standardized against its own rates must
return its own crude rate — and the coverage rule: a band with no measured rate is dropped and
**reported as dropped**, because silently treating it as 0% would bias every figure downward while
looking exactly the same.

---

# Round thirty-nine — proving the arithmetic, and a stale number in a docstring

Round thirty-eight's lesson was that a check against arithmetic beats a check against a source,
because it can catch an error in the method rather than in the reporting. This round applies that to
the two computations everything else here depends on.

## ✅ The aggregation ordering, proved rather than sampled

Every claim this project makes about aggregation rests on one relationship: **unanimous implies
majority implies union**. The published spreads — 44.44% / 4.17% / 0.0% on Pratama's abstracts,
36.6% / 21.2% in a live residency match — are only interpretable if that ordering cannot break.

The existing tests checked chosen cases. There are now tests that **enumerate every possible flag
pattern for one to seven detectors — 254 outcomes**, which is not a sample of the input space, it is
all of it. They pin the ordering, the consistency of the counts with the verdicts, and monotonicity
(an extra flagging detector can never turn a rule off).

Two are worth naming. **One detector makes the three rules identical** — the claim behind the
`degenerate` warning both tools print, now proved for every single-detector outcome rather than
asserted in a comment. And a **guard on the guard**: at least one hundred of the 254 patterns must
separate the three rules, because every other assertion in the file would hold vacuously if they
always agreed.

## ✅ The intervals, pinned to Wilson specifically

169 published proportions carry intervals and a test fails if one does not. That guarded *presence*.
Nothing guarded *correctness* — and the intervals are what every "the gap is not evidence of a
disparity" verdict in rounds thirty-four to thirty-seven turns on. **A systematically narrow interval
would have converted those honest negatives into findings.**

Now checked: the interval stays inside [0, 1], contains its point estimate, narrows with n (the
property the whole n = 120 → 599 → 2,400 → 6,810 progression relies on), leans upward near zero, and
**matches two textbook Wilson values to three decimals** — because every other property would hold
for a formula wrong by a constant factor.

Also pinned: **0 of 15 must not imply a rate near zero.** The 200+ word band reads 0.0% and the
roadmap quotes its interval to 37.9%; a zero-width interval there would make that row read as proof.

## ✗ And a stale number in a docstring, seven rounds old

Round thirty-one re-measured the pre-LLM rate and updated every document. `untell/calibrate.py` went
on saying:

> "This repo measured **26.7%** false positives at 50 words or fewer against **15.6%** at 50-100"

Those are the superseded figures. The current ones are **30.0%** and **21.7%**. Its module docstring
likewise still offered **15.8%** where the measurement is now **20.5%**.

**`untell-audit` scans documents and nothing scanned source.** That is the gap, and a stale figure in
a docstring is worse than one in a document: this one is the **stated justification for a shipped
default** — the reason `calibrate_by_length` sets per-band thresholds at all.

The retraction guard now scans `untell/` and `eval/` as well as the documents, with an exemption for
lines that explicitly describe a figure as historical, and a test asserting that exemption cannot
swallow an ordinary docstring. Three superseded figures are pinned by the replacement they became, so
a failure names the fix rather than only the fault.

## A footnote: the pre-existing failure is fixed, by accident

`test_docs_claims.py::test_why_best_test_count_is_not_stale` failed on `main` and on this branch for
this entire session, and every round reported it as environmental. It was — the container cannot
collect four torch-dependent files, so the documented count sat above what this machine could see.

This round's 600-odd new tests pushed the collected count past the documented one and **the assertion
flipped to its other side**: the doc now understated by 708, which the same test also catches. The
figure is updated to **9,958 tests across 620 modules**.

Worth stating plainly: **9,958 is a floor, not a count** — MEASURED by
`UNTELL_LITE_NO_TORCH=1 pytest --collect-only -q`, which reports it alongside 4 collection errors.
Four files still fail to import here, so a complete environment collects more. The documented figure has to be the smaller of the tiers for the
assertion to mean anything, and a floor satisfies that — but nobody should read it as the size of the
suite.

---

# Round forty — closing the gap that let round thirty-nine ship broken

Round thirty-nine was committed and pushed while `untell-audit` was failing. The audit and the commit
ran in one shell sequence that did not gate on the audit's exit code, so an unattributed figure went
out and was corrected in the next commit.

CI would have caught it. **After the push** — in a public failure, on a branch somebody else might
have pulled. Being more careful is not a fix; the sequence was wrong, not the attention paid to it.

`.githooks/pre-commit` refuses a commit CI would reject, scoped by what changed:

| change | gate |
|---|---|
| any `.py` | `ruff check .` |
| any `.md` | the documentation guards |
| a live document | `untell-audit` |

The scoping is the design decision. `untell-audit` takes about a minute, and **a gate slow enough to
skip is a gate nobody runs** — so it fires only on the documents it actually reads. `--no-verify`
bypasses everything, documented in the hook itself, because a gate with no escape hatch gets
uninstalled the first time somebody needs a work-in-progress commit and then protects nothing.

**Verified by using it, not by reading it.** A Python file with two lint errors was refused and `HEAD`
stayed put; a ROADMAP row renumbered to break the status guard was refused; `--no-verify` committed.

⚠️ **And the first attempt to test it was a bad test.** Appending *"a completely made-up 73.4%
figure"* to the ledger did not trip the audit — the attribution window is ±12 lines and it picked up
a `MEASURED` from the paragraph above. The hook was fine; **the probe was passing for a reason that
had nothing to do with what it was probing**, which is the same defect as a test that would pass with
the feature deleted. The real probes replaced it.

## What the tests check, and what they deliberately do not

They check the hook's **content**: that it is versioned rather than sitting untracked in `.git/hooks`,
that it is executable (git skips a non-executable hook **in silence**, which is indistinguishable
from a passing gate), that every gate CI runs is still named in it, that the failure path ends in
`exit 1` rather than a warning, and that installation is documented in `CONTRIBUTING.md` — because
`core.hooksPath` is not set by cloning, so **uninstalled is the default state.**

They do not shell out to `git commit`. That test would be slower and more fragile than the thing it
guards. What can drift silently here is the *list of checks*: a hook that stops running the audit is
faster and looks identical.

---

# Round forty-one — checking whether my own tests would notice

Round forty ended on a probe that passed for a reason unrelated to what it was probing. The obvious
next question is how much of this session's testing has that shape, and there is a way to find out
that does not depend on my judgement: **break the code and see whether anything complains.**

Nine mutations, aimed at the statistical machinery because that is where a wrong answer is invisible
— a detector that scores slightly wrong shows up in the output, an interval slightly too narrow turns
an honest negative into a finding, and rounds thirty-four to thirty-seven rest entirely on those
intervals.

## ✗ Three survived, all in code written the same day

| mutation | outcome |
|---|---|
| `outlier_scores`: median → mean | **SURVIVED** |
| `outlier_scores`: MAD → standard deviation | **SURVIVED** |
| margin cut off by one | **SURVIVED** |
| `standardize`: drop coverage renormalisation | killed |
| `agreement`: majority → "at least half" | killed |
| `agreement`: unanimous → "all but one" | killed |
| Wilson: drop the continuity term | killed |
| Wilson: drop the centre shift | killed |
| `outlier_scores`: drop length from the features | killed |

**The robustness test was the worst of them.** `test_the_centre_is_robust_to_the_outliers_it_is_measuring`
asserted that an odd document scored above 1.0 — a bar a non-robust implementation clears easily. Its
docstring explained, correctly and at length, why median and MAD matter; its assertion checked that
the function returned a number. Round thirty-eight's module docstring makes the same argument, and
**both substitutions it warns against passed the test written to prevent them.**

The off-by-one survived for a related reason: every assertion in that file was about rates and signs,
and none about **how many documents landed on each side.** A cut taking 21 documents instead of 20
changes a small-n rate and no test looked.

All three now have killing tests: the odd document must keep half its distance when a 4,000-word
outlier is added, and the margin must contain exactly the requested share at every quantile the sweep
uses.

## The sweep ships, and is itself guarded

`scripts/mutation_sweep.py` makes it repeatable, following the pattern
`tests/test_audit_mutation_guards.py` already documents — sweep, then write a killing test for every
survivor. It refuses to run on a dirty tree, because it edits source files and restores them from
memory.

And it has its own failure mode: **every mutant is a literal string that must appear in the source**,
so a refactor rewriting one of those lines turns its mutant into a no-op and the sweep reports nine
kills while testing eight things. Twenty-eight tests check that every pattern still matches, that
applying it changes the file, and that the four modules carrying the statistics are all covered.

⚠️ **And that guard's first assertion was wrong.** Checking `new not in source` looked obviously
right and fired on a perfectly good mutation: one mutant drops a trailing `+ ["words"]`, so its
replacement is a *substring* of the original. The property that matters is not whether the mutated
text is absent but whether performing the replacement changes anything — `source.replace(old, new) !=
source`. **A test written to catch no-op mutations was itself nearly a no-op.**

---

# Round forty-two — the second sweep, and a survivor that needed the right question

Round forty-one's sweep covered nine lines. This one adds eight more, across the calibration, the
agreement flags, the length-balance bar and the corpus filter — everywhere a wrong answer would be
invisible in the output.

**Six of the eight died immediately**, including both mutations of the conformal threshold (dropping
the finite-sample correction, and an off-by-one in the rank), the `degenerate` flag never firing, and
the length-balance bar loosened tenfold so nothing is ever reported as unmatched. That last one
mattering is the point: a confound check whose threshold has been quietly widened looks exactly like
a confound check that passes.

## ✗ Two survived

**Type-token ratio mutated to a constant and nothing noticed** — MEASURED by
`python scripts/mutation_sweep.py`, replacing `len(set(words)) / len(words)` with
`len(words) / len(words)`. No test asked whether the five
stylometric features are *informative* — a feature stuck at a constant contributes nothing to the
distance, silently reducing a five-signal margin to a four-signal one, invisibly in every number the
module prints. Two tests now cover it: each feature must vary with the thing it names, and **no
feature may be constant across the corpus**, because a constant cannot separate anything.

**And the band-boundary mutant took two attempts to kill**, which is the more instructive one.

## ⚠️ A killing test that did not kill

`low <= words < high` mutated to `low <= words <= high`. The obvious consequence is double-counting,
so the obvious test is that the profile still sums to 1.0. **It does — and the mutant survived it.**

`length_profile` **breaks after the first matching band**, so an inclusive upper bound cannot
double-count. What it does instead is **misassign**: a document of exactly 100 words matches
`(50, 100]` first and lands in the 50–100 band rather than 100–200. It moves between bands with
different measured rates, and the profile sums to one the whole way.

**The test asserted the consequence I imagined rather than the one the code has.** Round forty-one
found tests whose assertions were weaker than their docstrings; this is a test whose assertion was
about the wrong mechanism entirely, and it looked more rigorous than the one that works. The
assertion that kills it checks *which band* a boundary document lands in.

Then it failed on unmutated code, because the top band is named `200+` and not `200-`, and I had
written `startswith(f"{low}-")`. **Three attempts to state one boundary condition correctly** — which
is a reasonable argument for having a mutation sweep at all, rather than trusting that a test written
carefully is a test that works.

**17 of 17 now killed.**

---

# Round forty-three — three survivors I nearly wrote off as unkillable

A third sweep, over the download guard, the evidence surface, the corpus filter and the alignment
fix: eight more mutants, **five killed immediately**, three survived.

The interesting part is what happened next. All three looked like **equivalent mutants** — changes
that cannot alter behaviour because another check already covers the case — and an equivalent mutant
is legitimately exempt rather than a test gap. Two of the three were not.

## ✗ "The byte floor is redundant" — wrong

`_fetch` rejects a body under 200 bytes, then rejects one that will not parse, then one with zero
papers. Dropping the floor survived every test, and the reason looked conclusive: every probe used a
body that was either unparseable (`b"not found"`) or paperless (`<collection/>`), and the later
checks catch both.

But those are not the only small bodies. **A 94-byte body that parses AND contains a paper** passes
the later checks and is nowhere near an Anthology volume — which is what a transfer truncated a few
hundred bytes in looks like. The floor's job is exactly the case the probes did not cover.

## ✗ "Calibrate is double-guarded" — also wrong

`calibrate` refuses when `n < required_samples(alpha)`, and further down there is a check the comment
itself calls defensive: `if rank > n: return None`. Removing the first one survived, and the second
does catch every case a *tight* alpha produces — at α = 0.05 the rank exceeds n whenever the sample
is too small.

It does not catch a **loose** one. MEASURED from the formula `ceil((n + 1)(1 - alpha))`: at α = 0.5
with 5 scores the rank is 3, comfortably inside the sample, so without the first guard `calibrate`
would return a threshold derived from five documents. `MIN_CALIBRATION = 20` — read from
`untell/calibrate.py` — is why there are two guards, and the second cannot stand in for the first.

## ✅ And one that really was a plain test gap

The length-balance check applies its own `min_words` floor, and every fixture had been comfortably
long. It matters because `evaluate` skips texts under 50 words when scoring them: a balance check
counting them would describe a **different set of documents from the one the flag rates come from**,
and could report a corpus as unmatched on the strength of texts that were never scored.

## What this round is actually about

**"Equivalent mutant" is the most comfortable conclusion available**, and I reached for it twice in a
row on evidence that looked airtight both times — a redundant guard, a double-checked precondition.
The reasoning was sound and the premise was wrong: in each case the "covering" check covers a
*different region* of the input space, and the probes I had happened to sit in the overlap.

Checking took one command each. **25 of 25 mutants now killed**, MEASURED by
`python scripts/mutation_sweep.py`, and the three tests that kill these
document the exact input each guard exists for, which is what the earlier tests were missing.

---

# Round forty-four — the gate was too slow, and the check that read 9,958 as 958

Round forty-three's commit hit a two-minute timeout while the pre-commit hook ran. That is the
failure mode the hook's own design note warns about: **a gate slow enough to skip is a gate nobody
runs.** Profiling rather than guessing found where the time went.

## ✅ 58 of the audit's 70 seconds were one function

`check_no_dead_functions` ran `re.findall(rf"\b{name}\b", corpus)` **once per function** over a
multi-megabyte corpus — 570 scans, O(functions × codebase). Tokenising the corpus once into a
`Counter` and looking each name up is O(corpus + functions).

MEASURED: **59.0s against 0.3s, a 212× speedup**, with **identical counts for every name** and an
identical verdict. `\b\w+\b` is the same match as `\b{name}\b` when the name is a Python identifier,
which every one of them is. The whole audit went **70s → 10.5s**.

The counts were compared before the change was made, not after. An optimisation that quietly stops
finding things looks exactly like a fast, passing check — so four tests exercise the check against a
function that really is dead, including that a name mentioned only in prose still counts as
referenced (the repo dispatches by string name) and that `score_text` does **not** rescue a dead
`score` (word boundaries, the property the rewrite had to preserve).

## ✗ And the audit was misreading its own numbers

Applying that broke a test, which turned out to be unrelated and older. `check_test_count_claims`
matches `(\d{3,5})\s+tests`, and the round-thirty-nine footnote says **"9,958 tests"**. The digit run
stops at the comma, so the check read it as 958 — MEASURED, it reported the document as claiming a
count of 958 where the suite collects 10,061.

*(Written as `958 tests` in backticks. Phrased as plain prose it trips the very check it describes —
which is what happened when this entry was first written, and four more times afterwards. Round
fifty-five gave the audit the use/mention distinction so this sentence can simply say what it means.)*

**A false alarm accusing a correct document of understating by an order of magnitude** — the kind
that gets a check switched off. The pattern now accepts `[\d,]` and strips the separators.

## ⚠️ Two of my own tests, again

The tests written to pin the comma fix patched **`LIVE_DOCS`**. `check_test_count_claims` iterates
**`COMPARATIVE_DOCS`**, so the fixture file was never scanned and **five of the six cases passed
vacuously.** The sixth — the "guards the guard" case asserting a *wrong* count is still caught — was
the only one that failed, and it is the reason the vacuity was found at all.

Then, to check the corrected tests were not vacuous either, I reverted the pattern and confirmed
three of them fail. `git checkout untell/scripts/audit.py` reverted **the whole file**, silently
discarding the 212× speedup along with it; the audit still passed, ten times slower, and nothing
would have said so. Both changes were reapplied and re-verified.

**The recurring shape across rounds forty to forty-four:** every one of these was a test or a check
that passed for a reason unrelated to what it was testing. Four rounds running. The only thing that
has reliably caught them is deliberately breaking the thing under test and requiring a failure.

---

# Round forty-five — a floor under the failure that kept recurring

Four rounds in a row produced the same defect: a test passing for a reason unrelated to what it
tested. A probe whose input the audit never rejected; a robustness test whose assertion checked only
that a number came back; a boundary test aimed at the wrong mechanism; five cases that patched
`LIVE_DOCS` where the check reads `COMPARATIVE_DOCS`. Every one was found by accident — a mutation
that survived, or one sibling assertion that happened to fail.

`--vacuity` makes it systematic. It replaces **every public function body in a module with a raise**
and requires that module's test file to fail. MEASURED across the eleven test files written this
session: **11 of 11 noticed.** No test file here is entirely decorative.

## What it can and cannot do

It is deliberately coarse, and the mutation sweep is the fine instrument. **One alert test carries a
whole file**, so a file with nine vacuous tests and one real one passes. What it catches is the case
where the test file and the code under test are *not connected at all* — which is exactly what
happened with `LIVE_DOCS`, where the fixture was never scanned by the check it was meant to exercise.

The two together give a floor and a ceiling: the sweep proves specific lines are guarded, the vacuity
check proves the guarding is aimed at the right module.

## Guarding the guard, since that is the whole subject

`sabotage` has to leave the module **parseable**. A syntax error would make every test file "notice"
for the wrong reason — the module would not import — and the check would report a clean bill of
health it had not earned. A test compiles a sabotaged module, executes it, and asserts each public
function raises.

It also has to leave dunders alone: `__getattr__` and friends are how a module loads, so breaking
them turns "the test noticed" into "the module would not import", a different and much weaker signal.

And the pairs themselves are checked — both files must exist, and the six modules written this
session must all be covered — because a vacuity list naming a deleted test file reports a pass for a
check it never ran, which would be this failure one level up again.

---

# Round forty-six — a repo-wide vacuity sweep, and five wrong answers before the right one

Round forty-five checked eleven test files for vacuity. This one extended it to the whole suite:
**512 test files auto-paired to the 63 source modules they most import**, each module sabotaged in turn.

The result is worth stating before the process: **zero confirmed vacuous test files.**

## ✗ The instrument was wrong five times, always in the same direction

MEASURED by sabotaging each module and running its paired test files, once per fix:

| run | "noticed" | what was wrong |
|---|---|---|
| 1st | 336/512 | no `--continue-on-collection-errors` — sabotaging a widely-imported module aborted the whole group before anything ran |
| 2nd | 399/512 | `-rf` reports failures only; **collection errors are excluded from that summary** |
| 3rd | 433/512 | `ERROR path - reason` — the ` - reason` suffix was never stripped, so those files matched nothing |
| 4th | 480/512 | *(parser correct)* |
| 5th | **489/512** | `sabotage` walked only `tree.body`, so classes were never touched |

**336 → 489 across the five runs in the table above, and not one correction moved the number down.** Every bug made real tests look
decorative. The first run's headline would have been "176 test files do not notice their module
breaking", wrong by at least 153.

The class bug was the largest. Most of this repository's detectors and rewriters *are* classes, so
for those modules the sweep changed nothing and then reported their tests as indifferent.
`test_binoculars_dead_latch.py` ranked **top** of the triage list as the most module-focused
survivor — and `BinocularsDetector` had never been altered. With class bodies included it fails
immediately.

**What caught every one was the same move**: take the least believable entry and check it by hand.
`test_quality.py` uses eleven of its module's names 87 times; a test that inspects a class for a
`_dead` attribute cannot be indifferent to that class being destroyed. The verdict had to be wrong,
not the test.

## The 23 survivors, classified by running each alone

| bucket | n | what it means |
|---|---|---|
| **skips** | 10 | optional dependency absent (`mcp`, torch). A skip exits 0 and is indistinguishable from silence. |
| **already failing** | 1 | cannot be evidence in either direction |
| **passes** | 12 | the only real candidates |

And **11 of those 12 import only module-level data** — MEASURED by parsing each test file's imports
against its module's AST — `_CATEGORIES`, `_SYN`, `_TRANSITIONS_RE`,
`_FRONTABLE_RE`, `MAX_INPUT_CHARS`, `_TRAIN_PROMPT`. `sabotage` replaces **function bodies**, so a
test asserting properties of a catalogue or a compiled regex is legitimately unaffected. The
twelfth imports two real functions and **skips five of its six tests** for want of a corpus.

`test_composite_selects_when_max_saturates.py` is the sharpest case: it imports `_selection_key`,
which is `_selection_key = selection_key` — **an alias to a function defined in another module**.
Sabotaging `composite.py` cannot touch it.

## ✅ What this actually establishes

**No test file in this repository passes while the module it tests is destroyed.** That is a real
result and it took five corrections to earn.

It also surfaced something about the suite that was not the question asked: **a large share of these
tests assert properties of data rather than behaviour** — that no catalogue branch is dead, that no
`_SYN` entry emits a conjunction opener, that a regex is linear on long inputs. Function-body
sabotage is blind to all of it, which is a limit of the technique rather than a gap in the tests.
Catching a bad catalogue entry is arguably worth more than catching a bad function, because the
catalogue is what the tells system actually is.

**The reusable warning is about the instrument, not the suite.** Five plausible, publishable,
wrong numbers came out of a 60-line harness before a right one did, and every one of them was
biased toward finding fault with someone else's work.

---

# Round forty-seven — mutating the data, and the vacuous universal it exposed

Round forty-six's incidental finding was that **eleven of the twelve test files it could not break
import only module-level data** — catalogues, compiled regexes, thresholds — and that function-body
sabotage is blind to all of it. That is the wrong thing to leave uncovered here: **the tells
catalogue is not a detail of the tells system, it is the tells system.**

Four data mutants, and two of them found a real hole.

## ✗ A universal over an empty collection

Emptying `_OPENERS` broke nothing. `test_no_conjunction_opener_is_emittable.py` asserts the category
is **closed** — that no opener the rewriter can emit is a bare conjunction — and that is **vacuously
true when there are no openers.** Emptying `_PARTICLES` survived for the same reason: the test asserts
substitutions keep their prepositions, and with no particles there is nothing to keep.

**The catalogues could have been deleted outright and the suite would have stayed green.** This is
the oldest vacuous-test bug there is, sitting in the assertions guarding this repository's most
consequential data, and no amount of function mutation could ever have surfaced it.

Nine tests now assert the collections are populated, so every "no member does X" elsewhere has
something to quantify over. The sizes are **floors, not exact counts** — an exact count fails on
every legitimate addition, and a check that fails on correct changes gets deleted. Plus a check that
every entry in `_AI_VOCAB` is matched by the regex built from it, which catches an emptied catalogue
and a regex that stopped being derived from one, and cannot drift the way a hard-coded example would.

## ⚠️ And three of my four mutants did not mutate

The first versions emptied the containers with `_AI_VOCAB = [] or [...]`. **`[] or [...]` evaluates to
the non-empty list.** Same for `() or (...)` and `frozenset() or frozenset(...)`. All three changed
the file and none changed the value, so the sweep reported three survivors that were really
no-ops — and the "survivors" pointed at tests that were, at that moment, entirely innocent.

The round-forty-two guard exists to catch exactly this and could not: it asserts
`source.replace(old, new) != source`, which is **true here.** The text changed. Textual difference is
a weaker property than semantic difference, and the gap between them is where a mutation can look
applied and do nothing.

Caught by the same move as every round since forty: the result was implausible. A test named
*no conjunction opener is emittable* cannot be indifferent to the opener catalogue vanishing — so
either the test was broken or the mutation was, and checking took one line in a REPL.

Once the mutants actually emptied the containers, two of the four were **real** — which is the part
worth keeping. The no-op versions were hiding a genuine defect behind a bug of mine.

---

# Round forty-eight — the same scan across the whole suite, and eight false alarms

Round forty-seven found two vacuous universals by hand-picking four collections. That is not a
method. A static scan of **every test file** for `for x in COLLECTION: assert ...` and
`assert all(... for x in COLLECTION)` — where `COLLECTION` is imported from `untell/` or `eval/` and
**nothing anywhere in the suite asserts its size** — proposed fifteen candidates, nine of them real
collections rather than scalars caught incidentally.

## ✅ Mutation disposed of eight

Emptying each and running its test file:

| collection | emptied → |
|---|---|
| `_ADVERB_SLOT_ONLY` | caught (4 failures) |
| `_ACADEMIC_HUMAN_TRANSITIONS` | caught |
| `_NEEDS_PRIOR_DISCOURSE` | caught (2) |
| `_MERGE_WEIGHTS` | caught (17) |
| `_TIER_RANK` | caught (2) |
| `_SCALE` | caught (15) |
| `HUMAN_AUTHORED` | caught (5) |
| `SELECTION_ON_BARE_MAX_ALLOWED` | caught by `untell-audit` |
| **`_BARE_ARTICLES`** | **survived — all 8 tests still pass** |

**Static analysis proposes; mutation disposes.** Eight of nine candidates were already guarded, just
not by an explicit size assertion — the behavioural tests around them fail on their own. Reporting
the scan's output as nine gaps would have been nine times the truth.

## ✗ The one that was real

`test_no_output_stacks_two_determiners` reads:

```python
for article in ("a", "an", "the"):
    for second in _BARE_ARTICLES:
        assert f" {article} {second} " not in out
```

The inner loop runs zero times when `_BARE_ARTICLES` is empty. **The rewriter would be free to emit
"the the" and the assertion written to prevent exactly that would not fire.** Now guarded, and the
guard is checked against the mutant.

## ⚠️ Two of my own measurements in this round were wrong

`SELECTION_ON_BARE_MAX_ALLOWED` first came back as a survivor, and `untell-audit` reported
**"5 sites, all accounted for"** with the allowlist supposedly emptied. Both were the same mistake:
the override was appended to the **end of the module**, after
`if __name__ == "__main__": raise SystemExit(main())`. `main()` had already run and exited; the
override never executed.

Re-run in-process, the audit catches it immediately — `ok = False`, naming every unlisted site. The
guard was working the whole time and my probe was measuring nothing, which is the same defect this
ledger has now recorded in four consecutive rounds, this time in a three-line shell command.

**Appending to a module is not a safe way to override a constant.** It is only safe for a module
with no entry point — which is why the `_BARE_ARTICLES` result stands: `untell/rewriter/structural.py`
contains no `__main__` guard, and that was verified before the finding was believed.

## The sweep now carries all three modes

Round forty-eight's scan was a one-off script. `--collections` makes it standing: twelve catalogues
that a test asserts a universal over, each emptied in turn. MEASURED by
`python scripts/mutation_sweep.py --collections`: **12 of 12 killed** once round forty-seven's and
forty-eight's guards were in place.

The helper that does the emptying inserts its override **immediately after the assignment**, never
at the end of the file, and a test proves it lands before `untell/scripts/audit.py`'s `__main__`
guard. That is the round-forty-eight mistake made structurally impossible rather than merely
documented — and `type(X)()` cannot silently evaluate to the original the way `[] or [...]` did in
round forty-seven.

Five more tests guard the mode itself: every named collection must still exist at module level (a
rename turns its case into a no-op), the override must actually empty the container, and a missing
name must be reported rather than skipped. `mutation_sweep.py` now has three modes — one broken line,
one broken module, one emptied catalogue — and each has been wrong at least once, so each is tested.

---

# Round forty-nine — back to the corpus, and a result the arms cannot represent

Rounds forty to forty-eight were all testing infrastructure. The largest topic in the survey —
**robustness/paraphrase, 153 papers** — had 128 uncited, and reading the 44 in main-conference venues
produced three findings, one of which is a problem for the strategy rather than a number for it.

## ✅ The robustness figure, systematically measured

*Stumbling Blocks* ([2024.acl-long.160](https://aclanthology.org/2024.acl-long.160/)) stress-tests
popular detectors across **editing, paraphrasing, co-generating and prompting**, under limited access
to the generator, at several budget levels. **Performance drops 35% averaged over all detectors and
attacks.**

The shape matters more than the number: *"almost none of the existing detectors remain robust under
all the attacks, and all detectors exhibit **different loopholes**."* Different, not shared. **Which
detector an institution licensed determines which attack works against it** — the union/consensus
argument one level down, and a second reason a published robustness figure cannot be inherited any
more than a false-positive rate can.

## ⚠️ Frankentext: the categories stop being well-posed

*Frankentext* ([2026.acl-long.1457](https://aclanthology.org/2026.acl-long.1457/)) has an LLM
assemble a long narrative from thousands of randomly sampled human snippets, **about 90% of tokens
copied verbatim**. It is coherent; human annotators praise the premises and the humour. **72% are
misclassified as human-written by Pangram.**

No threshold fixes this, and it is not evasion in the sense the rest of that literature means.
**A Frankentext is mostly human tokens arranged by a machine.** Every arm this repository audits —
human, AI-assisted, machine-humanized, fully generated — assumes authorship of the *words*. Here the
words are human and the *composition* is not.

**This is the first result in the ledger that our own taxonomy cannot represent**, and the honest
consequence is not a new arm but a limit: a detector answering *"is this human writing?"* is
answering a question that stops being well-posed at the edges, and an audit built on that question
inherits the same problem. Worth stating in the strategy rather than quietly adding a fifth column.

## Also read, not acted on

*Counter Turing Test* ([2023.emnlp-main.136](https://aclanthology.org/2023.emnlp-main.136/))
introduces an AI Detectability Index and situates detection against the 2023 regulatory moment — the
open letter, the US Copyright Office statement on machine authorship, the first EU proposals. It is
the earliest paper in this corpus to treat detectability as a **property to be indexed per model**
rather than a binary, which is the same instinct as this repo's per-deployment framing, two years
earlier and aimed at generators instead of populations.

---

# Round fifty — turning the Frankentext finding into a measurement, and nearly publishing an artefact

Round forty-nine recorded *Frankentext* ([2026.acl-long.1457](https://aclanthology.org/2026.acl-long.1457/))
as the first result this repository's arms cannot represent: human words, machine arrangement, **72%
misclassified as human by Pangram**. A finding recorded is not a finding tested, and the 6,811
pre-LLM abstracts restored in round thirty-one are enough to ask what our own stack does with that
input property.

`eval/frankentext.py` stitches each text from sentences drawn from **different** human documents.
Every token is from a pre-2022 publication, so **every flag is a false positive in the strictest
sense available here.**

⚠️ **It is not a replication and the report says so.** Frankentexts are assembled *by an LLM* for
coherence; these are assembled by `random.sample` for none at all. Removing the coherence is what
isolates arrangement — and it also removes the hard part of that paper.

## ✗ The first run said stitched text evades detection tenfold

MEASURED by `python -m eval.frankentext --n 60` before the arms were matched:

| arm | n | flagged | 95% CI |
|---|---|---|---|
| stitched | 60 | 1.7% | [0.3%, 8.9%] |
| whole | **17** | 17.6% | [6.2%, 41.0%] |

A **−16.0 point gap**. It is the length confound of rounds thirty-six and thirty-seven, a third time.
The stitched texts averaged **263 words**, few abstracts are that long, so the comparison arm was
whatever seventeen documents happened to qualify — and short text is flagged far more often.

## ✅ Matched at 130 words with 150 per arm

MEASURED by `python -m eval.frankentext --n 150 --sentences 6`:

| arm | n | flagged | 95% CI |
|---|---|---|---|
| stitched | 150 | **10.7%** | [6.7%, 16.6%] |
| whole | 150 | **11.3%** | [7.2%, 17.4%] |

**Gap −0.7%, intervals overlapping almost entirely. No effect.** Arrangement is invisible to this
detector, which on reflection is what a perplexity-and-burstiness measure should do: human sentences
have human perplexity whatever order they arrive in.

That is a **negative result about our stack, not a refutation of the paper.** Pangram is a trained
classifier and Frankentexts are coherent compositions; neither condition holds here. What it does
establish is that the Frankentext threat model is invisible to the detector this environment can run,
so nothing in our measurements would show it.

## The probe now refuses a one-armed comparison

The `whole` arm can come back **empty** when the stitched texts are longer than any single document,
and the first version returned the stitched rate with `whole` at n = 0 — which reads as a comparison
and is not one. It now errors with the count and the fix. **Found by a test asserting both arms are
populated, written after the first run had already been misread once.**

---

# Round fifty-one — the same confound three times, so it becomes a function

Three rounds, three wrong headlines, one cause:

| round | claim | after matching |
|---|---|---|
| 36 | outlier gap separates at 5 of 7 cut-offs on 6,810 documents | gap changes sign between length bands; none separates |
| 37 | *(the author-status arm)* | **passed** at a worst median gap of 7.8% — but only because somebody checked |
| 50 | stitched text flagged at 1.7% against 17.6%, a −16 point gap | −0.7% at matched length, intervals overlapping |

The mechanism is measured here: **30.0% flagged at ≤50 words against 13.3% at 200+.** Any comparison
of flag rates between two groups inherits that unless the groups are length-matched.

**Remembering to check has failed three times out of three.** So `eval/arms.py` is the check as a
function, and the comparisons call it.

## What it refuses, and why the second condition matters

`length_match` takes the arms as `{name: texts}` — so a caller cannot check one and report the other
— and refuses on either of two grounds:

- **Median word counts differing by more than 15%.** Far below the range over which the flag rate has
  been measured to move, and stated as the judgement call it is.
- **An arm below 30 documents.** Round fifty's defect was *not* a length imbalance: both arms were the
  same length and one had **seventeen** documents, whose interval ran from 6.2% to 41.0%. A size
  check would have caught it where a length check alone would not.

It returns a verdict rather than raising. A comparison that declines to run is more useful inside
somebody's audit than an exception, and the failure line starts with **WARNING** where the success
line starts with **Length check** — different first words on purpose, so a skimmed report cannot be
misread.

## Wired in, not merely available

`eval/frankentext.py` now calls it instead of the bespoke size check written for it in round fifty,
and prints the verdict in its report header even when the comparison passes — **a passing check
should still show what it checked**. A test asserts the probe uses the shared function rather than a
private copy, because two comparisons with their own ideas of "comparable" is how they come to
disagree.

`eval/assisted_fairness.py` keeps its own `length_balance`, which does something this cannot: it
reports medians **per arm per author status** across five arms. The shared function is for the
two-arm case; the specialised one is not a duplicate of it.

---

# Round fifty-two — two papers say the category is the problem, not the accuracy

Round forty-nine recorded *Frankentext* as **the first result this repository's arms cannot
represent**: human words, machine arrangement, 72% misclassified as human by Pangram. Reading further
into the robustness topic shows it is not the first and not alone.

## ✅ The Ship of Theseus problem, stated as authorship rather than accuracy

*A Ship of Theseus* ([2024.acl-long.357](https://aclanthology.org/2024.acl-long.357/)) asks whether a
text retains its authorship after repeated paraphrasing — "whether authorship should be attributed to
the original human" once an LLM has rewritten it enough times. That is the **same question as
Frankentext from the opposite direction**: Frankentext keeps human words and machine-arranges them;
iterated paraphrase keeps human structure and machine-replaces the words.

**Both attack the category rather than the classifier.** Every arm this repository audits — human,
AI-assisted, machine-humanized, fully generated — presumes a fact of the matter about who authored
the words. These two say that fact dissolves under ordinary operations, and no threshold, ensemble or
calibration addresses it.

This upgrades round forty-nine from *one awkward result* to **a converging line of work**, and it
changes what the honest limitation section of this strategy has to say: not "our taxonomy has a gap"
but "the taxonomy is a simplification that two refereed results show breaking down at the edges."

## The evasion numbers, for the record

- ✗ **Detectors reverse on minor perturbations.** *Are AI-Generated Text Detectors Robust to
  Adversarial Perturbations?* ([2024.acl-long.327](https://aclanthology.org/2024.acl-long.327/)):
  "even minor changes in characters or words caus[e] a **reversal** in distinguishing between
  human-created and AI-generated text." Independent corroboration of SilverSpeak's homoglyph result
  by a different attack family.
- ✗ **Evasion no longer needs a trained paraphraser.** CoPA
  ([2025.emnlp-main.433](https://aclanthology.org/2025.emnlp-main.433/)) is **training-free**, using
  off-the-shelf LLMs and crafted instructions. Previous attacks "require substantial data and
  computational budgets"; this removes the barrier.
- ✗ **And the largest single figure in this ledger.** TempParaphraser
  ([2025.emnlp-main.1607](https://aclanthology.org/2025.emnlp-main.1607/)) simulates high-temperature
  sampling through multiple normal-temperature generations and **reduces detector accuracy by an
  average of 82.5%** while preserving text quality. Against *Stumbling Blocks*' 35% average drop
  across four attack families, this is one attack, more than twice as effective.

⚠️ **Both papers also report the defence**, and reporting only the attack would be selective. CoPA's
authors and TempParaphraser's both note that training on augmented data improves robustness, and
`2024.acl-long.327` proposes SCRN, a detector built to be robust to exactly these perturbations. The
picture is an arms race with movement on both sides, not a rout — which is the same correction this
ledger made in round twenty-one about watermark fragility.

## The full-suite check, and a failure that was my own prose

MEASURED after round fifty-one: **9,803 passed, 75 failed** across 40 files, against 40 failing files
on `main`. **One file failed on the branch and not on base** — `test_every_audit_check_can_fail.py` —
and it was not a code regression.

`check_test_count_claims` reported `claims 958 tests`. That is the **round-forty-four comma bug**,
whose fix is still in place and working. What it had found was the ledger entry **describing** that
bug, which contained the literal string it warns about. The check was right; the prose was the claim.

**Third time in this ledger** — and then a fourth, immediately, in the paragraph reporting the third.
Round twenty-nine's sentence about commercial LLMs did it, round forty-four's about the comma did it,
and round forty-six's `the 63 modules they most import` read as a test-module count.
Writing this section reproduced two of those literals while explaining them, and the checks fired
again.

Every one is phrased around the trigger now, and none of the checks was loosened. **That is the
decision worth recording**: the obvious fix each time is to relax the pattern, and each time the
pattern was right — it is a document stating a count next to a noun it tracks, which is exactly what
it exists to catch. A checker that exempted prose *about* counts would exempt the next real drift
written in the same shape.

The remaining drift was real: six test files added this round took the module count from 614 to 620,
repaired with `--fix-counts`.

---

# Round fifty-three — why four self-inflicted failures reached the remote

Four times a ledger entry **describing** a count-drift defect reproduced the literal string it warned
about and re-triggered the check. Round fifty-two documented that. What it did not explain is the
part that actually matters: **all four reached the remote before anyone noticed.**

The pre-commit hook built in round forty exists to refuse a commit CI would reject. On a Markdown
change it runs `test_docs_claims`, `test_roadmap_status` and
`test_retracted_claims_do_not_survive_elsewhere`. It did **not** run
`test_every_audit_check_can_fail` — which is the guard that notices a document stating a count next
to a noun the audit tracks.

So the gate was working exactly as configured, and its configuration had a hole shaped precisely like
the failure that kept recurring. Every one of the four was caught eventually — by a full-suite run,
long after the push.

It is in the hook now, verified by staging a doc edit that states a drifting count and watching the
commit be refused. It costs about twenty-five seconds and only on a Markdown change.

**The rewritten lesson.** Round fifty-two's conclusion — that the checks were right every time and
none should be loosened — was correct and incomplete. A check that is right and runs too late is a
check that documents failures rather than preventing them. The four instances were not a prose
problem; they were a **scheduling** problem, and the prose was where it happened to show.

---

# Round fifty-four — auditing the gate against the thing it is supposed to mirror

Round fifty-three closed one hole in the pre-commit hook. That prompts the obvious question nobody
had asked: **the hook exists to refuse what CI would reject, so what else does CI run that it does
not?**

Comparing the two directly found `mkdocs build --strict` — the **link checker**, whose first run in
CI found 47 broken cross-references. It was absent from the hook, and **this ledger's author had been
running it by hand at the end of every round for fifty-three rounds.** A step performed manually
every single time is the clearest possible sign it belongs in the gate.

A dead link is invisible to every other guard here: `untell-audit` reads claims, the doc tests read
counts, and neither follows a href. It is now in the hook, gated on a Markdown change, verified by
staging a link to a file that does not exist and watching the commit be refused.

## Two properties the tests now hold

**Graceful degradation.** `ruff` and `mkdocs` are dev dependencies, not guarantees. A hook that fails
hard when one is absent gets uninstalled by the first contributor who has not run
`pip install -e .[dev]`, and then guards nothing at all. Both are behind `command -v`, and a test
counts the probes.

**Scoping.** The link check runs only when Markdown changed. A gate that adds seconds to every Python
commit is a gate that gets bypassed, and the mkdocs step cannot find anything on a change that
touches no documents.

## ⚠️ And the test for the scoping matched the wrong line

The first version located the mkdocs invocation with `if "mkdocs build" in line` — and found **the
comment above it**, which mentions `mkdocs build --strict` while explaining what it is for. It then
checked the three lines before the comment, found no gating condition, and failed.

**Prose matched instead of the thing, in a test written for a hook added because prose kept matching
instead of the thing.** It now anchors on lines whose *stripped* form starts with the command, and
checks every such line rather than the first.

That is the fifth instance of this shape in three rounds, and the first where it appeared in a test
rather than in a document. The failure mode is not about counts or about Markdown: it is that **a
description of a thing looks exactly like the thing to anything matching on text.**

---

# Round fifty-five — giving the audit the use/mention distinction

Five times in three rounds, a ledger entry **describing** a count-drift defect reproduced the literal
it warned about and re-triggered the check. Rounds fifty-two to fifty-four handled each one by
contorting the prose — spelling a number out in words, renaming a noun, quoting a phrase indirectly —
and by concluding, correctly, that none of the checks should be loosened.

That conclusion was right and it left the actual problem untouched. **There was no way to write about
a count at all.** Every workaround produced a worse document and bought no safety, and the sixth
instance was only ever a matter of time.

Markdown already encodes the distinction that was missing. `the suite is 9,958 tests` is a claim
about this repository; the same text inside backticks is a **quotation of a string** — a sentence
about a claim rather than a claim. `without_code_spans` blanks inline code before either count check
reads a document, and the contorted sentences in rounds fifty-two and fifty-four are now written
plainly.

## Deliberately narrow, and measured before shipping

**Only inline code spans.** Not bold, not italics, not block quotes. Every real count in these
documents is written as prose or bold — nobody states a test count inside backticks — and tests pin
all three of those as still-claims.

MEASURED across `research-verification.md`, `why-best-open-repo.md`, `ROADMAP.md`, `index.md` and
`ai-writing-research.md` before the change shipped: blanking code spans loses **no** match either
check currently makes. It exempted nothing that was being caught.

⚠️ **The test written to pin that was wrong by the end of the same round.** It asserted that blanking
loses no match in any audited document — true when written, and false as soon as this entry started
quoting counts, which is the entire point of the change. **A guard that fails on every correct use of
the feature it guards is not a guard.** Replaced with the narrower thing that actually matters: the
repository's own live figures, in `why-best-open-repo.md`, must be stated **outside** backticks,
because those are the one claim the drift check exists to watch. The ledger may quote history freely;
the headline figure may not hide.

Two details that matter more than they look. Spans are replaced with **spaces rather than removed**,
so any line or column a check reports still points at the right place in the original file. And an
**unclosed** backtick must not blank the rest of the document — that would exempt every claim after a
stray character — so the pattern refuses to span newlines, with a test for it.

## ⚠️ The cost, stated plainly

**A genuinely stale count written inside backticks is now invisible to the audit.** That is the price
of being able to quote one. It is worth paying because the alternative was demonstrated five times: a
check the author routes around in prose is a check that shapes the writing without protecting the
document, and the contortions were themselves accumulating as a kind of debt in the ledger's own
sentences.

---

# Round fifty-six — a category the taxonomy never had, six times the size of the one it argues from

Rounds forty to fifty-five were almost entirely testing infrastructure. Returning to the corpus with a
broader sweep — **every uncited main-conference detection paper across all topics, 155 of them** —
found that **92 fell under no topic at all.**

Some of that is the detection filter still over-capturing: hallucination detection, factual
inconsistency, abuse detection, NLG evaluation. But a real category was hiding in the remainder.

## ✅ Multilingual detection: 13.3% of the corpus, and unmeasured

Adding `multilingual/cross-lingual` finds **77 of 578 detection papers**, against **12** on fairness
and **11** on false positives. MULTITuDE, M4GT-Bench, MultiSocial, detection in Urdu, Korean, Bangla.

**The strategy's ratio table had been quoting a taxonomy with a 13% hole in it.**

## The distinction is worth more than the count

Multilingual detection and detector fairness are **about the same population and ask opposite
questions.** One asks whether a detector *can* read a language; the other asks whether reading it
*harms* the person who wrote it. **The field studies the capability roughly six times more than the
cost.**

That is the same asymmetry as robustness against false positives — 153 to 11 — appearing in a second
place, and it strengthens this repository's central argument rather than complicating it. The
non-native writer is not a neglected subject in this literature. **They are a well-studied subject,
studied as a technical difficulty rather than as someone who can be wrongly accused.**

## What it says about the earlier counts

Every ratio this ledger has published survives: robustness is still an order of magnitude above
false positives and fairness. What changes is the claim that the taxonomy was complete. It was not,
and the missing row was the one closest to the strategy's own thesis — which is the most likely place
for a blind spot and the last place it was looked for.

The reachability guard caught the omission that followed: a new topic registered without a probe
would report an honest-looking zero forever, and the test that requires every topic to demonstrate it
can fire failed immediately.

---

# Round fifty-seven — measuring the noise floor instead of filtering it away

Round fifty-six found one missing topic by noticing it. Doing the same thing systematically —
clustering the **271 detection papers that fall under no topic** by vocabulary over-represented among
them — produced no second missing category. The strongest signal was **hallucination** (32 papers),
which is not a topic this survey lacks. It is a paper about a different problem.

## ✅ 13.8% of the corpus is some other detection task

MEASURED: **80 of 578** papers have a title naming another detection problem — fake news,
hallucination, factual inconsistency, toxicity, abuse, spam, bot or stance detection,
out-of-distribution — and not machine-generated text.

## ✅ And the shares barely move

MEASURED by re-running every topic count over the corpus with those 80 papers removed:

| topic | with them | without them |
|---|---|---|
| robustness/paraphrase | 26.5% | **27.5%** |
| multilingual/cross-lingual | 13.3% | **13.1%** |
| human-AI mixed/edited | 11.2% | **12.9%** |
| watermark | 7.6% | **8.8%** |
| education/integrity | 7.6% | **8.6%** |
| calibration/thresholds | 3.8% | **3.4%** |
| false positives/accusation | 1.9% | **2.0%** |
| fairness/non-native bias | 2.1% | **1.8%** |

**Fifth time the ratio has survived a change to the corpus beneath it**, and the first time the noise
has been *quantified* rather than argued about. Round thirty predicted this shape — noise roughly flat
across topics, recall loss uneven — and it holds: removing an eighth of the corpus moves no share by
more than 1.7 points.

## ✗ The filter is deliberately not being changed again

The obvious move is to exclude those 80. **It is the wrong one**, for the reason round thirty
established and then demonstrated: a phrase-only filter scored better on precision and dropped
`2026.eacl-srw.20`, the Czech result that **disconfirms part of this repository's own thesis**. For a
ratio, losing on-topic papers biases the topics unevenly while noise does not, and a title-based
exclusion would drop any genuine machine-generated-text paper that frames itself around
misinformation.

**Measuring the noise floor is more useful than removing it**, and it is honest in a way a second
filter revision would not be: the number now has a stated error term rather than an implied precision
it does not have.

## One claim gets sharper

`disability/neurodivergence` goes from one match to none on the filtered corpus — MEASURED by
re-running the topic counts with the off-topic papers removed. The single match was
*Centering the Margins*, a **toxicity**-detection paper — recorded in round thirty as not a
counterexample, and now shown to be the only thing standing between that row and zero. The claim that
**no study examines whether AI-text detectors flag neurodivergent or disabled writers** is exactly
true, in both corpora, with nothing to qualify.

## Shipped, so the error term travels with the count

Round fifty-seven's measurement was a one-off script. `python -m eval.litreview --noise-floor` now
reports it: how many detection papers name a different problem, and every topic's share with and
without them.

The point is not the convenience. **A count with no error term invites being read as exact**, and
this project spends most of its pages arguing that other people's numbers carry unstated conditions.
The survey's own figures had exactly that shape — 153 robustness papers against 11 on false
positives, with no statement of how much of the denominator was hallucination detection.

Five tests hold it, including one that pins the published figures — 80 of 578, no share moving more
than 1.7 points — so a change to the corpus or the patterns fails and names the drift instead of
letting a stale number stand.

> ✅ **It did exactly that in round sixty-eight**, when seven 2022 volumes were added. MEASURED on
> the widened corpus, `80 of 578` became **81 of 588** and the largest share move **1.5 points**.
> The pair above is the round fifty-seven measurement and is left as written.

⚠️ **And the first fixture tested nothing.** The synthetic hallucination paper written to prove the
noise check fires did not pass `DETECTION` at all, so it never reached the check. Real hallucination
papers in the corpus do pass it, because they name LLMs; the fixture did not. **The test asserted a
count of one and got zero for a reason unrelated to what it was testing** — the same shape as rounds
forty to forty-two, in a fixture this time.

---

# Round fifty-nine — the most-read document was outside the guard

Twenty-seven rounds after round thirty-one re-measured the pre-LLM false-positive rate, **the README
still said 15.8%.** It also said 26.7% where the measurement is 30.0%, and quoted an n of 120 where
the corpus now supports 599.

`untell-audit` reads the README — it is in `LIVE_DOCS`, and every one of those figures carried a
stated source. **The attribution check asks whether a number names a source, never whether it is
still true.** The check that asks that is the retraction guard, and its document list was
`ROADMAP.md`, the two research documents, the strategy options and the ledger. **Not the README.**

So the repository's most-read page carried its headline measurement, superseded, sourced, and wrong,
through twenty-seven rounds of a project whose entire subject is numbers that go stale.

This is the round-thirty-nine defect one document over. That round found `untell/calibrate.py`
justifying a shipped default with figures round thirty-one had replaced, because the guard scanned
documents and not source. The fix then was to add source. **The fix now is to add the documents the
guard's own list had omitted** — `README.md`, `docs/index.md`, `docs/why-best-open-repo.md` — which
raises the obvious question of what else is outside it, and the answer is that the list is now every
document `LIVE_DOCS` names.

## The README also gained a caveat it never had

The rate is quoted for documents of **60 words or more**, and round thirty-five established that the
floor is load-bearing: MEASURED by `python -m eval.pre_llm_fpr --n 300 --min-words 30` and the
same at a 150-word floor, the probe returns **22.0%** and **14.3%**. An 8.4-point swing from a
parameter nobody chose deliberately. That sentence was in the ledger and the roadmap and
not in the document most people read.

## Two ledger lines annotated rather than rewritten

Round twenty-seven's entry stated the old length figures as current. The ledger is an audit trail and
rewriting it would destroy the record, so both lines now carry a pointer to the round that superseded
them, and the quoted pair is written in backticks — a mention, under round fifty-five's rule, rather
than a claim.

---

# Round sixty — the threshold this roadmap recommended no longer holds its own bound

Round fifty-nine put `README.md` inside the retraction guard and corrected three stale figures on it.
The fourth figure on that page was the calibration result, and it turned out to be stale in a way the
other three were not.

The published claim was that the shipped 0.45 flags **17.3%** of pre-LLM human text and that
**0.5215** — derived by conformal calibration at α = 0.05 — bounds it at **4.7%**, both on a
150-document sample. Re-derived on the 599-document sample every other figure in this repository now
uses, with `>=` as the flagging comparison the probe itself uses:

| threshold | flagged, n = 599 |
|---|---|
| 0.30 | 374 — 62.4% |
| **0.45 — shipped** | 123 — **20.5%** |
| 0.504 — α = 0.10 here | 60 — 10.0% |
| **`0.5215` — α = 0.05 on the old sample** | 45 — **7.5%** |
| **0.5461 — α = 0.05 here** | 30 — **5.0%** |

✗ **`0.5215` does not meet the bound it was derived for.** It was published as holding false
positives under 5% and it flags 7.5%. The α = 0.05 threshold on this sample is **0.5461** — seven
thousandths higher, and the difference between a bound that holds and one that does not.

> ⚠️ **Superseded by round sixty-one, which was written the same day.** This paragraph is wrong about
> *why*. The conformal bound is marginal, not conditional: a threshold calibrated on 150 documents
> lands above α roughly 37% of the time by design, and `0.5215`'s 6.93% on the full corpus is the
> 90th percentile of that distribution — an ordinary draw. What was genuinely wrong was publishing
> "4.7%" as *the* rate it delivers. The correction to the correction is round sixty-one.

**Nothing shipped depends on it.** `grep` across `untell/` and `eval/` finds `0.5215` in no source
file and no test; it existed only in `README.md` and `ROADMAP.md`. So this is a claims correction,
not a broken default — which is the only reason it is a round in a ledger rather than a bug.

## Why this is the most useful thing this project has measured about itself

Every earlier round of this kind found a number that had gone stale because the *corpus* changed —
120 documents became 599, a word floor moved, a volume list was wrong. This one is different. Both
samples are pre-2022 ACL Anthology abstracts of 60 or more words, drawn from the **same 6,811
documents** with the **same detector** and the **same seed**. The only difference between them is how
many were drawn.

**And the threshold still did not transfer.** A calibrated threshold is a property of the sample it
was calibrated on, and this repository has now demonstrated that on the friendliest possible case —
same venue, same years, same register, same detector, same code — where it still failed. Every
argument this project makes about vendors publishing thresholds without their conditions applies to
its own published threshold, and now says so on the page.

> ⚠️ **"Failed" is the wrong word, per round sixty-one.** The threshold moved because thresholds
> calibrated on finite samples are random variables, which is what conformal prediction says they
> are. The paragraph's conclusion survives — a published threshold is a draw, not a constant — but
> `it still failed` is a mention of the claim, not a claim, from here on.

## What was corrected

`README.md` gained the n = 599 figures and a paragraph stating the failure. `ROADMAP.md`'s
calibration table was rewritten with all five rows above and the same paragraph, its status row 27
now reads "0.45 flags 20.5%; 0.5461 bounds it at 5%", and three other lines that quoted `0.5215` or
17.3% as current were updated. The stale header "Calibrated on 150 pre-LLM ACL abstracts" was
corrected to 599 — it had survived the table being rewritten beneath it, which is round
fifty-nine's defect in miniature, one line above the thing that replaced it.

⚠️ **`0.5215` is now written in backticks throughout.** Under round fifty-five's rule it is a
mention — the name of a superseded threshold — not a claim that anything holds at it.

## The finding that opened the next round

`pre_llm_abstracts` returns **6,811** documents. Every calibration figure above, and every
false-positive headline in this repository, is measured on **599 of them — 8.8%** — because
`eval/pre_llm_fpr.py` caps the sample at `--n`, whose default is 100 and which nobody revisited after
the corpus was restored. The roadmap even says "the corpus added in round thirty-one is 6,811
abstracts, so there was no reason to keep publishing the small sample", immediately above a number
computed on a small sample.

There is no reason not to score all of them. That is round sixty-one.

---

# Round sixty-one — the correction to round sixty, and the number the bound never promised

Round sixty found that `0.5215`, calibrated at α = 0.05 on 150 pre-LLM abstracts, flags 7.5% of a
599-document sample and called that a threshold failing its bound. Round sixty-one scored the whole
corpus and then asked whether "failing" was the right word. **It was not**, and finding out required
answering a question this repository had never asked about its own method.

## First, the corpus was never a sample of anything

`pre_llm_abstracts` returns **6,811** documents. Every false-positive figure this project has
published — 19.2% at n = 120, 20.5% at n = 599 — came from `eval/pre_llm_fpr.py`'s `--n`, whose
default is 100 and which nobody revisited after round thirty-one restored the corpus. Twenty-five
minutes of CPU scores all of them.

| threshold | flagged, n = 6,810 | 95% CI |
|---|---|---|
| 0.30 | 4,289 — 62.98% | [61.83%, 64.12%] |
| **0.45 — shipped** | **1,326 — 19.47%** | [18.55%, 20.43%] |
| 0.4975 — α = 0.10 | 683 — 10.03% | [9.34%, 10.77%] |
| `0.5215` — α = 0.05 on 150 documents | 472 — 6.93% | [6.35%, 7.56%] |
| **0.5401 — α = 0.05 here** | **341 — 5.01%** | [4.51%, 5.55%] |
| 0.5461 — α = 0.05 on 599 documents | 310 — 4.55% | [4.08%, 5.07%] |
| 0.6163 — α = 0.01 | 68 — 1.00% | [0.79%, 1.26%] |

✅ **The sampling ladder is a reassuring result, which is rare here.** 19.2% [13.1%, 27.1%] at n = 120,
20.5% [17.5%, 24.0%] at n = 599, **19.47% [18.55%, 20.43%]** over the census. The census lands inside
both samples' intervals: neither was biased, both were imprecise — 14.0 points wide, then 6.5, now
1.9. Nine rounds of this ledger have found a headline that moved when its corpus grew. This one did
not move; it sharpened.

## Then the question round sixty should have asked

If `0.5215` was derived correctly at α = 0.05, **how often is a correctly-derived threshold supposed
to exceed α?** Round sixty assumed the answer was "never" and read 7.5% as a defect.

The answer is **about half the time.** The split-conformal guarantee is *marginal*: it bounds the
false-positive rate averaged over calibration sets. Conditional on the single calibration set anyone
actually has, the realised rate on new documents is `Beta(n + 1 − rank, rank)` distributed, with mean
exactly α. A distribution with mean α sits above α roughly half the time.

MEASURED two ways that agree — 400 random calibration/test splits of the 6,810 real scores, against
the closed form, medians within **0.1 points** and exceedance probabilities within **1.8**:

| calibration set | median realised FPR | p5–p95 | P(exceeds α = 5%) |
|---|---|---|---|
| n = 50 | 3.33% | 0.72% – 9.14% | 27.9% |
| n = 150 | 4.44% | 2.21% – 7.74% | 37.3% |
| n = 599 | 4.95% | 3.63% – 6.54% | 47.8% |
| n = 2,000 | 4.98% | 4.22% – 5.82% | 48.6% |
| **n = 6,810** | **4.99%** | **4.57% – 5.43%** | **48.1%** |

⚠️ **The agreement checks the arithmetic, not the corpus.** The simulation shuffles before splitting,
so it *imposes* the exchangeability the Beta result assumes. It proves the closed form is right; it
proves nothing about whether ACL abstracts are exchangeable.

## The correction

✗ **`0.5215` did not fail.** Its 6.93% on the full corpus is the **90th percentile** of the band a
150-document calibration draws from. That is an ordinary draw, and round sixty's "it does not meet
the bound it was derived for" is now annotated in place as superseded rather than rewritten.

**What was actually wrong is narrower and worse.** Publishing "**0.5215** bounds it at **4.7%**"
stated one draw from a band running 2.2% to 7.7% as though it were the rate that threshold delivers.
The retraction stands; the diagnosis was wrong. Correcting a correction one round later is the
uncomfortable part, and leaving it uncorrected because it is embarrassing is the alternative.

## The finding worth taking away

**More calibration data does not make you less likely to exceed α.** That probability converges to
~50%; 6,810 documents are no safer than 150. Forty-five times the data narrows the p5–p95 band from
5.5 points to 0.9 and nothing else. **Buy data for precision, not for safety** — and read any single
published calibration, this repository's included, as a draw rather than a promise.

`untell.calibrate.coverage_spread(n, alpha)` computes the band, and `calibrate()` returns it as
`expected_fpr`, so the honest number cannot be separated from the threshold it qualifies. It is
cached on `(n, alpha)` because the closed form costs 0.34s at corpus size, enough to dominate a loop
over calibration sets — which is exactly the loop this round ran.

## ✅ The tie caveat, warned about since it shipped and never measured

`untell/calibrate.py` has always said ties break the bound, because `>=` catches a whole tie. On this
corpus **73.0% of documents share a score with another** — the detector rounds to four places — so
the warning is real. But the tie at the α = 0.05 threshold has multiplicity 2 and the realised rate
is **5.007%**. Pervasive ties, seven thousandths of a point. A caveat you can only retire by looking.

## ⚠️ The repository's only worked example did not run

`untell/calibrate.py` opened with a doctest showing `calibrate()` turning five scores into a
threshold of 0.3. It cannot: twenty documents is the floor for any α, the call returns `None`, and
the example raised `TypeError` on the subscript.

**It had never raised it anywhere.** There is no doctest configuration in `pyproject.toml`, no pytest
ini, nothing in CI — so across `untell/` and `eval/` the sole doctest in the repository had never been
executed, in the module whose subject is not trusting a number you have not run. Worse, it documented
the opposite of the module's design: a reader checking what a small sample returns was told it
returns a threshold, when refusing small samples is the entire point.

`tests/test_every_worked_example_in_the_source_actually_runs.py` now runs every module's doctests —
80 cases — and asserts that at least five runnable examples exist, so deleting the broken example
rather than fixing it would fail too. Verified to fire: a deliberately false example in
`untell/text_split.py` fails the sweep and the module was restored clean.

---

# Round sixty-two — the repair the audit recommends corrupted the document it was run on

Round sixty-one added two test files, which pushed the suite past a documented count, which made
`untell-audit` print what it has printed many times:

> DRIFT every 'N tests' claim is close to what pytest collects (`docs/humanizer-census.md`: claims
> 9202 tests, pytest collects 10278 — run `untell-audit --fix-counts` to repair)

Running the recommended repair **corrupted the verification ledger and did not fix
`humanizer-census.md`.** Measured, per file — what the checks match against what the fixer rewrote:

| document | module claims the checks see | module claims the fixer rewrote | test claims seen | rewritten |
|---|---|---|---|---|
| `research-verification.md` | `620` | `620`, **`63`** | `9,958` ×2 | **none** |
| `humanizer-census.md` | — | — | `9202` | **none** |

**Of the three claims the checks were reporting, the fixer repaired zero. Of the one thing it did
rewrite, one was not a claim at all.**

## Three defects, one cause

The check and the repair had **two different definitions of "a count claim"**, and the gap ran in
both directions at once.

✗ **The fixer did not know about code spans.** Round fifty-five taught the *checks* the use/mention
distinction — `without_code_spans()`, because five times in three rounds a document describing a
count-drift defect reproduced the literal it warned about and re-triggered the check. The fixer was
never taught the same rule, so it matched raw text. It rewrote

> round forty-six's `the 63 modules they most import` read as a test-module count.

into `the 624 modules they most import` — turning a sentence *about* a past false positive into a
false statement, inside the paragraph explaining why that class of false positive happens.

✗ **The fixer's pattern was narrower than the checks'.** The checks match `\*{0,2}(\d[\d,]{2,6})...`;
the fixer required `\*\*(\d+)\*\*`. So it could not repair `9202 tests` (not bolded) or `9,958 tests`
(grouped) — which between them are every test-count claim the checks have ever reported.

✗ **The fixer rewrote the ledger.** Round fifty-nine established that a superseded entry here is
*annotated*, never rewritten, because this file is an audit trail. `--fix-counts` silently edited two
historical lines, one of them a record of what was true in an earlier round.

## The fix is structural, not three patches

`_MODULE_CLAIM` and `_TEST_CLAIM` are now defined once and used by both checks and the fixer, so the
two sides cannot drift apart again. `substitute_outside_code_spans()` is the write-side counterpart
of `without_code_spans()` — it matches against the blanked copy, which preserves offsets, and splices
replacements into the original at those positions, so **the repair can only touch what a check could
have seen.** Formatting survives: bold stays bold, `9,958` becomes `10,278` and not `10278`.

And `COUNTED_DOCS` excludes the ledger from counting and repair alike, while leaving it inside
`COMPARATIVE_DOCS` for every other check. Eight tests hold all of it, including the exact corrupted
sentence as a regression case.

## Why this one is worse than a stale number

Every count-drift round in this ledger has been a document falling behind the code. This is the
inverse: **the tool that exists to stop that introduced a defect of exactly the kind it detects**, in
the file that records the detection, and reported success while doing it — `counts set to 10278
tests, 624 modules` was printed for a run that repaired nothing and broke a sentence.

The generalisable form: **a checker and its auto-fixer are two implementations of one predicate, and
nothing here was testing that they agreed.** Every test aimed at the checker passed throughout. The
fixer had none of its own, because it was "just" the repair path.

## ⚠️ And the first fix recreated a defect this repository had already documented

`COUNTED_DOCS` was introduced as a constant derived from `COMPARATIVE_DOCS` at import time. **Three
existing tests monkeypatch `COMPARATIVE_DOCS`**, so under that design they would have patched a name
nothing read, and the checks would have scanned the real repository instead of their fixtures — the
exact vacuity `test_the_dead_function_check_is_fast_and_still_works.py` already carries a comment
about, in the file the change would have broken.

MEASURED rather than assumed. Freezing the list at import and re-running the three files gives **43
passed, 1 failed** — and the one failure is the *negative* case, `1,200 tests against 9,958 is real
drift`. Every positive case passed vacuously. That is the same signature the earlier round recorded:
"only the negative case noticed".

So it is a function, `counted_docs()`, evaluated per call. A derived constant is a footgun wherever
the name it derives from is something tests patch, and the cost of the function is one tuple
comprehension per check.

**Two rounds in a row have now found the same shape**: round sixty-one corrected round sixty, and
this section corrects the first draft of round sixty-two. The pattern is not carelessness so much as
the thing this ledger exists to make visible — **a fix is a change, and a change needs the same
scrutiny as the code it repairs.**

---

# Round sixty-three — the suite was not hanging, one test was taking thirty-nine minutes

Round sixty-two's verification run appeared to stall at 97%. It had not stalled. `py-spy` on the
stuck worker named the frame:

```
_claimed_spans (untell/scripts/tells.py)
score_tells (untell/scripts/tells.py)
test_all_newlines_score_tells (tests/test_scale_ceilings.py)
```

That test's entire docstring is **"100k bare newlines must not crash."** It does not crash. MEASURED,
`_claimed_spans` on runs of bare newlines:

| newlines | before | after |
|---|---|---|
| 1,000 | 0.245s | 0.0008s |
| 2,000 | 0.987s | — |
| 4,000 | 3.918s | 0.0033s |
| 8,000 | 15.579s | — |
| 16,000 | **60.509s** | **0.0130s** |
| 100,000 | ~39 minutes, extrapolated | **0.0821s** |

**Four times the time for twice the input, at every step.** Clean quadratic, so the 100,000-newline
test costs about thirty-nine minutes — and "does not crash" was the whole contract, so nothing said
so.

## The shape, and why five patterns had it

Every offender was `^` under `re.MULTILINE` followed by `\s*`:

    (?:^|(?<=[.!?]\s))\s*(Moreover|Furthermore|...)

Under `re.MULTILINE`, **every newline in a run is a line start.** At each one `\s*` greedily eats the
rest of the run, fails the literal, and backtracks over everything it ate. O(n) work at O(n)
positions. `formulaic_transition`, `steering_opener`, `sycophancy`, `rhetorical_opener` and
`markdown_artifact` all had it.

The fix is `[^\S\n]*` — horizontal whitespace, which cannot cross a newline, so an attempt starting
inside a run fails in O(1). It also matches intent: this is *leading indentation on a line*, never a
blank line between paragraphs, and `^` already matches at the later line start regardless.

⚠️ **`untell/scripts/score.py` caps REST input at 50,000 characters, and the cap did not bound the
cost.** DERIVED from the MEASURED 60.509s at 16,000 newlines and the quadratic scaling the table
above establishes: 60.509 × (50,000 / 16,000)² ≈ **591 seconds — about ten minutes of CPU for one
request.** Extrapolated rather than run, because running it would have cost ten minutes. A byte limit
is not a work limit when the work is quadratic in the bytes.

## Equivalence, checked rather than argued

1,210 texts — 1,200 real pre-LLM abstracts plus ten fixtures built to hit each pattern — through
`_claimed_spans` before and after. **1,144 spans: every one the same category, the same end offset,
and the same matched text apart from a dropped leading run of newlines.** Six texts differ at all,
all fixtures, all in exactly that way.

✅ **That difference is an improvement, not a tolerated regression.** `_claimed_spans` sorts
**longest span first** so the richer tell claims contested text. A leading newline run inflated a
span's length without adding any tell, so a pattern preceded by blank lines could out-rank a
genuinely longer construction. One fixture shows a span of `[0, 48]` for the eight-character tell
`Notably,`; it is now `[40, 48]`.

## The durable half: the seventh pattern, found by the check rather than by hand

Fixing six patterns is worth less than making the seventh impossible to add unnoticed. A sweep now
walks **every compiled pattern reachable from `untell/` and `eval/`** — 269 of them — and times each
on a run of newlines and a run of spaces, failing anything that grows more than 2.6× for 2× input.

It earned its place immediately. Hand-inspection had found six; the sweep found two more on its first
run — `untell._env._COMMENT` (`\s+#.*$`) and `untell.scripts.tells._DIFF_ANCHOR_RE` — both quadratic,
both under the threshold a human eye had used.

Four patterns needed the other fix, where a newline should not stop the match: a negative lookbehind
anchoring the run to its first character, `(?<!\s)\s+` instead of `\s+`. MEASURED at 16,000
characters, `_SPACE_BEFORE_PUNCT`, `_TRAILING_HORIZONTAL`, `_SENTENCE_END_AFTER` and
`_LIST_CONTINUES_RE` ran **1.12–1.23s** against **0.00033s**, with identical matches on 2,010 texts.

✗ **Possessive quantifiers are the obvious fix and they do not work.** `[ \t]++` removes backtracking
*within* the run, and the growth ratio stays 4.0 — the engine still restarts at every position and
rescans. MEASURED: 8× faster, still quadratic. Only anchoring the run's start changes the exponent.

⚠️ **And the sweep's first version was flaky, which would have made it worse than nothing.** It timed
each pattern once. Run alone it passed; run beside five other test files it failed on a linear
pattern, because a scheduler steal in the large sample and none in the small one is enough to clear a
2.6× ratio. This repository's own rule — *a check that fails on correct machines gets disabled, which
is worse than not having it* — is written in `check_test_count_claims` two files away.

Fixed by measuring the **minimum of three runs**. Timing noise is one-directional: contention adds
time and never removes it, so the minimum is the robust estimator and a single sample is not. Three
consecutive runs of the same six-file selection that produced the failure now pass.

✅ **Verified to still fire.** Reverting one of the five tell patterns to `\s*` fails the sweep, which
names it — and names it as `untell.rewriter.structural._TELLS_TRANSITION_OPENER_RE`, a re-export of
the same compiled object, confirming the fix reaches every module that shares it.

## What this says about the test that found it

`test_all_newlines_score_tells` was doing its job and could not say so. It asserted the weakest
property available — no exception — for an input chosen precisely because it is pathological, and
then took thirty-nine minutes to report success. **A scale test with no time bound tests the wrong
half of the scale.** MEASURED after the fix, `tests/test_scale_ceilings.py` runs its 28 cases in **12.0 seconds** total.

---

# Round sixty-four — 88% of a scoring request was the caveat, not the score

Round sixty-three fixed the quadratic regexes and made the whole suite completable: **6 minutes 33
seconds for 9,953 passing tests**, where before it never finished at all. With the pathological case
gone it became possible to ask a question the repository had never been able to answer: **what does a
`/score` request at its own 50,000-character cap actually cost, and where does the time go?**

PROFILED at the cap, `score_text` at `tier=lite`:

| input | total | spaCy NER | share |
|---|---|---|---|
| ordinary prose | 3.88s | 3.40s | **87.8%** |
| `"a,"` repeated | 13.71s | 12.59s | **91.8%** |
| bullet lines | 3.76s | 3.27s | **87.0%** |

**All of it is `_mostly_locked_warning`** — an advisory sentence saying the rewriter may not touch
most of the input. The scoring path locks for no other reason. Rewriting locks separately and none of
this touches it.

## The note almost never fires, and it costs the most when it does not

MEASURED on 400 real pre-LLM abstracts, the locked share runs **median 0.028, p90 0.085, max
0.190** — against a bar of **0.50**. On 40 long documents built by concatenating them it is
**0.021–0.059**. The expensive computation answers "no" every time, with an order of magnitude to
spare.

That is not an argument that the note is useless: it exists for input that genuinely is mostly
quotation, citation or table, which academic abstracts are not. It is an argument that the answer is
usually obvious long before the document ends.

## A threshold on a proportion is the one thing you can sample

Which is most of what this repository is about, applied to its own hot path. Long input is read for
**5,000 characters** and the share estimated from that; the full document is read only when the
estimate lands within **0.15** of the bar.

MEASURED on those 40 long documents (median 12,471 characters), the prefix estimates the
full-document share to within **0.0077 median, 0.0180 at p90, 0.0261 at worst** — and **zero verdict
flips**. The margin is about six times the worst observed error.

| input at the cap | before | after |
|---|---|---|
| ordinary prose | 3.88s | **1.20s** |
| `"a,"` repeated | 13.71s | **1.48s** |
| bullet lines | 3.76s | **0.50s** |

> ⚠️ **Every figure in this round is a cold-process measurement, and round sixty-five says so.** Each
> includes a one-time ~1.0s spaCy model load that a running server pays once, not per request. The
> ratios above are therefore understated — steady-state it is 1.526s → 0.229s on prose, a 6.7×
> improvement rather than 3.2×. The numbers are not wrong; they were published without the condition
> that produced them, which is the thing this repository exists to complain about.

The note itself is MEASURED unchanged on **425 real documents** — 400 short, which take the exact path
untouched, and 25 long ones — and still fires on a document that is 96.6% preserved material.

## The test that would fail if the shortcut were the whole story

Every test above passes with the fallback deleted, which is exactly the shape of vacuity rounds
forty to forty-two and fifty-seven kept finding. So there is one more: a document whose **first 5,000
characters sit at 0.466 and whose full share is 0.735.** The prefix alone says *no note*; the truth
says *note*. Verified both ways — the shipped code answers "note", and deleting the fallback fails
that test and only that test.

## Two things this round did not do

✗ **It did not change what gets locked.** The prefix is read for the *note* only. Every rewrite still
locks the whole document, so no entity, citation or quotation is less protected than before.

✗ **It did not widen the degenerate-input guard, though that was the first idea.** `preserve.py`
already skips NER for "a pasted symbol blob", gated on word-character share below 0.10 and on long
punctuation runs. `"a,"` has a word-character share of **0.500** and no runs, so it sails through —
the guard measures the wrong quantity, since spaCy's cost is per *token* and that input is 50,000
one-character tokens where prose of the same length is about 9,000.

A mean-word-length gate separates them cleanly: MEASURED across 3,000 real abstracts the minimum is
**4.54** and every degenerate shape sits at **1.00**. But it also puts a markdown table and a CSV
paste at 1.00, and those can hold real names worth locking, so the gate would have traded a
correctness risk for speed. **The prefix estimate costs nothing in correctness and gets the same 9×,**
so the guard was left alone and the finding is recorded rather than acted on.

## The suite, finally

Round sixty-three's fix is what made this round possible, and the number is worth stating: the full
suite runs **9,953 passing tests in 6m33s**. Its 74 failures are identical, test for test, to those
at the pre-session commit — every one an absent optional dependency (`torch`, `peft`, `sacremoses`)
or a blocked `huggingface.co`. Verified by running the same 35 files in a worktree at `8f8d09e`:
**zero regressions in either direction.**

---

# Round sixty-five — the round about unstated conditions published figures with an unstated condition

Round sixty-four measured a scoring request at the cap, found an advisory caveat taking 88% of it,
fixed that, and published **3.88s → 1.20s** on prose. Profiling the *fixed* path to find the next
hot spot showed `_mostly_locked_warning` still at 84% — on a 5,000-character prefix, which cannot
possibly cost 1.8s of per-character work.

It does not. It is the **spaCy model load**, paid once when a process first locks anything. Every
number round sixty-four published was measured in a fresh process, so all of them carry a constant
that a running server pays once and never again.

## The same benchmark, warm

MEASURED at `674d04f` (round sixty-three) against `7773aee` (round sixty-four), median of three runs
after one warm-up call, each with different text so the caches miss:

| input at the cap | before | after | improvement |
|---|---|---|---|
| ordinary prose | 1.526s | **0.229s** | **6.7×** |
| `"a,"` repeated | 10.852s | **1.498s** | **7.2×** |
| bullet lines | 3.017s | **0.514s** | **5.9×** |

✗ **The published ratio was wrong in the flattering direction for the code and the unflattering one
for the fix.** Prose reads as 3.2× cold and is 6.7× warm, because a ~1.0s constant sits in both
halves of the cold ratio and shrinks it. `"a,"` reads as 9.3× cold and 7.2× warm, moving the other
way — which is the point: **a constant added to both terms of a ratio does not bias it in a
predictable direction**, so there is no correcting a cold number by inspection.

⚠️ **Nothing published was false.** Those really are the times a cold process takes. What was missing
is the condition, and this project's entire argument is that a number without its condition is not a
measurement. Round twenty-four established there is no such thing as *the* false-positive rate, only
one per corpus definition. There is no such thing as *the* request latency either — there is one per
process state, and the two differ by 6.7× on the shape that matters most.

## Where the time goes now

Warm, at the cap, nothing dominates. On `"a,"` the largest single cost is spaCy's own pipeline at
**0.534s**, then `_claimed_spans` at 0.304s, then a numpy `gemm` at 0.162s and Unicode folding at
0.050s. That is a healthy profile: no one call is more than a third, and the remaining spaCy cost is
on the 5,000-character prefix that round sixty-four introduced rather than on all 50,000.

Prose at **0.229s** warm is the number a deployed `/score` actually pays. It was 1.526s.

## What was added

The regression test's ceiling was 6.0s, chosen against cold measurements, which makes it far looser
than it looks: against the MEASURED 0.229s warm prose figure it takes a **26×** regression to fire.
It is now 1.0s for prose and 6.0s for the comma blob, each about four times the warm cost and each
below the pre-fix one, VERIFIED by running the file in a worktree at `674d04f` — prose 1.44s, commas
11.46s, both failing. ✗ **A first draft used 3.0s for prose, which the old code passed at 1.526s.**
A ceiling the defect clears is decoration, and it took running it against the defect to notice. It now pins the
steady-state cost after a warm-up call, where the headroom is real and the numbers mean what a server
would see.

---

# Round sixty-six — the scorer got slower when you ran two of it

The API server offloads every endpoint with `asyncio.to_thread`, so two simultaneous requests run on
two threads. MEASURED on `score_text`, threads against the same calls made one after another in the
same process:

| concurrency | sequential | threaded | ratio |
|---|---|---|---|
| 2 | 0.176s | 0.640s | **3.65×** |
| 4 | 0.340s | 1.148s | **3.37×** |
| 8 | 0.656s | 1.504s | **2.29×** |

**Concurrency made the work take three to four times longer than doing it one request at a time.**
Not slightly worse — worse than the serial baseline it should have matched.

## It is not the GIL, and proving that took isolating every component

Under the GIL, N CPU-bound Python threads take roughly as long as N sequential calls: a ratio near
1.0, not 3.5. MEASURED per component at 4 threads:

| component | threaded / sequential |
|---|---|
| `_claimed_spans` (pure-Python regex) | 1.17× |
| `score_tells` | 0.97× |
| detector `score` | 1.22× |
| `preserve.lock` | 3.23× |
| **`_spacy_entity_spans`** | **4.13×** |

Everything written in this repository behaves exactly as the GIL predicts. **One dependency's model
pass does not**, and at the `score_text` level that is invisible — it just looks like "threads are
bad here". The component sweep is what turned a symptom into a cause.

✗ **BLAS thread oversubscription was the first hypothesis and it was wrong.** MEASURED with
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`, the ratio at n=2 moves from 3.65× to
3.09×. Real but small; the plausible cause accounted for about a fifth of the effect.

## The fix is a lock, which reads backwards until you look at the numbers

`preserve._NER_LOCK` serialises the `nlp(text)` call. MEASURED:

| concurrency | sequential | threaded | threaded, holding the lock |
|---|---|---|---|
| 2 | 0.142s | 0.563s (3.97×) | 0.151s (**1.06×**) |
| 4 | 0.294s | 1.055s (3.59×) | 0.281s (**0.96×**) |
| 8 | 0.588s | 1.862s (3.17×) | 0.558s (**0.95×**) |

**If running two passes at once costs four times running them in turn, then taking turns is the
optimisation.** End to end on `score_text` the ratio falls from 3.65×/3.37×/2.29× to
**1.12×/1.27×/1.26×**, and a single uncontended call is unchanged at a MEASURED 73.2ms median. The
lock sits inside the uncached implementation, so cache hits still run fully parallel.

⚠️ **The pathology is worse on a loaded machine, which is the wrong direction.** Removing the lock to
check the tests still fail gave **26.06×** on NER and **23.97×** on `score_text` — against 3-4× when
the box was idle. It degrades hardest exactly when a server is busiest.

## And a comment that a later commit made false

`run.py`'s `_RNG_LOCK` said it "costs nothing today because the only concurrent caller already
serialises", and in the same paragraph predicted that offloading the endpoints to a threadpool
"would have exposed this one". **The offload landed afterwards.** The prediction came true and the
sentence beside it stayed.

MEASURED on `untell_text`, threads against a single call: 2 concurrent **1.88×**, 4 concurrent
**3.88×**, 8 concurrent **7.87×** — throughput flat at **0.9 rewrites/second at every level**.
Rewrites are serial per process and the ceiling does not move with load. That is a real limit rather
than a defect: serialising is what keeps `--seed` reproducible. The comment now says so, with the
numbers.

**Nothing tests a comment.** Round sixty-two found a checker and its fixer disagreeing; this is the
same shape between a comment and a commit that came later, and the only reason it surfaced is that
someone measured the thing the comment described.

---

# Round sixty-seven — three code-changing rounds, and not one score moved

Rounds sixty-three through sixty-six rewrote seven regexes, changed when the locked-share note reads
the whole document, and put a lock around spaCy's model pass. Each was verified locally — round
sixty-three compared 1,144 spans, round sixty-four compared the note on 425 documents. **None of them
verified the thing a user actually receives: the score.**

Round sixty-one saved the detector score for every one of the 6,810 pre-LLM abstracts. Re-scoring all
of them on the current code:

    n before 6810   n now 6810
    scores that changed: 0

**Not "within tolerance" — identical, to four decimal places, on every document.** Three rounds of
changes to the scoring path's regexes, its caveat logic and its threading, and the output is
bit-for-bit what it was. That is the strongest statement this repository can make about a refactor,
and it was available only because round sixty-one had written the baseline down.

## Nothing tests a comment, so now something tests some of them

Round sixty-six found `run.py` asserting that its lock "costs nothing today because the only
concurrent caller already serialises" — true when written, falsified by a later commit that the same
paragraph had predicted. `untell-audit` gained `check_source_comment_counts`: counts that a source
comment states about the code, re-derived from the code.

It guards one claim, made three times in `run.py` — that `structural.py` draws from the global
`random` module in **27 places**, which is currently exact and is the stated reason the real fix
"is not something to do blind". A number that sizes future work should not drift from the code it
sizes. Adding one draw site fails all three, VERIFIED.

Deliberately a short list rather than a parser for the general form. A checker that guesses which
numbers in prose are assertions produces false alarms, and false alarms are how a checker gets
ignored — the same reasoning that produced `without_code_spans`.

## The guard that the file about guards did not have

`test_every_audit_check_can_fail.py` exists because twelve of eighteen audit checks were once
unmentioned anywhere in 4,949 tests. It fixed those twelve by hand **and never added the check that
keeps the next one covered.** MEASURED at round sixty-seven: **4 of 19** had no known-negative —
`check_census_counts`, `check_largest_repo_claims`, `check_named_repo_stars`, and the one this round
had just added.

All four now have one, and `test_every_check_has_a_known_negative` fails when a `check_*` appears
with no case. VERIFIED by adding a probe check: it is named in the failure.

## Three things that went wrong writing it, all the same shape

✗ **The first count said five, including `check_attribution`.** The collector searched for the
check's name *in quotes*, and `test_attribution` calls `audit.check_attribution(report)` bare. The
measurement of the coverage gap had the same defect as the coverage gap.

✗ **The first `largest_repo_claims` mutation narrowed "eight largest" to "three largest" and the
check passed** — because the exhibits genuinely are the three largest, so the narrowed claim was
still true. A mutation a correct document survives proves nothing.

✗ **The second mutation edited the wrong document.** The check reads the exhibits in
`why-best-open-repo.md`; the census page carries a similar-looking claim it never reaches. The check
passed again, reporting the same three exhibits it had always seen. **A mutation aimed at the wrong
file is indistinguishable from a check that cannot fail** — which is precisely why `assert_passes`
runs first and why the premise assertions in each case are not decoration.

---

# Round sixty-eight — the survey skipped a year and nothing said so

`eval/litreview.py`'s `VOLUMES` ran 2020, 2021, **2023**, 2024, 2025, 2026. The string `2022` appears
nowhere in the file. Not an exclusion with a reason — a hole in the middle of the survey's
denominator that no comment acknowledged, in the list that produces this project's most-cited
research claim.

Seven 2022 volumes exist and resolve: `acl`, `emnlp`, `findings`, `naacl`, `coling`, `lrec`, `aacl`
— **4,997 papers**.

## What adding them did, which is almost nothing, which is the result

MEASURED by `python -m eval.litreview --download`, run once before adding the volumes and once after:

| | before | after |
|---|---|---|
| volumes | 108 | **115** |
| abstracts indexed | 38,231 | **43,224** |
| detection-related | 578 | **588** |

| topic | before | after | move |
|---|---|---|---|
| robustness/paraphrase | 26.5% | 26.2% | −0.3 |
| multilingual/cross-lingual | 13.3% | 13.3% | 0.0 |
| human-AI mixed/edited | 11.2% | 11.1% | −0.1 |
| watermark | 7.6% | 7.5% | −0.1 |
| education/integrity | 7.6% | 7.5% | −0.1 |
| calibration/thresholds | 3.8% | 3.7% | −0.1 |
| fairness/non-native bias | 2.1% | 2.2% | +0.1 |
| **false positives/accusation** | **1.9%** | **2.0%** | +0.1 |
| disability/neurodivergence | 0.2% | 0.2% | 0.0 |

**Thirteen percent more corpus, and no share moves by more than 0.3 points.** The imbalance this
project's strategy rests on — an order of magnitude more work on evading detectors than on the
people they accuse — survives its sixth independent change to the corpus beneath it, and this is the
largest single one.

## The genuinely new fact is in the ratio of the addition

4,997 papers contributed **10** detection-related ones: **0.20%**. The other 38,231 contributed 578,
or **1.51%** — DERIVED from the two MEASURED survey runs above. Seven and a half times the density.

**The field is three years old.** ChatGPT shipped in November 2022, and a year of ACL, EMNLP,
Findings, NAACL, COLING, LREC and AACL published either side of it contains almost nothing the
survey's patterns match. Machine-generated-text detection did not begin with ChatGPT — GPT-2 output
detection and GROVER predate it — but as a *research programme* with hundreds of papers a year, it
did. That is worth knowing when reading any claim about what "the literature" has settled: on this
subject the literature is barely older than the tools it studies.

## The check that caught the drift, doing its job

`test_the_shipped_measurement_reproduces_round_fifty_sevens_numbers` pins the noise floor at `80 of
578`. Widening the corpus failed it, and it named the drift rather than letting five documents keep
a stale pair. MEASURED on the widened corpus the figures are **81 of 588 (13.8%)**, largest share
move **1.5 points**.

✅ **And the pre-LLM corpus is untouched, which had to be checked rather than assumed.** The 2022
files now sit in the same `.anthology-cache` that `eval/pre_llm_fpr.py` reads, and every calibration
figure in this repository depends on that corpus being exactly what it was. It filters on the year in
each paper id, so MEASURED after the addition it is still **6,811** abstracts at a 60-word floor —
the same number rounds sixty-one through sixty-seven used.

That is the second time in this session a pinning test has earned its cost by failing — and the
first time one of them failed for a *good* change rather than a defect. A test that only ever fires
on mistakes has not been shown to fire on anything else.

---

# Round sixty-nine — the missing venues were the ones most likely to falsify the claim

Round sixty-eight found 2022 missing by hand and stopped there. The systematic sweep that should have
followed immediately found **forty-three volumes across five years that exist, resolve, and were not
indexed — 2,892 papers.**

Two are main conferences: `2023.eacl` (335 papers) and `2024.eacl` (281). The rest are journals,
shared tasks and workshops.

## The venues mattered more than the count

⚠️ **`trustnlp` and `bea` were both absent, in every year.** Trustworthy NLP, and Building
Educational Applications. Those are precisely where work on false accusation, detector fairness and
classroom use is published — and this survey's headline finding is that such work is scarce.

**A venue list that omits them under-samples the exact topics whose scarcity it reports.** That is
selection bias pointing toward this project's own conclusion, which is the worst direction for it to
point, and it was not deliberate: nothing in the file chose those venues or excluded them.

## So the prediction was made first, then tested

If the omission mattered, adding those venues should raise `education/integrity` and
`false positives/accusation` specifically. MEASURED, across the three corpus states:

| topic | 108 vols | 115 vols | 158 vols | **186 vols** |
|---|---|---|---|---|
| robustness/paraphrase | 26.5% | 26.2% | 26.2% | **25.7%** |
| multilingual/cross-lingual | 13.3% | 13.3% | 13.3% | 13.4% |
| human-AI mixed/edited | 11.2% | 11.1% | 11.1% | 10.8% |
| **education/integrity** | 7.6% | 7.5% | **7.9%** | 7.7% |
| watermark | 7.6% | 7.5% | 7.4% | 7.2% |
| calibration/thresholds | 3.8% | 3.7% | 3.7% | 3.6% |
| **false positives/accusation** | 1.9% | 2.0% | **2.2%** | 2.1% |
| fairness/non-native bias | 2.1% | 2.2% | 2.2% | 2.1% |
| disability/neurodivergence | 0.2% | 0.2% | 0.2% | 0.2% |

**The prediction was right in direction and small in size.** At 158 volumes both target topics moved
up and only those two did; `education/integrity` briefly overtook `watermark`. The headline ratio
went from **153:11** to **157:13** — from 13.9:1 to 12.1:1.

The last column closes every gap `--gaps` reported. **From 108 volumes to 186 — 72% more volumes,
23% more abstracts — the largest share move in the table is 0.8 points**, and it is robustness losing
ground.

✅ **The claim survives the most adversarial widening available to it.** Not a random extra year:
the specific venues where the allegedly-missing work would live, added on purpose to see whether the
imbalance was an artefact of not looking there. It was not. There are still twelve times as many
papers on evading detectors as on the people they wrongly accuse, after searching the two workshops
devoted to trustworthiness and to education.

Corpus after, MEASURED: **186 volumes, 46,905 abstracts, 612 detection papers**, noise floor
**81 of 612 (13.2%)** with a largest share move of 1.4 points. The pre-LLM corpus is MEASURED
unchanged at **6,811** — checked again, because it shares the cache and every calibration figure in
this repository depends on it.

## `--gaps`, so the next hole is a command rather than a hunch

`python -m eval.litreview --gaps` probes every venue named anywhere in `VOLUMES` against every year
named anywhere in `VOLUMES`, and lists what exists and is not indexed. The rule it encodes is the one
that makes a hole detectable at all: **if a venue is worth indexing in one year it is worth indexing
in the next.**

It reports rather than adds. Which volumes belong in a survey is an editorial decision about scope,
and a tool that widened the corpus behind its author's back would produce numbers nobody chose — the
failure this whole ledger is about, arriving through the front door.

✗ **And the first draft of this section claimed it then reported none, which was wrong.** The rule
is every known venue against every known year, so **closing a gap opens gaps**: adding `trustnlp` for
2023 makes its absence from every other year a finding. Forty-three closed, twenty appeared; twenty
closed, sixty-two appeared.

That is not a runaway — it is the rule doing what it says, and **fifty-four of those sixty-two were
2020 and 2021**, years that are in `VOLUMES` for a different corpus entirely. The file has always
said so: they exist to give `eval/pre_llm_fpr.py` human ground truth, and they predate the field the
survey counts. Probing them for survey venues is a category error, so the sweep now starts at
`SURVEY_FROM_YEAR = "2022"`. The remaining eight were real and are indexed.

The twenty include several venues with nothing to do with detection — `crac` is coreference, `codi`
is discourse, `law` is linguistic annotation — and they are in anyway. **Keeping only the on-topic
ones is how a denominator acquires a thumb on it.** The rule that makes a hole visible is venue
consistency across years, not a judgement about relevance.

✅ **VERIFIED, not asserted this time**: after the eight went in, `--gaps` prints *"no gaps: every
venue named in VOLUMES is indexed for every year it names"*. The corpus reached a fixed point in
three iterations.

---

# Round seventy — the retraction guard could not see a retracted claim that wrapped

Reading row 28 — the last open item — turned up a paragraph in `ROADMAP.md` that opens by retracting
a claim and closes by making it:

> ✗ **An earlier version of this paragraph justified that gap by asserting that "formulaic phrasing,
> low burstiness, regular sentence length" are documented features of autistic writing. No source
> says that, and checking it reversed the argument.**
>
> […eight lines…]
>
> The traits detectors key on — formulaic phrasing, low burstiness, regular sentence length,
> template adherence — **are documented features of some autistic writing**.

The retraction and the claim, in the same paragraph. Round seventeen withdrew that sentence; it has
stood ever since.

## Why the guard missed it, which is the more general problem

`tests/test_retracted_claims_do_not_survive_elsewhere.py` exists for exactly this, and has carried
the pattern `low burstiness, regular sentence length` since round seventeen. It reported nothing.

**These documents hard-wrap, and the phrase wraps between `regular` and `sentence`.**
The guard searched one line at a time, so it could not match a phrase that spans the break.

✗ **Every multi-word retired form in the table was one wrap away from invisible.** Eight of the
eleven patterns are multi-word. Whether a retraction was enforced depended on where the paragraph
happened to break — a property of the text width, not of the claim.

The fix folds single newlines to spaces before matching, and maps the hit back to a line by counting
newlines in the original. Blank lines are left alone, because a paragraph break is not a wrap.
Folding preserves length, so an offset means the same position in both strings — VERIFIED on
`ROADMAP.md`, and pinned by a test that puts the phrase on line 41 of a fixture and requires the
report to say 41.

## What it found the moment it could see

Two live instances, both restating the retired trait list as fact: `ROADMAP.md:507` and this ledger
at line 1366.

The roadmap's is now removed and replaced by what actually justifies row 28 — the MEASURED finding
that autistic university students wrote with **fewer grammatical errors** and at a **higher reading
level**, which is what detectors read as machine-like. Distributional distance, not deficit. The
ledger's is annotated in backticks as a mention, per the convention that entries are annotated rather
than rewritten.

## The shape

Round sixty-two: a checker and its auto-fixer disagreed about what a claim is. Round sixty-six: a
comment and a later commit. This one: **a guard and the typography of the documents it guards.**

Each time the check was correct on its own terms and blind to a case nobody had thought to construct.
The pattern was right, the table was right, the retraction was recorded in the right place — and a
line break decided whether any of it did anything.

---

# Round seventy-one — the same blind spot, in the check that guards a privacy claim

Round seventy fixed the retraction guard's line-based matching. The obvious next question is what
else has that shape, and the answer was the highest-stakes check in the audit.

`check_demo_privacy_claims` exists to stop a document telling users their text never leaves their
machine while `demo.html` POSTs it to an API. It matched its phrases — `nothing uploaded`,
`never uploaded`, `runs entirely in your browser` — as substrings of the raw document.

MEASURED by planting the identical false claim in `docs/index.md` two ways:

| how the claim is written | verdict |
|---|---|
| `The demo runs entirely in your browser, so nothing leaves your machine.` | **FAIL** — caught |
| the same sentence, wrapped between `your` and `browser` | **PASS** — missed |

**A line break was the difference between a privacy claim being caught and being published.**

## One check already knew, and the knowledge did not travel

`check_corpus_bound_claims` collapses whitespace before matching, and its comment says why:

> the first version matched the raw text and missed the exact sentence it was written for, because
> the README writes the claim as "to **zero while preserving meaning**" and the asterisks sit inside
> the phrase. A checker that any bold-face defeats is worse than none: it reports PASS.

Whoever wrote that had the whole insight — a phrase matcher is defeated by anything that inserts a
character mid-phrase — and applied it to emphasis markers in one check. **Newlines do the same thing,
and the sibling check twenty lines away never learned either lesson.**

`audit.flatten_prose` is now the shared answer: lower-case, emphasis stripped, whitespace collapsed.
Both checks use it.

## The durable part

`tests/test_a_line_break_does_not_defeat_a_document_check.py` plants a claim each phrase-matching
check must report **twice** — once on a line, once split at its midpoint — into a real copy of the
repository, and requires both to be caught. It asserts the unwrapped case first, so a probe that
tests nothing fails loudly rather than passing vacuously; that is the shape round sixty-seven hit
twice while writing mutations.

VERIFIED to fire: reverting the one-line fix in `check_demo_privacy_claims` fails it, naming the
check, the claim and the remedy.

## ⚠️ And writing this up tripped the check it describes

Quoting the three phrases the check looks for made the newly wrap-safe check report *this entry* —
the fourth time in this project that documenting a defect reproduced it. Round fifty-five settled the
rule for the count checks: inline code is a mention, not a claim, so `without_code_spans` blanks it
before matching. **The privacy check never inherited that rule either.** It does now, composed with
the whitespace fix: `flatten_prose` blanks code spans first.

Two rules, both already written down in this repository, neither of which had reached this check —
in the same round, in the same function.

✅ **And then the pre-commit hook caught the third instance**, before it reached the remote. The
roadmap row written for this round used the phrase itself, which the check duly reported. The hook —
added in round fifty-three precisely because four self-triggers had been pushed — refused the commit
and named the guard.

**Then the sentence you are reading did it a fourth time**, by quoting the phrase again while
explaining the third. Both are in backticks now. Round fifty-five's rule works exactly as designed
and is easy to forget in the same paragraph that invokes it: **describing a defect is the single most
reliable way to reproduce it**, and the only defence that has ever held is structural — a mention
marked as a mention, and a hook that refuses the commit when it is not.

## Three rounds, one lesson, arriving three times

| round | the two things that disagreed |
|---|---|
| sixty-two | a checker and its own auto-fixer, about what a claim is |
| sixty-six | a comment and a commit that landed after it |
| seventy | a guard and the typography of the documents it guards |
| **seventy-one** | **two sibling checks, one of which had already learned it** |

The last is the one worth sitting with. This was not an unknown failure mode: it was written down,
in the same file, in a comment explaining a bug of exactly this kind. **A lesson recorded in a
comment beside one call site is not a lesson the next call site inherits** — which is the argument
for `flatten_prose` being a function rather than a fixed regex, and the same argument round
sixty-two made for `_MODULE_CLAIM` and round sixty-three made for `eval/arms.py`.

---

# Round seventy-two — the bound this repo recommends is 10.78% for short documents

`untell/calibrate.py` shipped `calibrate_by_length` alongside `calibrate`, with a docstring saying
that one threshold across all lengths "is one average". **Nobody had measured what the average
costs.** The scores and word counts for all 6,810 pre-LLM abstracts were already saved from round
sixty-one, so it took one arithmetic pass.

MEASURED, the global α = 0.05 threshold of 0.5401 by document length:

| band (words) | documents | realised FPR | 95% CI | band's own threshold |
|---|---|---|---|---|
| **60–100** | 603 | **10.78%** | [8.55%, 13.51%] | 0.6087 |
| 100–150 | 3,032 | 5.11% | [4.38%, 5.95%] | 0.5422 |
| 150–200 | 2,705 | 4.03% | [3.35%, 4.84%] | 0.5283 |
| 200+ | 470 | 2.55% | [1.47%, 4.41%] | 0.5187 |

**The five percent bound is 10.78% at the short end and 2.55% at the long one.** The short band's
interval does not reach 5% from below — its *lower* limit is 8.55% — so this is a real breach of the
guarantee, not sampling noise.

## The direction is the bad one

Short documents are where this repo has separately measured the highest false-positive rates
(**30.0% at 50 words or fewer**), where a detector has least evidence, and where a wrong accusation
is least recoverable. The global bound is loosest exactly there.

✗ **And the corpus floor conceals the worst of it.** These abstracts are 60 words or more, so
**60–100 is the mildest short-document band that exists in this corpus.** Whatever happens below 60
words is worse and unmeasured by this table.

## The scale, against this ledger's own recent history

Rounds sixty and sixty-one spent two full rounds — a retraction, a correction to the retraction, and
a new function — on the **0.0060** between two global thresholds derived from different sample sizes.

**The spread across length bands is 0.0900. Fifteen times larger.**

Read the other way it is the same fact: the short band's threshold applied to the whole corpus flags
**1.25%**, the long band's flags **7.14%**. One number cannot serve both ends, and the number this
repository publishes is the mixture's.

## Why it was invisible

`calibrate()` is what the documentation demonstrates, what the roadmap's calibration table uses, and
what rounds sixty, sixty-one and sixty-five all argued about. `calibrate_by_length()` sat beside it,
correct and tested, and **no document ever quoted a number from it.** The function that would have
shown the problem was shipped, exercised by a unit test with synthetic data, and never pointed at the
corpus.

That is a third kind of blind spot, after round sixty-two's checker-versus-fixer and round
seventy-one's two sibling checks: **a right answer that exists in the code and never reaches a
document.** Nothing was wrong. Nothing was stale. It simply was not run.

## ✅ Incidental: round sixty-two's fixer, working in the wild

Committing this round tripped the count guard — six new test modules since the last repair — so
`untell-audit --fix-counts` ran for the first time since it was rewritten. It set the counts in
`why-best-open-repo.md` and `humanizer-census.md` and **left this ledger alone**, which is exactly
what round sixty-two changed it to do after it rewrote two historical entries here, one of them a
count quoted inside a code span. Both of those lines are still as written.

---

# Round seventy-three — the warning stops at 40 words; the risk does not

Round seventy-two measured the *calibrated* threshold by length. This one measures the threshold
users actually get. MEASURED at the shipped verdict bar of **0.45** on all 6,810 pre-LLM abstracts —
human by construction, so every flag is a false positive:

| band (words) | documents | flagged | 95% CI |
|---|---|---|---|
| **60–100** | 603 | **28.69%** | [25.22%, 32.43%] |
| 100–150 | 3,032 | 20.65% | [19.24%, 22.12%] |
| 150–200 | 2,705 | 17.26% | [15.89%, 18.73%] |
| 200+ | 470 | 12.77% | [10.05%, 16.09%] |
| all | 6,810 | 19.47% | — |

**More than one human document in four, between 60 and 100 words, is flagged.**

`_short_text_warning` stops at `_MIN_WORDS_FOR_A_VERDICT = 40`. So every one of those 603 documents
got **no caveat about length at all** — the cliff is at 40 and the elevated rate runs past 100.

The evidence is also stronger than what the existing bands rest on: **6,810 documents that are human
because of when they were published**, against 40 HC3 texts truncated to length.

## Two corrections while building it, both about which number is which

✗ **The first version gated on `DEFAULT_THRESHOLD`, which is the wrong knob.** `threshold` defaults
to **0.30** and is the *loop's stop target*; `verdict_threshold` is **0.45** and is what `flagged` is
decided on. The rates above are measured at 0.45. Gating on the loop target would have printed a
0.45 rate for every caller who left the loop alone — attributing one threshold's number to another,
which is the exact defect `_threshold_range_warning` exists for. It now gates on the verdict bar, and
a caller who sets their own gets nothing.

✗ **The first version fired on 40–200 words, and an existing test was right to reject it.**
`test_the_specific_caveat_comes_first` guards against stacking caveats, and it caught a 66-word
sample of ordinary prose going from one note to two.

The test was making a real point. **20.65% and 17.26% sit either side of the corpus-wide 19.47%**, so
a note at 100–200 words says "this document is average" — on the majority of all input, while burying
the situational caveats the ordering rule exists to surface. The band is now 40–100 only, where
28.69% is **1.5× the corpus average and 2.2× the 200+ rate**, and that is what makes it worth saying.

## What the fixture change was, since weakening a guard to pass is the temptation

`PROSE` in that test was a 66-word paragraph — squarely inside the band, so the caveat firing on it
is correct behaviour, not noise. The fixture is now 131 words, which is what "ordinary prose" was
meant to mean, and **`SHORT_PROSE` is the old 66-word paragraph with its own test**: it must earn the
length note, and the standing tier note must still keep the last word. The guard is stronger than
before, not weaker — the case it used to cover by accident is now covered on purpose.

## The unmeasured range is named rather than interpolated

40–60 words is not measured: the pre-LLM corpus floors at 60. The rate there is **higher**, since it
rises as text shortens — this repo separately measured 30.0% at 50 words or fewer — so the note says
so instead of quoting a number nobody derived.

---

# Round seventy-four — it is not that short text is noisy, it is that short text is mis-scored

Rounds seventy-two and seventy-three measured *flag rates* by length and recommended per-length
thresholds. Neither asked **why** short documents are flagged more, and the answer decides whether
that recommendation is right.

Two mechanisms produce the same flag rate:

* **Extra variance** — the detector cannot tell at short lengths, and the tail crosses the bar by
  accident. The honest response is *abstention*: say the score means nothing here.
* **A shifted mean** — the detector can tell and is systematically wrong. The response is a
  *per-length threshold*, because the signal is there and the bar is in the wrong place.

The distributions, MEASURED across all 6,810 abstracts:

| band (words) | n | mean | sd | IQR |
|---|---|---|---|---|
| 60–80 | 158 | 0.3792 | 0.1525 | 0.2115 |
| 80–100 | 445 | 0.3612 | 0.1373 | 0.2012 |
| 100–125 | 1,279 | 0.3477 | 0.1361 | 0.1864 |
| 125–150 | 1,753 | 0.3340 | 0.1255 | 0.1741 |
| 150–175 | 1,681 | 0.3328 | 0.1260 | 0.1726 |
| 175–200 | 1,024 | 0.3267 | 0.1216 | 0.1657 |
| 200–250 | 436 | 0.3122 | 0.1252 | 0.1626 |

**Both move.** The mean falls monotonically with length and so does the spread, so the table alone
cannot separate them.

## One variable at a time

Give the short band the long band's mean while keeping its own spread, then its spread while keeping
its own mean. MEASURED at the shipped 0.45, 60–100 words against 200+, a gap of **15.92 points**:

| counterfactual | flagged | share of the gap closed |
|---|---|---|
| matching the mean | 28.69% → **15.75%** | **81%** |
| matching the spread | 28.69% → 25.04% | 23% |
| matching both | 28.69% → 13.60% | 95% |

against a long-band rate of 12.77%. The two closures sum past 100% because the effects are not
independent.

✅ **It is the mean, four to one.** Short human text is not scored more *noisily* by this detector —
it is scored more *machine-like*. That is a worse finding than noise and a more tractable one: it
means `calibrate_by_length` is the correct fix, and abstention would be throwing away a signal that
is present.

**It also sharpens what the MEASURED 28.69% means.** A 60-to-100-word human abstract is not an
unmeasurable input; it is an input this detector systematically reads as more artificial — by 0.052
of mean score — for no reason having to do with who wrote it.

## Shipped rather than left as a script

`eval.length_standardized.decompose_length_gap` computes it, and reports the mechanism by name so a
caller does not have to reason it out. Round fifty-seven's rule: **a measurement that stays in a
one-off script does not travel with the number it qualifies.**

The tests give it a pure mean shift and a pure variance difference and require the right answer to
each. **A diagnosis that said "mean shift" for everything would have reproduced the real corpus's
answer by luck** — that case is the one that makes the real one worth anything.

⚠️ One detector, one corpus, one register. The mechanism is not claimed beyond that.

---

# Round seventy-five — the length bias is a small-sample bias in a coefficient of variation

Round seventy-four established that short documents are scored *higher*, not just noisier. This round
asks which term does it, and the answer is mechanical.

The lite score is `max(rep, 0.6·burst_signal + 0.4·common_signal)`, where `burst_signal` is
`(0.55 − cv) / 0.55` and `cv` is the coefficient of variation of sentence word-counts. MEASURED
across 3,000 abstracts:

| band (words) | sentences | burstiness CV | burst_signal | common_signal |
|---|---|---|---|---|
| 60–100 | 4.3 | 0.2848 | **0.4850** | 0.2023 |
| 100–150 | 5.9 | 0.3183 | 0.4274 | 0.2119 |
| 150–200 | 7.6 | 0.3442 | 0.3809 | 0.2432 |
| 200+ | 9.2 | 0.3706 | **0.3335** | 0.2691 |

`burst_signal` falls by 0.1515 across the range — **0.0909 of score at its 0.6 weight** — while
`common_signal` moves the *other* way and gives back 0.0267. Net 0.0642, against a MEASURED mean
score shift of 0.052. **Burstiness is the entire length effect and then some.**

## And the CV gradient is not about the writing

`_burstiness` divides by `n`, not `n − 1`, and applies no small-sample correction. A CV estimated
from four sentences underestimates the true one badly.

MEASURED on sentence lengths drawn from **one fixed distribution** whose true CV is 0.5000 — so any
gradient with sentence count is estimator bias by construction:

| sentences | `_burstiness` | + Bessel | + Bessel and 1/4n |
|---|---|---|---|
| 3 | 0.3778 | 0.4627 | 0.5013 |
| 4 | 0.4135 | 0.4775 | 0.5073 |
| 10 | 0.4588 | 0.4837 | 0.4958 |
| 100 | 0.4837 | 0.4861 | 0.4873 |

**The shipped estimator ranges over 0.106 on sample size alone; the corrected one over 0.014.** At
the 0.6 weight that is **0.116 of score handed to whichever documents happen to have fewer
sentences** — larger than the 0.052 shift actually observed, so the corpus effect is entirely
consistent with estimator bias.

Three rounds of measurement — flag rates, then mean-versus-variance, then components — end at a
missing `− 1` in a variance denominator.

## ⚠️ The correction is shipped and is NOT the default, deliberately

`burstiness_bias_corrected` is in `untell/detectors/perplexity_burstiness.py`, tested, and unused by
the scoring path. Swapping it in gives, MEASURED on all 6,810 abstracts at the shipped verdict
threshold:

| band | current | corrected |
|---|---|---|
| 60–100 | 28.69% | **16.42%** |
| 100–150 | 20.65% | 12.80% |
| 150–200 | 17.19% | 11.76% |
| 200+ | 12.77% | 8.51% |
| **all** | **19.44%** | **12.41%** |

A 36% relative cut in false positives, and the length ratio narrows from 2.25× to 1.93×.

✗ **That is half a measurement and the flattering half.** The correction raises every CV, which
lowers every score — mean 0.3366 → 0.2934 — and **a detector that fires less always has fewer false
positives.** The cost in detection power is not measurable here: it needs an AI-labelled corpus, and
HC3 and RAID both require network access this environment denies.

**Changing a detector's operating point on the half of the trade-off that flatters it is the exact
error this repository exists to document.** So the estimator is here with its evidence, the default
is untouched, and a test fails if anyone wires it into `lite_score` without doing the other half
first — naming, in its failure message, the measurement that has to come first.

That test is the deliverable as much as the function is. **A correct fix, held back for want of the
measurement that would justify it, is a different thing from a fix nobody found** — and only one of
them is honest to ship.

---

# Round seventy-six — the detector flags human abstracts more often than machine ones

Round seventy-five could not decide whether correcting `_burstiness` was worth doing, because the
decision needs AI-labelled text and both HC3 and RAID require network access this environment denies.
The instruction was to find a way.

**There is one. A language model wrote the corpus.** `eval/data/generated_abstracts.py` holds 70
academic abstracts across NLP subfields, written to match the human arm's register and length range
and nothing else. The label is not an annotation — it is the provenance, which is the one property
those downloadable corpora buy.

MEASURED at the shipped verdict threshold of 0.45, matched by length against pre-LLM ACL abstracts:

| band (words) | machine | human |
|---|---|---|
| 40–60 | **9.7%** [3.4%, 24.9%] n=31 | **64.5%** [46.9%, 78.9%] n=31 |
| 60–100 | **12.0%** [4.2%, 30.0%] n=25 | **28.7%** [25.2%, 32.4%] n=603 |
| 100+ | **7.1%** [1.3%, 31.5%] n=14 | **18.6%** [17.6%, 19.6%] n=6,207 |
| **40–100 pooled** | **10.7%** [5.0%, 21.5%] n=56 | **30.4%** [27.0%, 34.1%] n=634 |

**In every band the detector flags human text more often than machine text.** Over the matched
40–100 range the intervals do not overlap — 21.5% against 27.0% — and the mean score is **0.2962 for
the machine arm against 0.3718 for the human one.**

✗ **This is not a weak detector on this register. It is pointed the wrong way.**

## Why that is the result and not an artefact of arm construction

The arms are matched by length, because this detector's length effect is large enough to swamp
authorship — rounds seventy-two to seventy-five measured exactly that. Pooling happens only where
both arms have data; `eval/detection_power.py` reports a band present in one arm and absent from the
other rather than dropping it, since dropping it is what makes an unmatched comparison look matched.

The mechanism is round seventy-five's. The score's largest term rewards **uniform sentence length**,
and academic abstracts are uniform: 4.3 sentences at 60–100 words, tightly clustered in length
because the genre demands it. Machine abstracts written across seventy different topics vary more.
The detector is measuring genre conformity and calling it authorship.

## ⚠️ What this supports, and what it does not

* **One model, one register, n=56 in the machine arm.** No claim beyond academic abstracts.
* **These were written deliberately varied**, across seventy distinct topics. Typical model output —
  many completions of one prompt — would be more uniform and would score *higher*. So the true
  separation may be better than this shows.
* **It could not plausibly be reversed.** The human arm is 634 real abstracts and its rate is pinned
  to within a few points. Whatever the machine arm's true rate, the human arm is flagged at 30.4%.

## What it does to round seventy-five

Round seventy-five held back the `_burstiness` correction because it cut false positives from 19.44%
to 12.41% and the cost in detection power was unmeasurable. It is measurable now: MEASURED on the matched
60–100 band, the correction takes the machine arm from 12.0% to **8.0%** while taking the human arm
from 28.7% to **16.4%**.

**Both fall. The ratio improves. And both remain the wrong way round.** The correction is a real
improvement to a detector that, on this register, does not work — so the case for adopting it is
stronger than round seventy-five could show, and still not the case for trusting the thing.

> ✗ **"The ratio improves" is wrong, and round seventy-seven says why.** That reads a paired flag
> rate at a FIXED threshold as evidence of better separation. It is not: the correction lowers every
> score, so fewer documents of both classes cross a fixed bar. MEASURED threshold-free, AUROC over
> the matched range goes **0.3538 → 0.3402** — marginally *worse*. The correction changes where the
> scores sit, not how they are ordered.

The default stays unchanged, for the reason it always was: this is one register, and a change to a
shipped detector wants evidence from more than one.

---

# Round seventy-seven — threshold-free, and the correction to round seventy-six

Round seventy-six measured flag rates at one threshold. A flag rate is a property of the detector
**and the bar**; the ordering is a property of the detector alone. MEASURED on the matched arms:

| band (words) | AUROC | n machine | n human |
|---|---|---|---|
| 40–60 | **0.1873** | 31 | 31 |
| 60–100 | **0.3599** | 25 | 603 |
| 100+ | **0.4589** | 14 | 6,207 |
| **40–100 pooled** | **0.3538** | 56 | 634 |

95% bootstrap interval on the pooled figure: **[0.2824, 0.4272]** — the whole interval below 0.5.

> ⚠️ **These come from a reimplementation of the score's components, not from `score_text`.** Round
> eighty-four made the arc reproducible in one command and the command printed **0.3529**, CI
> **[0.2822, 0.4270]**. Both are right about what they measured; only one is what the shipped
> detector returns, and the published figures were corrected to it.

**So the inversion is not an artefact of choosing 0.45.** A random machine abstract outscores a
random human one 35% of the time. The detector's ordering is reversed, not just its operating point.

✅ **And the gradient confirms the mechanism.** AUROC climbs toward a coin flip as documents
lengthen — 0.1873, 0.3599, 0.4589 — which is what the small-sample burstiness bias predicts, because
longer documents have more sentences and less estimator bias. Round seventy-five derived that
mechanism from a simulation; this is the same curve in the outcome.

## ✗ The correction to round seventy-six

Round seventy-six reported that `burstiness_bias_corrected` moved the machine arm 12.0% → 8.0% and
the human arm 28.7% → 16.4%, and read the improved ratio as the correction helping.

**By AUROC it does not help.** MEASURED on the matched range: **0.3538 with the shipped estimator,
0.3402 with the corrected one.** Marginally worse. Per band it is 0.1873 → 0.2170 at 40–60 and
0.3599 → 0.3562 at 60–100.

The reason is simple once stated. **The correction raises every CV, so it lowers every score, so
fewer documents of *both* classes cross a fixed bar.** A paired flag-rate comparison at one threshold
cannot tell that apart from better separation. AUROC can, because shifting every score leaves the
ordering untouched — which is precisely the invariance a flag rate lacks.

This is the trap this repository documents, walked into while documenting it. Round sixty-five
published ratios without the process state that produced them; this published a ratio without the
threshold that produced it. **Both times the number was real and the comparison was not.**

## What it means for the estimator fix

`_burstiness` is genuinely biased — round seventy-five's simulation on a fixed distribution settles
that, and it is not in dispute. What round seventy-seven settles is that **fixing it does not fix the
detector.** The bias explains the *length* gradient; it does not explain why machine abstracts score
below human ones at every length. Something else does, and the mechanism named in round seventy-six
is the candidate: the score's largest term rewards uniform sentence length, academic abstracts are
uniform because the genre demands it, and that has nothing to do with who wrote them.

**Correcting an estimator inside a detector whose ranking is inverted improves the estimator.** It
was never going to improve the ranking, and the flag rates said otherwise for one commit.

---

# Round seventy-eight — it is not one bad term, it is the whole feature set

Round seventy-seven established that the detector's ordering is inverted on academic abstracts —
AUROC 0.3538, interval entirely below 0.5. The obvious next question is whether one term does it, and
the obvious candidate was burstiness, since rounds seventy-four and seventy-five had traced the
length effect to it.

MEASURED, each component ranked on its own over the matched 40–100 range:

| component | AUROC 40–100 | 40–60 | 60–100 |
|---|---|---|---|
| full score | 0.3532 | 0.1873 | 0.3595 |
| `burst_signal` | **0.4122** | 0.2565 | 0.3905 |
| `common_signal` | **0.3459** | 0.3148 | 0.4120 |
| `rep` | 0.5000 | 0.5000 | 0.5000 |

✗ **The hypothesis is refuted, and in the informative direction.** Both live components are below
0.5, and **burstiness is the better of the two.** Scoring on `common_signal` alone gives 0.3459 —
*worse* than the full score. Dropping the burstiness term would make the detector worse, not better.

## Why the common-word term is the more inverted one, which is legible once seen

`common_signal` rises with the fraction of very common words, on the reasoning that predictable
vocabulary reads as machine-generated. Academic abstracts are dense in function words and stock
phrasing — *we show that*, *in this paper*, *these results suggest* — because the genre is built from
them. Machine abstracts written across seventy different topics carry more varied vocabulary.

**The feature is reading genre, and in this corpus the genre is the human one.** Same conclusion as
round seventy-six's, arrived at from the opposite end: not "the detector is confused by short text"
but "every feature it has encodes academic register, and academic register is what the human arm is
made of".

That is why correcting `_burstiness` did not move the AUROC. **There is no term to fix.** The bias
round seventy-five found is real and worth correcting on its own terms, and correcting it leaves a
detector whose every live feature points the wrong way on this register.

## ⚠️ And a mistake caught before it was published

`rep` sits at exactly 0.5000 in every band. My first reading was that it is dead code: I probed it
with `"the the the …"`, `"We show that."` repeated, and an `a b c` cycle, got 0.0 from all three plus
0.0 on 3,070 real documents, and concluded it never fires.

**All three probes were under forty words**, which is `_repetition_signal`'s own documented minimum,
so they hit the length guard and never reached the type-token test. Probed properly it returns
**1.0** on 100 repeated words, on `"alpha beta"` × 60, and on a sentence repeated 25 times, and 0.0
on prose.

So the 0.5000 is correct and expected. The function is a **degenerate-collapse guard**, not a
discriminative feature, and its docstring says exactly that: on 800 HC3 texts "this term is exactly
0.0 and the detector's measured FPR/TPR are unchanged by construction". It exists so a rewriter that
collapses into repetition cannot win the loop.

**A constant is not evidence of dead code, and a probe that returns nothing is not evidence the code
does nothing.** The check that mattered was reading the function's own stated preconditions before
concluding anything from a null result.

---

# Round seventy-nine — the finding reaches the pages people read

Round seventy-two's lesson was that `calibrate_by_length` was correct, tested, and never pointed at
the corpus, so the problem it would have shown stayed invisible: **a right answer that never reaches
a document does nothing.**

Rounds seventy-six to seventy-eight produced the most consequential measurement this project has
made — the lite tier's ordering is reversed on academic abstracts, AUROC 0.3538 with the whole
interval below a coin flip — and for three rounds it lived only in this ledger.

`README.md` and `docs/index.md` now carry it, above the calibration answer rather than below it,
because the calibration answer is a fix for the false-positive half of a detector whose other half
had never been measured.

## The README's framing needed the change more than its numbers did

Its second paragraph opens: *"What this is for: finding out how much a detector's verdict is worth."*
Every figure under it was a false-positive rate. **A false-positive rate cannot answer that
question** — a detector that flags nothing scores perfectly on every one of them. The page argued
that detectors are wrong about human text far more often than their vendors admit, which is true and
which is not the same as saying the verdict is worthless.

Now it says both, with the interval, and with the limits named in the same breath: one model, one
register, 56 machine documents in the matched range. The human arm is 634 real abstracts, so the
human rate is solid and the machine rate is not precise. **What the interval rules out is that the
two are the right way round.**

## Two stale figures found while doing it

`docs/index.md` still published **12 fairness papers and 77 multilingual**, and a noise floor of
**13.8% moving no share by more than 1.7 points**. Round sixty-nine widened the corpus from 108
volumes to 186 and those became **13, 82, 13.2% and 1.4**. The retraction guard does not cover them
because nothing was retracted — they were correct when written and the corpus grew underneath them.

Round fifty-nine found the README twenty-seven rounds stale for the same reason. **A number that is
merely superseded has no marker to search for**, which is why the survey figures are pinned by a test
and these were not.

## ⚠️ And the attribution window shifted again

Inserting a section between a number and its `MEASURED` marker un-attributed the calibration
paragraph — the third time this session. Round sixty-five hit it inserting a blockquote, round
sixty-eight inserting an annotation.

The check reads a window of lines around each number, so **editing anywhere above a claim can
silently detach it from its source**, and what the audit reports is the number rather than the
insertion that moved it. It has caught something real every time, and every time the fix has been to
put a marker on the line rather than to widen the window — a wider window would attribute numbers to
sources that merely happen to be nearby.

---

# Round eighty — a superseded number has no retired form to search for

Round seventy-nine found `docs/index.md` publishing **12** fairness papers and **77** multilingual,
ten rounds after round sixty-nine widened the corpus from 108 volumes to 186 and made them **13** and
**82**. It was found by reading, which is not a method.

Nothing could have caught it. The retraction guard searches for retired *forms* — a phrase somebody
withdrew — and **nothing was withdrawn.** Those numbers were correct when written and the corpus grew
underneath them. There is no string to look for, only a value to re-derive.

The census already solved this shape: it commits its raw data and re-derives every published count
from it. The survey could not, because its corpus is 186 Anthology XML files that are downloaded
rather than committed. `eval/data/survey_counts.json` is the artefact that closes the gap —
`python -m eval.litreview --json` regenerates it — so the corpus stays a download and the counts
stay checkable, which is the property that mattered.

`check_survey_counts` reads every live document against it. VERIFIED to fire: reverting the round
seventy-nine fix fails it and prints both tuples.

## ⚠️ The first version was wrong, and the way it was wrong matters

It matched single numbers — `(N) detection papers`, `(N) on fairness` — and reported fifteen
violations. Most were not violations.

**This repository runs two surveys.** The sample is `eval/litreview` over 186 volumes and 46,905
abstracts. The **census** is the entire ACL Anthology — **1,718 volumes, 82,352 abstracts, 763
detection papers, 1952 to 2026** — built from a partial clone, and it is what the roadmap's headline
argument quotes: 164 robustness papers against 20 on false positives, across the whole published
history of the field.

So the check was reporting the census's 763 as drift against the sample's 612. **Two correct numbers
for two different measurements.** It also flagged `70 abstracts` (the generated machine corpus),
`6,810 abstracts` (the pre-LLM corpus) and `2021 abstracts` — a year.

A checker that reports correct numbers as errors gets ignored, which is the failure mode this
project has now recorded four separate ways. The fix is composite patterns matching **whole published
sentences** rather than numbers in isolation: the volumes, abstracts and detection-paper counts have
to appear together, in the order and phrasing the sample's own sentence uses. Two such sentences
exist and both agree.

**Reading the hits before believing them is what separated the one real defect from fourteen
false alarms** — and the false alarms were the more interesting half, because they surfaced that the
repository's two surveys are easy to confuse and nothing had said so in one place.

---

# Round eighty-one — the AI-tell catalogue fires on half of pre-ChatGPT academic writing

Rounds seventy-six to seventy-eight measured the lite *score* against machine text. This project has
a second detector — the hand-written tell catalogue, 29 patterns across thirteen categories — and it
had never been measured against machine text at all.

MEASURED at matched length against the generated abstracts:

| | machine | human |
|---|---|---|
| documents with at least one tell | **8.6%** [4.0%, 17.5%] | **48.1%** [44.2%, 52.0%] |
| mean tells per document (40–100 words) | 0.036 | 0.953 |
| **AUROC** | **0.2697** | — |

**Twenty-six times more tells on human academic abstracts than on machine-written ones**, and an
AUROC further from a coin flip than the lite score's 0.3538. **Every one of the thirteen categories
that fired at all fired more on human text.** There is no exception to find.

## The catalogue is a list of academic register markers

MEASURED across the full 6,842-document corpus, share of known-human documents carrying each:

| category | human documents |
|---|---|
| `ai_vocab` | **45.67%** |
| `formulaic_transition` | **18.43%** |
| `negated_contrast` | 3.06% |
| everything else | under 2% each |

And by individual string, MEASURED the same way:

| tell | human documents |
|---|---|
| **`state-of-the-art`** | **25.37%** |
| `furthermore` | 5.26% |
| `moreover` | 5.15% |
| `leverage` | 4.25% |
| `robust` | 3.84% |
| `comprehensive`, `crucial` | 3.33% each |
| `utilize` | 2.65% |

**One string accounts for a quarter of the corpus.** `state-of-the-art` sits in the vocabulary list
between `best-in-class`, `top-tier`, `turnkey` and `supercharge` — which are promotional register.
In NLP it is the standard term for the best current method, and `robust` is a statistical term.

**The catalogue is not wrong about marketing copy. It is being applied to academic prose, where these
are the field's own words.** Nearly half of everything published at ACL before ChatGPT existed
contains at least one word from a list of AI indicators.

## What was done about it, and what was not

✗ **The catalogue was not edited.** Deciding whether `state-of-the-art` belongs on a list of AI
indicators is a judgement about the registers this corpus cannot speak for, and a corpus of NLP
abstracts is the worst possible evidence for removing the NLP term of art.

✅ **The base rates ship instead.** `eval/data/tell_base_rates.json` holds the measured share of
known-human documents carrying each tell and each category, and `score_tells` now returns a
`human_base_rate_note` when a fired category is one most human writing also has.

*"8 AI tells"* invites being read as eight pieces of evidence. *"8 tells, of which two categories
appear in 45.7% and 18.4% of known-human academic abstracts"* is the same count and a different
verdict. **A count without a base rate is not evidence, and this tool had been reporting counts
without base rates since it shipped.**

## The schema guards did their job

Adding one returned key failed **seven** tests across four files — the OpenAPI schema, the published
response schemas, the result-shapes document and the returned-key audit. Every one of them existed
because a key had once been added and documented nowhere.

⚠️ And the result-shapes parser reads line by line, so writing the new key's `(only when …)` note
across a line break made the entry unparseable and the key still counted as undocumented. **The note
has to fit on one line** — a constraint nothing states, discovered by a test that was right twice for
different reasons.

---

# Round eighty-two — the catalogue is an excellent detector of something else

Round eighty-one left two explanations standing for the tell catalogue firing on 48.1% of human
academic abstracts and 8.6% of machine ones: it is broken, or it reads **register** and academic prose
is not the register it flags.

Those separate by holding authorship constant. `eval/data/generated_registers.py` is assistant-reply
and marketing copy written by the same model, in the same session, as the abstracts.

MEASURED, arms matched by length:

| comparison (same author) | academic | other register | AUROC |
|---|---|---|---|
| 60–100 words, assistant | **0.092** tells/100w (n=25) | **7.357** (n=12) | **1.0000** |
| 30–60 words, promotional | **0.000** tells/100w (n=31) | **8.523** (n=12) | **1.0000** |

**Eighty times the tell density between two registers by one author**, and at 30–60 words the
academic arm carries *no tells at all* while every promotional passage carries several. Both
separations are perfect.

And the control: **promotional against assistant is 0.5625** — the catalogue cannot tell its own two
target registers apart, which is exactly what it should do if it is reading the thing it flags.

## So the catalogue works. It is not measuring what it says it measures

✅ **It is an excellent register classifier.** Built from assistant-style and marketing LLM output —
`ai-tells.md` and the 435-repo census — and on that material it separates perfectly from academic
prose, at n as small as twelve, with the arms length-matched.

✗ **It is not an authorship classifier**, and round eighty-one measured the cost of using it as one:
AUROC 0.2697 on machine-versus-human at matched length. **A perfect classifier of register, used as
a classifier of authorship, is worse than a coin flip** whenever the two arms differ in register more
than they differ in author — which is exactly the situation whenever a human writes in the register
an assistant favours, or an assistant writes in a register it does not.

The categories that fire on the assistant and promotional arms are the ones you would predict:
`ai_vocab` on 22 of 24 passages, `formulaic_transition` on 11, `cliche` on 9, `sycophancy` on 4.
Those are real properties of that prose.

## ✗ And the lite score does not even do that

Run on the same register comparison, `score_text` gives **AUROC 0.5095** — a coin flip. Its means are
0.2998 for academic, 0.3164 for assistant, 0.3651 for promotional: barely ordered at all.

MEASURED, both detectors on both questions:

| what is being separated | tell catalogue | lite score |
|---|---|---|
| register (same author) | **1.0000** | 0.5095 |
| authorship (matched length) | 0.2697 | 0.3538 |

**The catalogue detects one thing perfectly and the wrong thing badly. The score does neither.**

That is the fairest account this project can give of its own two detectors, and it took holding
authorship constant to get it — which is available to anyone with a language model and was not
available with a downloaded corpus, because a downloaded corpus cannot hold the author fixed.

---

# Round eighty-three — a machine-written abstract is judged more human than a real one

Rounds eighty-one and eighty-two measured the two detectors. `humanness` is the number a user
actually reads — a 0-100 score `untell` puts in front of people — and it inherits both.

MEASURED at matched length, 60–100 words, lite path:

| arm | n | mean humanness |
|---|---|---|
| **machine: academic** | 25 | **80.8** |
| human: academic | 603 | **75.4** |
| machine: assistant | 12 | 71.7 |

> P(machine academic reads MORE human than human academic) = **0.6733** — should be below 0.5
> P(human academic reads MORE human than machine assistant) = **0.6009** — should be above 0.5

**A machine-written abstract is judged more human than a real one, two times in three.**

## The 0.978 was in the file all along, and it is a property of the corpus

`untell/humanness.py` already recorded AUROC **0.978** on HC3 pairs at full length. HC3 is chatbot
question-and-answer text — **the register a language model is stereotyped for, and the one the tell
catalogue was built from.**

So the same score, on three comparisons:

| what it is asked to separate | MEASURED |
|---|---|
| HC3: assistant-register machine text from human answers | **0.978** — excellent |
| machine assistant text from human academic text | 0.6009 — right way, weak |
| machine academic text from human academic text | **0.6733 the wrong way** |

**Same tool, three verdicts, and the variable is register.** Round eighty-two established why by
holding authorship constant: the tell catalogue separates registers perfectly (AUROC 1.0000, one
author) and separates authorship worse than a coin flip (0.2697). A score built on those signals
inherits both properties exactly.

The 0.978 and the reversal now sit in the same comment, because a figure recorded without the
condition that produced it gets read as a property of the score. That is round sixty-five's finding
and round seventy-seven's, arriving a third time in the file that a user's number comes from.

## ✅ And the score orders the machine registers correctly

Authorship held constant, the MEASURED means are academic **80.3**, assistant **71.7** and
promotional **66.4** — the ordering anyone would give. **It is a working instrument pointed at the wrong quantity.** That is
a more useful thing to know than "it is broken", and it is the third time this arc has landed there:
the catalogue is a perfect register classifier, the score is a decent register orderer, and neither
is an authorship classifier.

## ⚠️ Two mistakes while measuring it

✗ **`humanness()` returns a float, not a dict.** My verification script called `.get("score")` on it
and died. The measurement was already right — the first script handled both shapes — but the check
written to confirm the direction convention was the thing that broke, which would have been a poor
reason to doubt a correct number.

✗ **The direction convention is worth spelling out, not inferring.** Higher humanness means *more
human*, so a working tool puts machine text BELOW human text, and an AUROC computed the usual way
(P(positive > negative)) reads backwards for this score. The figures above are printed with the
direction named in the same line — `should be below 0.5`, `should be above 0.5` — because a sign
error here would invert the headline and read as a fix.

---

# Round eighty-four — the arc becomes one command, and the command corrects it

Rounds seventy-six to eighty-three are the most consequential measurements in this repository and
they were reproducible only by re-deriving the scripts that produced them. `eval/detection_power.py`
existed but needed two pre-scored JSON files that nothing shipped knew how to make.

    python -m eval.detection_power --run --registers

now builds both arms, scores them, and prints the whole arc: flag rates per matched band, the pooled
comparison, the AUROC, the inversion verdict, and the same-author register table. `--limit` caps the
human arm for a fast run; the Anthology cache is the only prerequisite, and the tool names the
download command when it is missing rather than rendering an empty table that reads as a result.

## ✗ And the first thing it did was contradict a published figure

The command prints **AUROC 0.3529**. The README, the index, the roadmap and this ledger all said
**0.3538**.

Both numbers are real. Round seventy-seven computed the AUROC from a **reimplementation of the
score's components** — written to compare two burstiness estimators without re-running the whole
pipeline — and the difference between that and `score_text` is the clamping and `max` the shipped
path applies. MEASURED both ways on the same arms: 0.3538 from the reimplementation, **0.3529 from
`score_text`**, bootstrap CI [0.2822, 0.4270] against [0.2824, 0.4272].

**The reproduction command is the authority, not the script that found the result.** Every figure
that stands for *what the shipped detector does* is now 0.3529, and the 0.3538 stays where it belongs
— beside the estimator comparison it was computed for, labelled as the component path.

This is a small number and a large distinction. A published measurement whose reproduction command
returns something else is the defect this project exists to document; it had one for eight rounds,
and the fix was to make the command exist.

## What the harness is careful about

* **It bounds the human arm above as well as below.** The machine arm tops out near 220 words; a
  human arm running to 356 would compare length as much as authorship, which is what `eval/arms.py`
  exists for.
* **It skips text the detector declines to score** rather than folding a zero in. A no-signal reading
  is not a most-human-possible document.
* **It refuses without a human arm** instead of inventing a default, and names the missing download
  rather than printing dashes.

## ⚠️ The full tier remains unmeasurable here, and that is now settled rather than assumed

Every figure in this arc is the **lite** path. The README tells readers to re-run at `--tier full`
before trusting a flag or a clear, and that tier has never been measured against machine text.

VERIFIED, not assumed: `torch` and `transformers` are absent, no model is cached, PyPI is reachable
so the packages could be installed — and `huggingface.co` returns **403 at the egress proxy, by
organization policy**, so GPT-2's weights cannot be fetched. The blocker is policy, not effort, and
it is recorded here so nobody repeats the investigation.

---

# Round one hundred and fourteen — the study we said nobody had done, and the constant that decided it

`ai-writing-research.md`'s *Gaps worth noting* #5 has stood since that document was written:
homogenization and detection are never studied together despite being two views of one phenomenon,
and measuring false-positive rate against a writer's distance from the model's stylistic centre of
mass would connect them mechanically instead of by correlation. Everything the study needs was
already in this repository, so it was built: 6,810 ACL abstracts from volumes through 2021 —
**published before ChatGPT, so every flag is a false positive by construction** — against a centroid
built from the committed machine-written abstracts, with Burrows's Delta as the distance because it
already *is* a distance-from-a-centre-of-mass measure.

## The prediction looked refuted, at one vocabulary size

| quintile | n | mean words | crude FPR | 95% CI | standardized |
|---|---|---|---|---|---|
| 0 (nearest the machine centre) | 1,362 | 172 | 19.8% | [17.7, 21.9] | 21.3% |
| 1 | 1,362 | 162 | 17.1% | [15.2, 19.2] | 17.4% |
| 2 | 1,362 | 154 | 18.2% | [16.2, 20.3] | 18.4% |
| 3 | 1,362 | 144 | 20.6% | [18.6, 22.9] | 19.9% |
| 4 (farthest) | 1,362 | 130 | 21.7% | [19.6, 23.9] | 19.8% |

**Flat.** Every interval overlaps every other, and a length-stratified Cochran-Armitage trend test
gives **z=0.08, p=0.93** (MEASURED, `eval/data/homogenization.json`) — about as null as a number
gets.

⚠️⚠️ **THAT NULL WAS PUBLISHED, AND IT WAS AN ARTEFACT OF ONE CONSTANT.** The paragraph above
originally continued "on this corpus and this detector, homogenization and detection are not two
views of one phenomenon". The whole table and test are computed at **vocabulary size 150**, and the
finding does not survive varying it. Nine sizes, same 6,810 documents, same stratified test
(MEASURED, `eval/data/homogenization_vocab_sweep.json`):

|  30 |  50 |  75 | 100 | 150 | 200 | 300 | 500 | 800 |
|---|---|---|---|---|---|---|---|---|
| +3.91 | +3.70 | +2.03 | +0.50 | −0.41 | −2.49 | −3.70 | −5.02 | −4.30 |

**Smooth, monotone, significant at both ends in opposite directions.** 150 is where the curve
crosses zero — a null that reads as "no effect" and means "the sign changes here". This is rounds
eighty-six and eighty-nine again, a constant nobody chose deciding a published figure, committed by
the round that cites those rounds as its guard. The sweep *was* run at n=600, the flip *was* seen,
and the full-corpus headline was taken from a single size anyway.

## What the crossover establishes, which is a mechanism and not a null

`vocabulary()` returns the most frequent *n* words, so the constant is not a precision knob — it
changes what is being measured. Small *n* is almost purely function words, the classic stylometric
signal; large *n* has absorbed content words. **Two constructs sharing a name**, and the reversal is
the evidence that they are two:

* **In function-word space — the stylistic reading, and the one the gap actually names —
  false-positive rate RISES with distance from the machine centre.** Being stylistically unusual
  makes a human document *more* likely to be falsely flagged, not less. z=+3.91 at 30 words,
  p=0.0001.
* **In a content-inclusive space it FALLS.** z=−5.02 at 500, p<0.0001. That axis is substantially
  topic, and "distant in topic from a corpus of machine-written NLP abstracts" is not what anyone
  means by a stylistic centre of mass.

The gap asked for a study connecting homogenization to detection "mechanistically rather than by
correlation". There is a mechanism and it runs the other way: **detectors do not flag a writer for
resembling the model, they flag a writer for departing from the reference human distribution** — and
because the model also sits near that distribution's centre, the correlation the literature reports
looks like the first story while being produced by the second.

⚠️ **An interpretation this data does NOT test.** It is tempting to close the loop on §4 by saying
non-native writers sit far from the centre in function-word space — article and preposition use is
exactly a function-word signal — which would make the L2 false-positive result an instance of the
effect above. That is a hypothesis, not a result: **there is no non-native corpus here**, every
document is an ACL abstract, and nothing in this study measures a writer's background. It is
recorded as the next experiment, not as a conclusion.

## The naive version of the same study returns a significant result in the opposite direction

Unstratified, the identical data gives **z=2.16, p=0.031** for false positives *rising* with
distance (MEASURED, same artefact, `trend_crude`). Published, that reads as *being stylistically unusual protects you from detectors* — a
tidy, quotable, wrong finding, with a p-value.

It is the length confound wearing the result's clothes. The farthest quintile averages **130 words
against the nearest's 172**, because a short document estimates its own word frequencies badly and
lands further from any centroid by estimation noise alone; and this corpus separately flags
**28.69%** of 60-100 word documents against **12.77%** above 200. The whole effect is length, and
the distance axis is where it happened to be standing.

**Anyone filling this gap without stratifying by length publishes the reverse of the finding.** That
is the more useful half of this round: the gap is not merely unfilled, it is booby-trapped.

## What it means for the removal half, which is worse news

If distance had predicted false positives, "remove the AI tells" would finally have had a mechanical
definition — increase the distance — that did not route through the tell catalogue rounds eighty-one
and eighty-two measured as a register detector (AUROC 1.0000) rather than an authorship one (0.2697).
It does not, so that definition is not available.

The displacement arm makes it concrete. MEASURED with an exact sign test, ties excluded:

| rewriter | machine text (the actual job) | human text (the control) |
|---|---|---|
| composite | p=0.29 — no displacement | **p=0.0005, toward the machine centre** |
| structural | p=0.73 — no displacement | **p<0.0001, toward the machine centre** |
| targeted | p=0.29 — no displacement | **p=0.0066, toward the machine centre** |
| surgical | p=1.00, 39 of 40 unmoved | p=0.125 — no displacement |

**On machine text no rewriter moves the document off the machine centroid in either direction**,
while the detector score falls 0.3049 → 0.2684. On *human* text the same rewriters significantly drag
prose *toward* the machine centre — they homogenize the one population where that is unambiguously
the wrong direction.

So the loop's gains are **detector-specific, not stylometric**. That is the in-loop-versus-held-out
gap the free-ceiling report names as the central unknown, measured with a mechanism rather than
inferred from the literature.

## Scope, because a null needs it more than a positive does

One detector — the stdlib lite path. (`torch` itself is installable here; what the organization
blocks is `huggingface.co`, so the model weights are unreachable and installing the package would
change nothing. Round one hundred and fifteen measures both.) And this repo has
separately measured that path as near-chance on per-sentence targeting. **A null from a weak
instrument is weak evidence.** One corpus, one register, one distance measure, human documents only.
What is refuted is the mechanical claim on this setup, not the correlational finding in the fairness
literature that motivated it.

⚠️ Two things this round nearly got wrong and one it got wrong outright. The headline was first
computed at n=150 and showed a 12.6-point drop in the predicted direction — noise, and the full
corpus erased it. The vocabulary sweep at n=600 **flipped sign across the constant** (−0.053 at 50
words, +0.114 at 300).

**And then the headline was published from a single vocabulary size anyway, before the full-corpus
sweep had returned.** The commit message says the n=600 flip "is why nothing was published until the
full corpus had run" — the full corpus *curve*, not the full corpus *sweep*, and the difference is
the entire finding. Seeing a constant flip an effect's sign and then quoting one setting of it is a
worse error than never having swept, because the sweep is what made the flip known.

---

# Round one hundred and thirteen — the answer was a retry, and the sentinel that hid it

The cold-worktree probe round one hundred and twelve was waiting on came back, and it eliminated the
last candidate. MEASURED, every condition the sweep can present to `untell/scripts/audit.py`'s
selection — its five named test files, timed end to end on this machine:

| condition | time |
|---|---|
| **cold fresh worktree, no `__pycache__`** — what the sweep actually does | **113s** |
| four concurrent copies, four cores — the sweep's own worker count | 177–180s |
| solo, warm working tree, under unrecorded load | 206s |
| round one hundred and seven's recorded figure | 267s |
| the cut | 300s |

**The sweep's real environment is the fastest of them all.** Cold cache was the leading hypothesis
after contention was refuted, and it is refuted harder — a fresh worktree runs the selection in
just over half the time the warm tree did. Every explanation offered for round one hundred and
seven's timeout is now eliminated, and the honest reading is that the selection's runtime has a
tail that crosses 300s rarely, for reasons this machine does not preserve.

## Which turns the question from "why" into "so what", and there the harness is at fault

A transient crossing was enough to write the module off **permanently in a committed artefact**.
Round one hundred and ten moved the register's protected share 44.7% → 43.8% on exactly one such
flip; rounds one hundred and ten through one hundred and twelve spent two multi-hour sweeps and
three test rounds chasing it. Nothing retried, and nothing could have known to: `_failures`
returned the **same `UNUSABLE`** for a timeout and for a run that died before reporting, so the
`unmeasurable` record could only say *"its test selection times out **or** fails to collect"*.

**Two causes with opposite remedies, reported as one.** A timeout wants another try or a bigger
budget; a collect failure wants a dependency installed and will give the identical answer forever.
This is the defect this module was built to find in other code, sitting in its own error path.

Split into `UNUSABLE` and `TIMED_OUT`, with a retry on the timeout only, and the cause recorded.
The first sweep under the fix says so:

    unmeasurable: untell/detectors/fast_detectgpt.py | cause: collect_error | retried: False

`fast_detectgpt` **never timed out** — `torch` is absent, so it fails to collect — and every
artefact in this repository has been describing it with a disjunction that was half wrong.

## The split nearly introduced a worse bug than it fixed

`verify_survivors` tested `baseline == UNUSABLE`. After the split that misses `TIMED_OUT`, and the
consequence is not a skipped module: **the sentinel is itself a number**, so `observed > baseline`
holds for essentially any run, and every survivor of that module would have been reported *"killed by the
wider suite"*. The false-survivor rate — the precision figure round one hundred and three records
for this checker — would have come out **better than the truth**, from a sentinel change two
hundred lines away.

Caught by the failure-set diff against HEAD rather than by reading, which is the same method that
caught the vacuous test two rounds ago. The guard against it is general: a test now fails on any
bare `== UNUSABLE` anywhere in the module.

## And one of my own guards broke on a rename

The same diff showed `test_a_module_the_filter_empties_is_skipped_not_baselined` failing — it
pinned the literal `baseline = _failures(`, which the retry refactor renamed to `_usable_baseline`.
The property it guards was untouched. **A test that breaks on a refactor it does not care about is
a test that gets weakened or deleted by whoever is mid-refactor**, which is how a guard dies
quietly. Rewritten to match the assignment rather than the callee.

---

# Round one hundred and twelve — three sweeps, one answer, and the prediction still untested

With `--kinds` fixed, the experiment round one hundred and eleven could not run was run. Three
sweeps of the same tree, two worker counts:

| run | mutants | killed | survivors | identical survivors | `audit.py` measured |
|---|---|---|---|---|---|
| committed, 4 workers | 340 | 88 | 252 | — | yes |
| **serial, 1 worker** | 340 | 88 | 252 | **yes** | yes |
| fresh, 4 workers | 340 | 88 | 252 | **byte-identical file** | yes |

**The sweep is deterministic across runs and invariant to worker count.** Every kill/survive
verdict, every one of the 44 module baselines, and every baseline failure count agree. The fresh
four-worker run reproduced the committed artefact to the byte — same 93,123 bytes — so
`mutation_boundary.json` and `boundary_register.json` needed no change at all.

Worth stating because the staleness hook had been firing since round one hundred and eight: it
compares **mtimes**, and the content had not moved. The warning was right in principle — tests did
change — and the under-reporting it warns about was **exactly zero** this time. That is not an
argument for removing it; a sweep that happens to be unchanged is only knowable by re-running it.
It is an argument for reading "stale" as "unverified", not as "wrong".

## The prediction is still untested, and three runs is why

Round one hundred and ten predicted `--workers 1` would classify `audit.py` measurable. It did.
**So did both four-worker runs.** Round one hundred and seven's `unmeasurable` outcome has now
failed to reproduce three times.

**When the control arm never exhibits the condition, the comparison establishes nothing about its
cause.** Round one hundred and eight named this exactly — a plant whose control is dirty gives an
outcome that looks like a result and is not one — and the same discipline applies to a prediction
whose contrast case refuses to appear. Calling this confirmation would be the error that round
exists to prevent. The claim stands where round one hundred and eleven left it: **measured cause,
untested prediction.**

What the three runs did buy is the elimination of a rival explanation. Had the sweep been
non-deterministic in its *verdicts*, `audit.py`'s classification would be one symptom of a broader
instability. It is not: the only thing that varies between runs is whether a module is measured at
all, which is the timeout and nothing else.

## Then the contention claim was tested directly, and it is REFUTED

Waiting for a fifty-minute sweep to flake is a bad way to test a claim about a three-minute test
selection. The direct probe: run four copies of `audit.py`'s selection **concurrently** — the
sweep's own worker count, on four cores — and time each.

    copy 1  177s      copy 3  179s
    copy 4  178s      copy 2  180s          all four, wall clock 12:51:10 -> 12:54:10

**Every one finished faster than the 206.46s solo measurement**, against a 300s cut. Four-way
contention does not push this selection past the timeout; it does not push it past its own solo
time. Round one hundred and ten's explanation — recorded there as measured cause — **is wrong**, and
the 206.46s figure it rested on was itself the slow observation, not the fast one. It was taken
while other work was running on this machine, which the round did not record and should have.

So the honest state of the question is now worse than "untested": the leading hypothesis is
eliminated, and round one hundred and seven's timeout has no explanation. Two candidates remain,
and only one of them is a property of the harness:

* **cold `__pycache__`.** Every timing in rounds one hundred and ten and here was taken in the
  **warm working tree**. The sweep runs each baseline in a **fresh worktree** with no compiled
  cache, which is a cost none of these measurements include. Being probed.
* **machine state at round one hundred and seven**, which is not recoverable and not a finding.

The general lesson is the one this ledger keeps relearning: **a mechanism that explains the
observation is not thereby the mechanism**, and the cheap direct test — three minutes here — was
available the whole time while two multi-hour sweeps were spent circling it.

## An artefact for the claim, and its one defect

`eval/data/mutation_boundary_serial.json` is committed so the invariance above is checkable rather
than asserted. ⚠️ It was produced **before** the report-shape fix in the same round, so it carries
no `outcomes` key. The claim does not depend on one — identical survivor sets plus identical totals
over a deterministic candidate set pins the killed sets too — but the two artefacts are **not
shape-matched**, and anyone diffing them will find the key missing. Recorded rather than quietly
regenerated, because the missing key is itself the defect that round documented.

---

# Round one hundred and eleven — the flag that meant something different at one worker

Round one hundred and ten predicted that `--workers 1` would classify `audit.py` measurable every
time, contention being the variable. Running that prediction:

    python -m eval.mutation --all --kinds boundary --workers 1 --json
    03:58:35 -> 10:58:43    killed at a 7-hour timeout, no output at all

The four-worker boundary sweep of the same tree takes about fifty minutes. **The serial run was not
four times slower; it was a different job.** The CLI dispatches on worker count:

    runner = run_parallel if args.workers > 1 else run
    kwargs = {"workers": args.workers, "kinds": kinds} if args.workers > 1 else {}

`kinds` rode along inside the parallel-only branch, and `run` had no such parameter to receive it.
So `--kinds boundary --workers 1` **accepted the flag, ignored it, and swept every operator** — the
1,397-candidate run `run_parallel`'s own docstring puts at about four hours, started by someone who
asked for the 340-mutant one.

**Nothing warned.** Had it finished, the only evidence would have been a `by_kind` map carrying more
keys than the flag named, and nobody reads that to check a filter they passed. The defect is a flag
whose meaning depends on an unrelated flag's value, and the two functions had drifted because a
parameter was added to one of them.

Two smaller divergences came from the same drift. `_worker` skips a module the filter emptied;
`run` did not, and paid a full baseline pass — up to the entire timeout — for each one. And the
filter has to run BEFORE the `limit` spacing, because spacing a sample and then filtering it selects
different mutants from filtering and then spacing, so a capped run would have measured different
things on the two paths.

## The experiment is untested, and the ledger says so

Round one hundred and ten's contention claim is **neither confirmed nor refuted**. The run that was
supposed to test it never ran the comparison. That claim stands as written — measured cause,
untested prediction — and the re-run is now possible because the flag works.

⚠️ One alternative the serial run would not separate even when it completes: the 206.46s timing was
taken in the **warm working tree**, while every sweep baseline runs in a **fresh worktree with no
`__pycache__`**. Cold-start compilation is real overhead that figure excludes, and it would push the
baseline toward 300s independently of contention. A single-worker run removes contention only. If
`audit.py` still comes back unmeasurable at one worker, cold cache is the leading candidate.

## The test written for this was vacuous, and running it is what said so

The first version of `test_both_runners_narrow_the_same_way_in_the_same_order` reproduced each
runner's narrowing **inside the test** and asserted the two reproductions agreed. It passed against
the unfixed tree — because it never touched the code. It proved that filter-then-cap differs from
cap-then-filter, which is a fact about lists rather than about `eval/mutation.py`.

**That is precisely the vacuity this module exists to hunt, written by hand into its own test
file.** It was caught by running the new tests against a pre-fix worktree, not by reading them —
which is the same method round sixty-two's warning is about, and the reason a positive control is
worth the two minutes. Rewritten to read the real function bodies, all four now fail pre-fix and
pass post-fix.

---

# Round one hundred and ten — the share fell without a single boundary losing protection

The pre-commit hook had flagged the boundary sweep stale since round 108. Landed:

|  | old sweep | new sweep |
|---|---|---|
| mutants | 331 | **340** |
| killed | 86 | **88** |
| survived | 245 | 252 |
| score | 26.0% | 25.9% |
| unmeasurable modules | 2 | **1** |

| register |  |  |
|---|---|---|
| boundaries | 48 | 48 |
| protected | 21 | 21 |
| unprotected | 26 | **27** |
| unmeasured | 1 | **0** |
| protected share | 44.7% | **43.8%** |

**The share fell and nothing lost protection.** Exactly one boundary moved, and it moved out of
`unmeasured` into `unprotected`: `untell/scripts/audit.py:903`, the `_MODULE_DRIFT` comparison.
Round ninety's rule is that a zero meaning "could not test" and a zero meaning "does not matter"
are the same number and opposite facts. This is that rule paying out in the direction nobody
budgets for — **the placeholder was flattering, and measuring it made the number worse.** A reader
comparing 44.7% to 43.8% would see a regression; the truth is one fewer thing this repo cannot see.

## Why the module became measurable is not a change anybody made

Round one hundred and seven recorded `audit.py` as unmeasurable because its test selection — which
includes `test_every_audit_check_can_fail.py`, itself a mutation suite — takes about 4m27s, against
the harness's 300s timeout. Checked, both unchanged since: the selection is the same five files and
still includes the mutation suite, and `--timeout` still defaults to 300. **Same selection, same
timeout, opposite classification.**

⚠️ **This first said the baseline "sits close enough to the cut that two runs disagree", which was a
guess standing in for a measurement.** Timed since, alone on the machine: **206.46s**, against round
one hundred and seven's recorded 4m27s (267s) and the 300s timeout. Solo it is not marginal at all —
a 31% margin. What makes it marginal is that **the sweep runs four workers in parallel**, so no
mutant baseline is ever measured in isolation, and 206s of work contends with three siblings for
four cores. The variable is contention, not the module.

That distinction changes what to do about it. "Inherently borderline" argues for raising the
timeout; contention argues that the same sweep at `--workers 1` would classify `audit.py` measurable
every time, and that the 300s cut is being applied to a number the harness never observes on its
own. Neither is acted on here — what is recorded is that the cause is now measured rather than
assumed.

So 43.8% is a number whose denominator depends on how busy the machine was. It is recorded as
measured, because it is, and as unstable across rounds, because that dependency is real. Its 8
mutants — 2 killed, 6 survived, baseline clean — are real measurements either way.

## The new mutant this round added is my own, and it survived

Round one hundred and nine added one boundary-shaped comparison, `run.py:545`
`if unchanged >= rewrites:`. It accounts for the +1 mutant that is not `audit.py`'s +8, and the
sweep reports it **survived** — an off-by-one in code written last round, with tests written last
round for exactly it.

It is a **selection artefact, not a gap.** Applied by hand and run:

    tests/test_a_rewriter_that_wrote_nothing_does_not_report_a_refused_draft.py   5 failures
    tests/test_a_run_that_adopted_nothing_says_so.py                              1 failure

**Killed six ways.** Neither file is in `run.py`'s ten-test selection, which is ranked by breadth —
and a test written for one specific branch of one function is the least broad thing in the
repository, so the ranking puts it last precisely when it is the only test that matters. Round
ninety-nine found the same shape from the other side, where a breadth ranking dropped the boundary
tests and cost 22 kills.

This is not an argument for widening the selection: running ten thousand tests per mutant is what
the per-module selection exists to avoid, and the cost was argued when it was chosen. It is an
argument for reading a survivor as **"the selected tests do not kill this"** and never as "nothing
does" — which is what `eval/boundaries.py --verify` exists for, and what the sweep's own survivor
list does not say on its face.

---

# Round one hundred and nine — the rewriter that wrote nothing, reported as a draft refused

Asked of the tool rather than of its evidence: **run the humanizer on real machine text.** Not the
built-in demo corpus (three hand-written paragraphs, 37 words), and not HC3, whose published failure
is confounded — `hc3_roberta` is immobile on its own training corpus, so a null there measures the
detector's home-field advantage rather than the rewriter. The neutral corpus is
`eval/data/generated_abstracts.py`: 70 machine-written abstracts, already committed, in the academic
register this repo targets.

MEASURED, `tier=lite`, `max_iters=5`, 10 abstracts, the four no-key rewriters:

| rewriter | changed | adopted | score |
|---|---|---|---|
| composite (the default) | 5/10 | 6 | 0.3025 → 0.2692 |
| structural | 5/10 | 13 | 0.3025 → 0.2790 |
| targeted | 5/10 | 6 | 0.3025 → 0.2692 |
| **surgical** | **0/10** | **0** | **0.3025 → 0.3025** |

The default path works. `surgical` does not move a single document, and `stopped` reads `stalled` on
6 of 10.

## The mechanism

`SurgicalRewriter` passes `prefer_tells=True`, so `surgical_substitute` ranks words by `_tell_ranks`
— does swapping this word remove a catalogued tell. That function returns only words with
`gain > 0`. A text carrying no catalogued tell has `base = 0`, and a tell count cannot go below
zero, **so the ranking is empty and the substitution loop never runs one iteration.** The rewriter
returns its argument byte-identical.

MEASURED on 40 of the abstracts: **36 have an empty ranking, and 37 come back unchanged.** This is
not an edge case. Rounds eighty-one and eighty-two established that the tell catalogue separates
academic-vs-chatbot **register** at 1.0000 and authorship at 0.2697 — so formal prose is exactly the
text it has nothing to say about, and exactly the text this rewriter therefore cannot touch.

## The part worth the round: nothing reported it

An identical candidate passes every gate *by construction*. It reproduces every locked span, so the
sentinel multiset check holds. The meaning gate sees similarity 1.0. `score()` returns the same
number, so the adoption guard's `<=` on score holds. What stops it is the separate
`cand_best != best_masked` check — a comparison of the TEXT, not of the score the user is then
told about. Every surface then described a draft that was never written:

| surface | said | truth |
|---|---|---|
| `result["adopted"]` | 0 | correct |
| `result["inspect"]` | `candidate_accepted`, `adopted` | no draft was taken |
| `result["warning"]` | "every draft scored worse than your text" | nothing was compared on score |
| the remedy attached | "Try `--best-of 3` for more draws" | the rewriter is **deterministic** |

Two accountings of one decision disagreed — `_inspect_was_adopted` was set beside the
`cand_best != best_masked` guard rather than inside it — and **the one that lied is the one a user
opens to find out why nothing changed.** The suggested remedy could not work: the loop already
collapses `best_of` to a single draw for deterministic rewriters, so N draws are byte-identical by
construction.

## This is the fourth instance of one defect

`_nothing_adopted_warning` already carries two branches whose stated reason is that "scored worse"
would describe a comparison that did not happen — `vetoed` and `sentinel_failed` both `continue`
*before* the scorer. **The identical draw is the same defect one step earlier in the chain, where
there is no draft to compare at all,** and the branch structure built to catch it did not.

Worse, the test that was supposed to hold the note to a real run
(`test_a_run_that_adopted_nothing_says_so.py::test_it_reaches_a_real_run`) **stubbed the rewriter to
return its input** — constructing precisely this case — and asserted the scored-worse wording off it.
The test encoded the conflation it existed to prevent. Its assertion is corrected in place, with the
reason kept visible.

## The alternative fix, measured and rejected

The tempting repair is to give the tells objective a score-ranked fallback, so tell-free text still
has words to try. `surgical_substitute`'s docstring even claims the score rule is always available
("this only ever ADDS adoptions the score-only rule refused"). Prototyped and MEASURED on the same
40 abstracts:

| ranking | zero-substitution runs |
|---|---|
| `prefer_tells=True` (shipped) | 37/40 |
| `prefer_tells=False` (score-only) | **40/40** |

The score-only rule is not a path this text has and the tells rule lacks — it is a **worse version
of the same dead end**, for the reason that function's own candidate table already gives: the stdlib
heuristic cannot see a synonym swap, so `score < cur_score` is unreachable either way. Restoring it
would have bought nothing and cost the leave-one-out ranking pass.

**So the fix is not to manufacture an edit surface. It is to say there isn't one, and name a
rewriter that has one.** The loop now counts identical draws, `inspect` emits `candidate_identical`
and no longer claims an adoption the counter denies, and the note names the cause and points at a
rewriter that is not the one that just failed, instead of at more draws.

## The fix had the same defect in miniature

The first version of the note recommended `composite` unconditionally — and `composite` is the
**default**. It fires there for real: 1 of 20 abstracts, 15 identical draws. So a user who had
changed no setting was told to try what they were already running, by the note written to stop
exactly that kind of unusable advice. Two more overreaches in the same sentence: it asserted "more
draws will keep returning the same text" of a **stochastic** rewriter, where 15 identical draws are
evidence and not the guarantee that holds for a deterministic one; and it explained the empty run by
the tell catalogue, which is `surgical`'s edit surface and **not** `composite`'s — a mechanism that
was not the one that failed. All three are now conditioned on which rewriter actually ran.

## The shape

Round ninety-three asked whether the detector could be wrong with every test still passing. This is
that question asked of the *rewriter*: **it could do nothing at all, and every field the tool
publishes would report a working loop that had made a judgement call.** The measurement that found
it was not a new instrument — it was running the shipped tool on text of the kind it is for, which
no measurement in this ledger had done for the rewriter.

---

# Round one hundred and eight — the mechanism round one hundred and six could not find

Round one hundred and six ended with an admission rather than a fix. It had planted six defects for
`cache_keys`, measured **50% recall with the easy cases missed**, and nearly published that a gating
checker was blind to the most basic form of what it exists to catch. The plants were malformed —
three named their mutable global `_STATE`, and `"_STATE".isupper()` is **True**, which the checker's
own docstring reads as immutable — so they contained no defect and the checker was at 100%.

What caught it was disbelieving the number and going to read the docstring. The round said so:

> *That's a judgement, not a mechanism, and I haven't found a mechanism for it.*

## ✅ The mechanism: every plant is a minimal edit of its own control

A single source can only produce two outcomes — the checker fires or it does not — and "the plant is
empty" is indistinguishable from "the checker is blind". A **pair** produces four, and they separate
exactly the cases that were conflated:

| checker fires on | outcome |
|---|---|
| defective only | **detected** |
| neither | **the edit introduced no defect** — round 106's error |
| both | **the clean side already had a defect** |
| clean only | the checker is inverted |

MEASURED, round one hundred and six's exact plant re-run as a pair: it classifies as **"the edit
introduced no defect"**, not as a miss. The tool refuses to report a recall at all while any pair is
broken, because a broken pair is scored as a miss the checker did not commit.

## Why the pairing works rather than merely detecting

The `cache_keys` pairs differ from their controls **only in the case of the global's name** —
`_STATE` against `_state`, which is precisely the distinction that was got wrong. A test asserts it:
`pair.clean.replace("_STATE", "_state") == pair.defective`.

That is the part worth keeping. The mechanism does not just catch the error after the fact; **it
makes writing it require saying out loud which side of the convention each half is on.** Round one
hundred and six's plant cannot be expressed as a pair without noticing that both halves are the same
module.

A second constraint keeps the pairs honest: every edit must span **at most four lines**, asserted
per pair. A "clean" and "defective" version differing everywhere isolates nothing, and its outcome
could not be attributed to the defect it claims to test.

MEASURED after the rewrite: **28 pairs, 28 detected, 0 broken.** The recall figures are unchanged —
the checkers were always at 100% on these forms — and what changed is that the number now cannot be
produced by a plant that contains nothing.

## The general form

| round | evidence | how it was inflated | fixed by |
|---|---|---|---|
| 102 | findings | a rule too loose to be true | reading every finding |
| 106 | plants | a plant that was not a defect | **pairing each with its control** |

Both are the same failure at one remove: the evidence for a measurement needs the same scrutiny as
the measurement. Rounds ninety-one through one hundred and two established that for findings. This
establishes it for plants, and mechanically rather than by care.

---

# Round one hundred and seven — landing the sweep, and a module that measuring made unmeasurable

Rounds one hundred to one hundred and six all ran against a boundary sweep taken before round
ninety-eight's tests existed, with the pre-commit hook noting the staleness on every commit. This
lands a fresh one and reads what moved.

MEASURED, the register rebuilt on current data:

| | before | now |
|---|---|---|
| off-by-one caught | 18 | **21** |
| off-by-one survives | 30 | **26** |
| not measurable | 0 | **1** |
| protected share | 37.5% | **44.7%** |

All four thresholds round one hundred and one closed — `voice.py:185`, `tells.py:1081`,
`tells.py:1409`, `run.py:329` — now read as protected, which is the register confirming work it
could not see when it was stale.

## ✗ And one module became unmeasurable, because of a fix

`untell/scripts/audit.py` was measured in the previous sweep and is not in this one. The cause is
round one hundred's selection widening — the fix that recovered 22 kills by including tests that
name a module's threshold constants.

`audit.py` has many constants, so it now selects `test_every_audit_check_can_fail.py`, which is
**itself a mutation suite**: it mutates each audit check and re-runs the whole audit. MEASURED, one
baseline pass over that selection takes **4m27s**. A per-mutant timeout large enough to accommodate
it would put a single module's sweep into the hours.

**This is not fixed by raising the timeout, and it is recorded rather than hidden.** Its one
boundary, `_MODULE_DRIFT`, moves from *unprotected* to *unmeasured* — which is the honest
classification and slightly flatters the protected share, since the denominator loses a known gap.
Round ninety's rule again: a zero meaning "could not test" and a zero meaning "does not matter" are
the same number and opposite facts.

The general shape is worth naming. Round one hundred's fix bought **+22 kills** and cost **one
module's measurability**, and neither number was visible at the time — the gain showed up two rounds
later in a re-run, the cost three. A change to an instrument is not free just because its immediate
effect is an improvement.

---

# Round one hundred and six — a bad plant is a false miss, and it looks exactly like a real one

Round one hundred and five measured recall by planting defects and found a real blind spot. This
round extended the plants to `cache_keys`, a **gating** checker, and got:

    cache_keys   50.0%   easy 0/2   hard 3/4
                 missed: reads a module global, functools.cache, zero-argument cached function

A gating checker missing the most basic form of the thing it exists to catch. That is the kind of
finding a round is built around — and it was wrong.

## ✗ The plants were malformed, not the checker

All three "misses" named their mutable global **`_STATE`**. In Python `"_STATE".isupper()` is
**True**, and this checker's own docstring says upper-case names are treated as immutable, because
that is the convention the repository enforces elsewhere. So the plants contained **no defect**: a
cached function reading an immutable constant is exactly the case the checker documents as sound.

Rewritten with `_state`, MEASURED: **6 of 6**, including all three "misses" and both the
`functools.cache` and zero-argument forms.

## What that says about the method

Precision is **inflated** by a false finding. Recall is **deflated** by a false plant. They are the
same error in mirror image, and both look like news:

| | inflated by | deflated by | reads as |
|---|---|---|---|
| precision | a finding that is not a defect | — | the checker is better than it is |
| recall | — | a plant that is not a defect | the checker is worse than it is |

Round one hundred and two spent three iterations removing false findings from a checker. This round
spent one removing false plants from a measurement of a checker. **The method needs the same
discipline as the thing it measures**, and there is no reason it should have been exempt.

## ✅ The guard: a clean control per checker

Each checker now has a paired module containing **no** defect of its kind — a cached function over a
compiled regex, a justified constant, a comparison-free module, a read of a documented key. If any
fires, the tool **refuses to report**, because a checker that fires on anything scores 100% recall
for the wrong reason.

That is the same shape as the mutation harness's positive control, pointed the other way: the
positive control proves the instrument can see, and the clean control proves it is not merely
shouting. MEASURED: **28 plants, 28 detected, 0 clean controls fired.**

⚠️ **Neither control proves the plants contain what they claim.** A clean control catches a checker
that fires on everything; it cannot catch a plant that contains nothing, which is what happened
here. The only thing that caught that was reading the checker's docstring after disbelieving the
result — and the reason to disbelieve it was that a 50% recall on the easy cases of a gating checker
is too big a defect to have gone unnoticed this long.

---

# Round one hundred and five — a blind spot produces no findings, so reading them cannot find it

Round one hundred and four completed the precision column: all eight checkers carry a measured share
of findings that were real when somebody read them all. **None had a measured recall.**

The two are opposite questions. Precision is about the findings; recall is about the defects. A
checker reporting one finding and being right is **100% precise and may be missing forty** — and
every precision figure in the register was obtained by reading findings, which is a method that
cannot see anything a checker never reports.

So: plant a known instance of exactly what each checker claims to catch, run it, and see whether it
fires. `eval/checker_recall.py` does that with **22 plants across three checkers**, each labelled
easy or hard, because recall against easy cases is worth as little as a mutation positive control
that barely moves the score.

MEASURED: **21 of 22 on the first run.**

| checker | recall | easy | hard |
|---|---|---|---|
| `boundaries` | 8/8 | 2/2 | 6/6 |
| `constant_census` | 6/6 | 3/3 | 3/3 |
| `result_keys` | **7/8** | 4/4 | **3/4** |

## ✗ The miss was a gap that a precision fix had created

`result_keys` missed a read **inside a closure over the result**:

```python
def outer():
    result = score_text("hello")

    def inner():
        return result["whatever"]   # never checked
    return inner
```

Round one hundred and two pruned nested function bodies out of the module scan, to kill six false
positives from `eval/holdout.py`'s `render(result)`. That fix was correct and it silently blinded the
checker to an entire form.

**No amount of reading findings would have found this, because a blind spot produces no findings.**
The precision measurement in round one hundred and three said 89% and was not wrong; it was
answering a different question. Only planting the defect found it.

The scan descends again and carries the enclosing scope's origins inward, while a parameter or local
assignment rebinds the name and clears what it inherited — so the false positives stay dead.
MEASURED in both directions after the fix: **22 of 22 plants caught, and still zero findings on
the repository.**

## ✗ And a test whose name asserted the opposite of the design

`test_the_scan_does_not_descend_into_nested_functions` passed after the fix, because what it
actually asserts is that a nested function *shadowing* the name is not flagged — which is still
true. Its name states the opposite of how the scan now works.

A passing test with a misleading name is a defect: the next reader trusts the name over the body.
Renamed to `test_a_nested_function_shadowing_the_name_is_not_flagged`, with the closure case added
beside it as `test_a_closure_reading_the_outer_result_IS_flagged`.

## What the pair of numbers is for

| | measured by | blind to |
|---|---|---|
| precision | reading every finding | anything never reported |
| recall | planting known defects | forms nobody thought to plant |

Neither substitutes for the other and both have a stated blind spot. Recall here is 22 of 22 against
**the forms I thought to plant**, which is exactly the limitation precision has in reverse — and the
reason the plants are committed rather than described, so the next form can be added to a list
instead of remembered.

---

# Round one hundred and four — the harness measures itself, and it is the one with most to answer for

Round one hundred and three's register left exactly one checker **UNMEASURED**: the mutation
harness. That is also the checker with the most reason to be wrong, because **both of its known
defects produced false survivors** — stale bytecode meant a mutation never loaded (round
ninety-five), and a breadth-ranked test selection dropped the tests most likely to catch a boundary
(round one hundred). Neither could ever have produced a false *kill*.

A survivor is the harness's finding, so its precision is the share of reported survivors genuinely
uncaught by any test. Round one hundred and one measured the boundary register this way; the method
generalises to every operator.

MEASURED: **24 survivors, stratified 3 per operator kind, each re-run against every test importing
its module** rather than the capped selection the sweep uses.

| | |
|---|---|
| genuinely uncaught | 21 |
| killed by a test the sweep never ran | 3 |
| **precision** | **87.5%**, Wilson 95% [69.0%, 95.7%] |

That is consistent with the boundary register's **90%** (27 of 30) measured the same way — two
independent samples of the same harness landing within each other's intervals, which is more
reassuring than either figure alone.

**The register is now complete: 8 of 8 checkers carry a precision figure and the method behind it.**

## ⚠️ The per-kind cells are not a ranking, and saying so is the point

The sample is 3 per kind. Boundary, extremum and identity each came out 2 of 3 and the rest 3 of 3,
which looks like a finding and is not: **a 2-of-3 cell has a Wilson interval of [20.8%, 93.9%]** —
the entire plausible range. Publishing that table without the caveat would invite exactly the
operator-ranking claim round ninety-seven earned honestly with 355 mutants, on evidence that cannot
support it.

A test asserts the caveat is recorded, and says explicitly when it may be dropped: if the per-kind
samples ever grow past about five, the cells can be compared.

## What 87.5% licenses and what it does not

It licenses acting on a survivor list without re-checking each entry: roughly one in eight is
already covered, which is a tolerable rate for a backlog and an intolerable one for a gate — and the
harness does not gate. It does **not** license quoting a mutation score as the suite's coverage. The
two errors compound in the same direction: a false survivor understates the suite, and rounds
ninety-five and one hundred each found a systematic source of them.

The honest summary of every mutation figure in this repository is therefore: **a lower bound, on the
operators implemented, against the test selection used, with about one in eight survivors already
covered by a test the sweep did not run.** Every clause in that sentence was measured, and each one
took a round.

---

# Round one hundred and three — how far to trust each checker, written down

Round one hundred and two closed on a pattern with four instances and no owner: **the first version
of a static rule here is always too loose.** Each instance was found by reading every finding while
the list was short enough to read, and each was recorded in the round that made it — and nowhere
afterwards. A reader looking at `eval/` sees eight checkers and no way to tell which gate a commit,
which have had their findings verified, and which report a number nobody has ever read.

`eval/checkers.py` is the register. Per checker: what it checks, whether it can fail a commit, and
its **measured precision** — the share of its findings that were real when somebody last read them
all.

MEASURED across the eight:

| checker | gates | precision | findings now |
|---|---|---|---|
| `claim_verification` | yes | 100% | 0 drifted of 19 |
| `litreview --untriaged` | yes | 0% real | 0 untriaged of 33 |
| `cache_keys` | yes | 1 of 6 | 0 unaccepted |
| `result_keys` | yes | 89% | 0 |
| `boundaries` | no | 90% | 30 unprotected of 48 |
| `constant_census` | no | 11 of 12 | 41 undefended of 111 |
| `constant_influence` | no | n/a — reports an absence | 0 live of 35 |
| `mutation --all` | no | **UNMEASURED** | survivor lists |

**Seven of eight shipped a first version that was too loose.** That is the finding the register
exists to keep visible: not that any one checker was wrong, but that being wrong first is the normal
case here, and the only thing that has ever caught it is reading every finding.

## Measuring one of the two unmeasured checkers

`constant_census` had no precision figure, so a seeded sample of 12 of its 41 findings was read
against the source. **11 genuinely have no stated reason for their value**, including
`DEFAULT_THRESHOLD`, `DEFAULT_BAR = 0.76`, `BERTSCORE_BAR = 0.88` and
`_HUMAN_PARENTHESES_PER_100W = 0.80` — the last of which reads like a measured human rate and has
nothing saying so. One, `_MANIFEST_VERSION`, is a schema version rather than a threshold and was
never in scope.

⚠️ **The sample also exposed an ambiguity in the check's own definition.** For 5 of the 11, a comment
explains why the MECHANISM exists without saying why the number is that number:
`_MAX_NAMED_SIGNALS = 5` is capped so "the prompt stays proportionate to the actual worst
offenders", which is a reason for capping and not for five. Reading those as justified gives **6 of
12** instead of 11. Both are recorded, because the check cannot tell them apart and neither can a
single number.

## ✗ And the register made a false claim on its first run

It listed `constant_influence` as gating. That command always exits 0.

Its own test caught it — `test_the_gating_flag_matches_what_the_command_does` reads each registered
command's source for a non-zero return. **A false assurance is worse than an absent one**, because
somebody relies on it: a register saying a checker gates is a reason not to check by hand.

A second self-check earned itself immediately too. The render's closing line said the first version
had been too loose "five times out of eight" while the computed value was **seven** — a hardcoded
figure beside a computed one, in the round about checker reliability. It reads the computed value
now, and a test asserts it.

## What this is worth

The register does not make any checker better. What it does is make the honest state readable in one
place: four checkers can fail a commit, four cannot, one has never had its findings counted, and
seven of eight were wrong the first time. **A checker with no precision figure is not a precise one,
it is an unmeasured one** — round ninety's rule, turned on the instruments rather than the code.

---

# Round one hundred and two — six wrong keys is a defect class, not six mistakes

This session guessed a return shape wrong **six times**, in code written by someone who had read the
document warning about it:

| read | the key that exists | what it cost |
|---|---|---|
| `score_text(...)["score"]` | `max` | scored 0 of 6,842 documents after a twenty-minute run |
| `humanness(...).get("score")` | it returns a float | a verification script died |
| `score_sentences(...)["spread"]` | `unrankable` | a boundary test asserted nothing |
| `humanize_diff(...)["removed"]` | `removed_lines` | three tests failed at once |
| `score_tells(...).get("caveats")` | `warning` | a caveat test passed on an empty string |
| a line number off by one | — | a mutant reported as surviving |

Six is not carelessness six times. **`docs/result-shapes.md` opens by saying that guessing wrong
"returns a plausible value rather than raising"**, and the trap is not ignorance of the document —
it is reaching for the plausible key without opening the file, which no amount of documentation
prevents.

`tests/test_every_returned_key_is_documented.py` already checks one direction: every key these
functions RETURN is documented. It cannot see a caller reading a key that never existed.
`eval/result_keys.py` is the reverse: track `name = FUNC(...)`, then flag every `name["k"]` and
`name.get("k")` whose key that function does not return.

## ✅ Eight undocumented conditional keys

MEASURED on the repository: **8 keys are returned and were not in the documented list** — `scored`,
`out_of_range_detectors`, `timings`, `voice_warning`, `rewriter_warning`, `error`, `evidence_note`,
`matches`.

Every one appears **only under a non-default argument or a failure path**, which is precisely what
the forward check's payloads never exercise: `scored` only when nothing could be scored at all,
`error` instead of a rewrite when no rewriter is available, `timings` only with `--timings`. The two
checks are blind in opposite directions, and neither substitutes for the other. All eight are now
documented.

## ✅ And a test assertion that could not fail

```python
assert result.get("detector_modes", {}) or True  # shape may vary; the warning is the contract
```

`X or True` is a tautology. The assertion has never been capable of failing, and it reads a key
`score_sentences` does not return — which is how the checker found it. Its own comment says the
warning is the contract, so that is what the test asserts now.

## ✗✗✗ Three rounds of false positives in the checker, and the count is the point

MEASURED at each stage, the first version reported **38 distinct (function, key) pairs**, most of
them false. Three separate
defects, each found by checking a finding instead of believing it:

| version | distinct pairs | what was wrong |
|---|---|---|
| unordered `ast.walk`, no invalidation | 38 | a name reassigned from something else kept its old origin |
| ordered, invalidate on `=` | 25 | `for r in rows:` rebinds and was not treated as an assignment |
| plus loop/with/except rebinds | 16 | still descended into nested functions from the module scope |
| plus scope pruning and parameters | **9** (MEASURED, all verified by hand) | — |

Every one of the final nine was verified by hand against the source before being acted on. Eight
were real; the ninth was the tautology.

**A checker whose findings are mostly false is worse than no checker** — 38 reported against 8
real — and this
repository has now written that sentence about four separate checkers — the citation cross-check in
round ninety-two, the claim-verification proximity rule in ninety-one, the cache-patch rule in
ninety-six, and this one. The pattern is that the first version of a static rule is always too
loose, and the only reliable way to find out is to read every finding it produces while the list is
still short enough to read.

---

# Round one hundred and one — check the register before acting on it

Round one hundred produced a register of **30 unprotected boundaries** and the obvious next move is
to write thirty tests. **The harness has twice reported false survivors**: stale bytecode masking
mutations in round ninety-five, and a test-selection heuristic dropping the very boundary tests it
should have run in round one hundred. Both errors ran the same way — a harness that fails to load a
mutation and one that fails to reach a test both report a survivor.

A register inherits that. So each of the 30 was re-run against **every test importing its module**,
uncapped — 97 test files for `scripts/score.py`, 83 for `scripts/run.py` — which is unaffordable
across thousands of mutants and affordable exactly once for thirty.

MEASURED: **27 of 30 are genuine gaps; 3 were selection artefacts.**

| | |
|---|---|
| genuinely unprotected | 27 |
| already covered by a test the capped selection missed | 3 |
| register accuracy | **90%** |

`preserve.py:947`, `score.py:1516` and `score.py:1344` are protected by tests the sweep never ran.
Ninety per cent is good and the check was still worth its hour: it is three tests not written for
code that is already covered, and — more to the point — the register's accuracy is now **measured
rather than assumed**, which is the difference between a list you act on and a list you argue about.

## Four of the twenty-seven, closed

The user-visible ones — thresholds a person meets rather than internals:

| threshold | decides |
|---|---|
| `voice.MIN_SAMPLE_WORDS` | whether the user is warned their voice sample is too thin to profile |
| `run._MIN_VOICE_SAMPLE_WORDS` | whether a voice distance is computed at all |
| `tells._LANG_MIN_WORDS` | whether a document is considered for non-English detection |
| `tells._MIN_WORDS_FOR_A_RATE` | whether `tells_per_100w` carries its quantisation caveat |

MEASURED, each mutant re-applied against only the new test file: **4 of 4 boundary mutants killed**.

## ✗ And an assertion of mine that looked like a defect and was not

MEASURED from the source: `voice.MIN_SAMPLE_WORDS` is **150** and `run._MIN_VOICE_SAMPLE_WORDS` is
**20**. I asserted the runner's floor must be at least the voice module's — two constants guarding
one idea — and it failed by a factor of seven.

The assertion was wrong. They answer different questions: 20 is *"below this the distance is
meaningless, do not compute"*, 150 is *"below this the profile is noisy, say so"*. Both are
defensible and the gap between them is deliberate.

What matters is what happens **inside** the gap, and that is now tested: a 20-to-149-word sample is
scored, so the user must be told it is thin. `voice_distance` calls `_warn_if_sample_is_thin`, which
is the only thing making the pair safe, and nothing checked that it does.

Two further slips, both mine and both caught by the tests failing: the runner's own guard survived
its first test because I exercised `voice_distance` directly and never took the runner's path; and
the tells caveat lives under `warning`, not `caveats` — the sixth wrong return-shape guess this
session, and the second in three rounds.

## What "verify before acting" costs and saves

An hour of machine time against thirty tests, three of which would have been written for code that
is already covered. That is a poor trade on the arithmetic alone — three tests is not an hour — and
a good one on everything else: the 90% figure is what makes the remaining 27 worth acting on without
re-checking each one, and a register nobody trusts gets read once and ignored.

---

# Round one hundred — boundary testing does not scale by hand, which is a different claim

Round ninety-nine concluded that the n−1/n/n+1 discipline "cannot be applied 206 times". That is
true of doing it by hand and false of the part that actually matters: **`x < THRESHOLD` has exactly
one boundary and it is written in the source.** Finding them is mechanical; only writing the cases
is not.

`eval/boundaries.py` enumerates every comparison in `untell/` against a named numeric module
constant and cross-references the boundary mutation sweep. Round ninety-eight found **8** thresholds
by grepping for names I thought of. The register finds **48**.

| | |
|---|---|
MEASURED, `python -m eval.boundaries`:

| boundaries against a named threshold | 48 |
|---|---|
| off-by-one caught | 18 |
| **off-by-one survives** | **30** |
| protected share | **37.5%** |

The unprotected are concentrated where the rewriter and the scoring path meet: `scripts/score.py`
carries 7, `scripts/tells.py` 5, `rewriter/structural.py` 3.

## ✗✗ The sweep was under-reporting the suite, and the cause is a heuristic aimed at exactly these tests

The register's first run said **7 protected of 48**. Round ninety-eight had verified seven
off-by-ones as killed only two rounds earlier, and every one of them came back "unprotected".

`test_index` ranks a module's tests by **breadth** — how few `untell` modules a test file imports —
on the reasoning that a test importing one module is about that module and one importing twelve is
an integration test. **A boundary test breaks that reasoning.** It imports the threshold constant
*and* the callers that compare against it, so it looks broad, ranks last, and the cap drops it.
`test_a_threshold_switches_exactly_where_it_says.py` imports five modules and was selected for none
of them.

So the selection now always includes test files naming the module's **threshold** constants — those
appearing in an ordering comparison, which is what distinguishes a boundary test from one that
happens to import a size cap. MEASURED, same 339 mutants and the same tests, only the selection
changed:

| | boundary kills | score |
|---|---|---|
| breadth ranking alone | 64 | **18.9%** |
| plus threshold-naming tests | 86 | **25.4%** |

**Twenty-two kills recovered from tests that were already written.** Every mutation figure in rounds
ninety-three to ninety-nine understated this suite, on top of the bytecode defect round ninety-five
found — and both errors ran in the same direction, because a harness that fails to reach a test and
a harness that fails to load a mutation both report a survivor.

⚠️ **Two intermediate versions of the fix were wrong**, and the way they were wrong is worth keeping.
Including any test that names any module constant took `untell.scripts.score` from 5 selected files
to **35** (MEASURED), which would have made the sweep unusable. Ranking those by how many constants they name
put the dedicated boundary test outside the top three for three of the four modules it covers,
because a size cap counts the same as a threshold. Only restricting to constants that appear in an
ordering comparison — the module's actual thresholds — put it inside for all five.

It is still a heuristic and the docstring says so: `untell.scripts.score` needed five slots rather
than three, and five is a round number rather than the number that made one file pass. A module
whose boundary test falls outside it will under-report its own coverage, and this register is where
that shows.

## ✗ And a register is only as current as its sweep

The first version read a sweep taken before round ninety-eight's tests existed. Every number it
printed was wrong in the **alarming** direction, which is the one that wastes the most work — it
would have sent someone to re-fix seven boundaries that were already fixed.

`sweep_is_stale` compares modification times and the report leads with the warning rather than
trusting whoever runs it to re-sweep first. Verified against a real file with a bumped mtime, not
asserted.

## What the arc from ninety-seven to one hundred establishes

| round | claim |
|---|---|
| 97 | the suite catches inversions and misses off-by-ones, 55–0 |
| 98 | so the thresholds are unprotected — 7 of 8, all now fixed |
| 99 | property tests scale and are structurally boundary-blind |
| **100** | **but finding the boundaries is mechanical — MEASURED, 48 of them, not 8, and 30 remain** |

Round ninety-nine's rule stands with one word changed. *Write the property test for coverage, and
add explicit n−1/n/n+1 cases at every threshold a person can meet* — and the list of thresholds is
**generated, not remembered**.

---

# Round ninety-nine — the leverage, and the bias reproducing in tests written to avoid it

Round ninety-eight closed eight named threshold sites by hand. The paired sweep found **206 sites
where both mutants survived** — comparisons no test reaches at all — so hand-fixing is not the
shape of the answer. This round looks for structure instead.

## Where the 206 are

They are not spread evenly:

| file | untested comparison sites |
|---|---|
| `rewriter/structural.py` | 46 |
| `scripts/run.py` | 22 |
| `attacks/word_importance.py` | 20 |
| `scripts/score.py` | 20 |
| `scripts/tells.py` | 17 |

And the single largest concentration in one function is **14 in
`word_importance._tell_probe_words`** — a performance optimisation whose forty-line docstring
argues one property:

> *"It returns a SUPERSET of every word whose probe could report a positive gain, so skipping the
> rest never changes a ranking decision."*

**That claim is checkable and nothing checked it.** If the probe set ever omits a word whose
substitution really does change the tells count, the ranking silently changes and the only symptom
is a worse rewrite. So rather than fourteen branch tests, one property test: substitute every word's
first occurrence, recount, and require any word that moved the count to be in the set.

## ✗ The leverage is real and much smaller than hoped

MEASURED, the new property test against every previously-surviving mutant in that function:
**6 of 28 killed.** One test file for six mutants is better than six hand-written branch tests, and
it stays true if the branches are rewritten — but twenty-two survive, because a property test over a
realistic corpus exercises branches at *typical* values and most of these need a specific document
shape to reach at all.

One of the six needed the corpus extended: the trigram branch — which the docstring calls "the
strongest signal in the catalogue" — requires a document of **at least 60 words with at least 5% of
them inside a repeated trigram**, and the sample written for repeated phrasing was 53 words. It
looked like it exercised the category and did not.

## ✅ And the finding inside the six

Of the six mutants killed, **five are inversions and one is an off-by-one.** Comparison mutants died
at 5 of 14 sites; boundary mutants at 1 of 14.

That is round ninety-seven's ordering reproducing **inside a test written two rounds later by an
author who knew about it and was deliberately building a property rather than branch assertions.**
The bias is not carelessness and cannot be fixed by intending to do better.

The mechanism is now clear. A property test asserts something true of every input and is exercised
on the inputs a corpus happens to contain — realistic documents, at typical lengths, away from every
boundary. Catching an off-by-one requires a case constructed **at** the boundary, which is a
different act of authorship, not a more careful version of the same one.

## What the two techniques are for

| | catches | scales to 206 sites |
|---|---|---|
| property test over a corpus | logic errors, inverted branches, contract violations | yes |
| n−1 / n / n+1 at a named threshold | off-by-ones | no |

**They are complementary and neither substitutes for the other.** Round ninety-eight's discipline is
the only thing that caught the seven threshold off-by-ones, and it cannot be applied 206 times.
Property tests scale and are structurally blind to boundaries.

The practical rule this leaves: **write the property test for coverage, and add explicit n−1/n/n+1
cases at every threshold a person can meet.** The second list is short — round ninety-eight found
eight — and it is the list that would otherwise never be reached.

---

# Round ninety-eight — the prediction, and the seven thresholds it was right about

Round ninety-seven ended with a measured property of this test suite rather than a score: over 339
comparison sites, of the 55 pairs where the tests distinguish a branch **inversion** from an
**off-by-one**, the inversion is caught and the off-by-one missed at every one — 55 to 0. The suite
tests that branches do the right thing and not that they switch in the right place.

That is a prediction, and the place it should bite first is the thresholds a person actually meets.

## ✅ Confirmed, 7 of 8

MEASURED against the paired sweep, the comparisons guarding this repository's documented thresholds:

| site | off-by-one | inversion |
|---|---|---|
| `score.py:732` `words >= _MIN_WORDS_FOR_A_VERDICT` | survives | killed |
| `score.py:705` `words < _MIN_WORDS_FOR_A_VERDICT or …` | survives | survives |
| `tells.py:723` `< _MIN_WORDS_FOR_REPETITION` (trigrams) | survives | survives |
| `tells.py:853` `< _MIN_WORDS_FOR_REPETITION` (openers) | survives | survives |
| `perplexity_burstiness.py:330` `< _MIN_WORDS_FOR_SIGNAL` | survives | killed |
| `perplexity_burstiness.py:632` the same floor in `.score()` | survives | killed |
| `humanness.py:426` `< _MIN_WORDS_FOR_A_BAND` | survives | survives |
| `sentences.py:163` `< _MIN_SENTENCES_FOR_SPREAD` | **killed** | killed |

Seven of eight, and four with **nothing testing either branch**. These are not internal details.
`_MIN_WORDS_FOR_A_VERDICT` decides whether a person is told their text is too short to judge, and
the warning quotes the 40-word figure — so an off-by-one there is the tool disagreeing with its own
documentation about the document in front of the reader.

Each threshold is now asserted at **n−1, n and n+1**. Two points would leave the switch free to sit
on either side of the gap; three pin it. **MEASURED: 7 of 7 previously-surviving off-by-ones now
killed**, verified by re-applying each mutant against only the new test file.

## ✗ The first attempt killed 4 of 7, and the reason is the round's own subject

Three survived the first pass:

* `tells.py:853` — the sample was built at `floor - 1` and `floor + 6`. **`< floor` and `<= floor`
  differ on exactly one input, the floor itself, and neither sample was it.** I wrote a boundary
  test that did not touch the boundary, in the round about a suite that does not touch boundaries.
* `tells.py:723` — a second function behind the same constant, which the opener test never calls.
  One threshold, two call sites, and testing one says nothing about the other.
* `perplexity_burstiness.py:632` — `_MIN_WORDS_FOR_SIGNAL` guarded a **second time** inside
  `PerplexityBurstinessDetector.score`. The function-level mutant died to the new test while the
  method-level one lived, which is the clearest possible demonstration that two copies of a
  threshold are two chances to get it wrong.

The samples are exact now (`_repeated_openers(n)` returns exactly `n` words, asserted before use),
both call sites are covered, and the detector object is tested alongside the bare function with an
assertion that the two agree.

## ✗ And a fourth wrong return-shape guess

The first draft asserted `score_sentences(...)["spread"]`. There is no `spread` key — the threshold
guards `_targeting_is_unrankable`, and the observable key is `unrankable`. The humanness test looked
for the word "band" in a caveat that says "does not separate the classes" instead.

Neither was a defect in the code; both were assertions written from the constant's *name* rather
than from the function. That is the fourth time this session a guessed return shape has cost a run,
which is what `docs/result-shapes.md` exists for and did not prevent, because the trap is not
knowing the document — it is reaching for the plausible key without opening the file.

## What the round is worth

The seven kills close the specific gap. The transferable part is that **round ninety-seven's
statistical finding made a concrete prediction about eight named lines, and seven of them held** —
which is what turns "the mutation score is 46%" from a number into a diagnosis. A property of the
suite, measured once, told me where to look.

---

# Round ninety-seven — the mutation operators were an unchosen parameter too

Rounds eighty-six and eighty-seven established the shape: a tool's own unchosen parameter decides
its answer, and the value nobody picked deliberately is usually the flattering one. Rounds
ninety-three to ninety-six built a mutation harness and published three scores from it.

**That harness has exactly three mutation operators — comparison, arithmetic, extremum — and nobody
chose that set.** It was enough to produce a number. Whether it reaches the failure modes that
matter is a different question, and only a wider set can answer it.

Five were added: **boundary** (`<` → `<=`, the off-by-one, as opposed to `<` → `>=`, which inverts
the branch), **boolean** (`and` ↔ `or`), **membership** (`in` ↔ `not in`), **identity**
(`is` ↔ `is not`) and **constant** (`True` ↔ `False`). Candidate mutants across the package go from
**1,397 to 3,313**.

## ✗ The three I picked are the three easiest

MEASURED, 355 mutants across 56 modules, evenly sampled per module:

| operator | killed | survived | score | in the original three? |
|---|---|---|---|---|
| boundary | 9 | 27 | **25.0%** | no |
| constant | 24 | 56 | **30.0%** | no |
| boolean | 26 | 28 | 48.1% | no |
| identity | 20 | 21 | 48.8% | no |
| membership | 23 | 22 | 51.1% | no |
| comparison | 21 | 14 | **60.0%** | yes |
| arithmetic | 32 | 18 | **64.0%** | yes |
| extremum | 9 | 5 | **64.3%** | yes |

**Every operator I had implemented scores above every operator I had not.** Split that way, MEASURED
over the same 355 mutants: the original three kill **62.6%**, the five added kill **39.8%**, and the
package score falls from **58.3%** to **46.2%**.

So round ninety-four's headline was flattered by roughly twelve points, not by any error in the
measurement but by which mutations the tool happened to know how to make. That is round
eighty-six's finding about the survey's proximity window, one level up and pointing at my own
instrument rather than at the repository's.

## The finding underneath the ranking

`boundary` at 25% is the sharpest row, and it is not just "another operator". It mutates **the same
comparison sites** as `comparison` does — the only difference is whether the branch is inverted or
shifted by one.

An inverted branch is caught by any test that exercises either side. An off-by-one changes behaviour
on **exactly one input**, so it is caught only by a test sitting on the boundary. The gap between
60.0% and 25.0% is therefore a statement about the character of this test suite: **it tests that
branches do the right thing and not that they switch in the right place.**

⚠️ **The cross-operator table is sampled, and that weakens the comparison.** `--limit` spaces mutants
evenly through each module, so a site's two mutants are not guaranteed to both have been run — which
means a survivor whose partner is absent cannot be told from one whose partner was killed. So the
ranking was re-run as a `--kinds comparison,boundary` sweep with **no sampling**, giving every site
both mutants.

## ✅ The paired result, and it is stronger than the ranking

MEASURED over **339 comparison sites, both mutants run at every one**:

| | sites |
|---|---|
| both killed | 78 |
| both survived | 206 |
| **inversion killed, off-by-one survived** | **55** |
| off-by-one killed, inversion survived | **0** |

**Of the 55 sites where this suite distinguishes between the two mutations, it catches the inversion
and misses the off-by-one at every single one.** Not a tendency — a total ordering, with zero
exceptions in 339 sites. Exact binomial two-sided p = 5.6 × 10⁻¹⁷.

Mechanically that is what should happen: any test exercising a comparison catches an inversion,
because the branch goes the wrong way for most inputs, while catching an off-by-one needs a test
sitting exactly on the boundary. Killing the off-by-one therefore *implies* killing the inversion.
What the data adds is that the implication holds here without a single exception, which makes
`boundary` a strictly sharper instrument than `comparison` and the older operator strictly
redundant beside it.

## ✗ And the unsampled run corrects the sampled table

The same two operators, measured without `--limit`:

| operator | sampled (355 mutants) | **unsampled (678 mutants)** |
|---|---|---|
| comparison | 60.0% | **35.4%** |
| boundary | 25.0% | **18.9%** |

Both are honest measurements of different populations, and the difference is a property of
`--limit` that I had not stated: **capping mutants per module weights every module equally, while an
uncapped run weights them by size.** The sampled run gave a small, well-tested module the same eight
mutants as `scripts/run.py`, so the well-tested modules were over-represented and the score came out
high. For "how many of this repository's comparison sites are actually protected", the uncapped
figure is the right one: **35.4% and 18.9%.**

The ordering the round rests on is unaffected — every added operator still scores below every
original one, and the paired result is unsampled by construction. What moves is the level.

## What this says about the previous four rounds

Nothing in rounds ninety-three to ninety-six was wrong. Every kill was real, the bytecode defect was
real and one-directional, the cache audit stands. **What was wrong was treating a mutation score as
a property of the test suite when it is a property of the suite and the operator set together** —
and reporting it without saying which operators produced it.

The scores now carry their operator set. The number to act on remains the enumerated survivor list,
which just grew by every off-by-one and boolean flip the first three operators could not express.

---

# Round ninety-six — every other cache, checked for the same defect

Round ninety-five lost a measurement to an incomplete cache key. The lesson generalises past the one
that bit: **a key that omits something the value depends on returns a plausible wrong answer**, and
plausible is the whole problem — the mutation score came out 3.7 points low and nothing about the
output looked wrong.

This repository already has a scar from the same shape in shipped code. `untell/scripts/score.py`
carries a comment about a score cached under one torch mode being read by an env-pinned test under
another: **56 assertions failed in one full-suite run** before the scoring mode went into the key.
Two instances is a pattern. So `eval/cache_keys.py` checks all of them.

## The audit

MEASURED: **6 cached functions** across `untell/` and `eval/`. Five are pure over their arguments
once one level of indirection is followed — `_pair_probs` reads nothing itself but calls `_load`,
which returns a model loaded once per process and immutable thereafter.

**One has a genuinely incomplete key.** `human_base_rates()` takes **no arguments at all** and reads
`eval/data/tell_base_rates.json`. An empty key for a file-dependent value is the textbook case.

It is **accepted rather than fixed**, and the reason is not the reasoning. The file is a committed
artefact that changes only when the code reading it changes, so within a process there is nothing
for a key to distinguish — but that argument would have been just as available for the bytecode
cache, and it would have been wrong. What makes it safe is the second check.

## The check the audit cannot replace

`human_base_rates` is varied by exactly one test, which calls `cache_clear()` before the patch and
again after. That works, and **nothing made it work.** A test that patches and forgets reads the
previous value, and because an `lru_cache` outlives the test it poisons every later test in the
process — which is precisely the 56-failure incident, one layer up.

So `tests_that_patch_behind_a_cache` fails when a test patches a name a cached function reads and
never mentions `cache_clear`. Verified against a probe test rather than asserted: the probe is
flagged, and removing it returns the count to zero.

## ✗ And the first version of that check was wrong on its only finding

It flagged any patch of a *module* owning a cached function. Its one hit was
`tests/test_detectors.py` patching `untell.scripts.tells.score_tells` — which `human_base_rates`
does not read.

I had written the coarse rule down as deliberate, with a justification: *"coarse is right here — the
cost of a false alarm is one added line."* That reasoning is wrong, and it is wrong in a way this
ledger has recorded three times now. **The line a false alarm prompts is a `cache_clear()` that
clears nothing**, which is cargo cult, and the repository's own note on the subject is that false
alarms are how a checker gets ignored. The rule now matches against the names a cached function
actually references, directly or through a helper in the same module.

Writing a justification for a design decision and having the justification be wrong is a different
failure from not thinking about it. The comment made the rule look considered, which is worse than
leaving it obviously provisional.

## What the two checks are between them

| | catches |
|---|---|
| key completeness | a cache that *can* return a stale value |
| patched-without-clearing | a test that *makes* it |

Neither is sufficient. The first would have accepted `human_base_rates` on its own reasoning; the
second only fires once somebody writes the test that would break. Together they are a ratchet: the
incomplete key is allowed, named, and guarded, and the guard fails before the poison spreads.

---

# Round ninety-five — acting on the survivor list, and proving each kill

Round ninety-four ended by saying the number to act on is not the mutation score but the enumerated
survivor list. **A list nobody acts on is the defect rounds ninety-one and ninety-two kept finding**:
work performed once, recorded, and then not done. So this round acts on it — and, because a test
that looks like it closes a gap is worth nothing unless it does, each new test is verified against
the specific mutant it is meant to kill.

## Two modules closed, six survivors, every kill demonstrated

`untell/languages.py` — `dominant_script`, which decides `catalogue_for`, which decides **which tell
catalogue a document is scored against**:

| survivor | what it meant |
|---|---|
| `max(counts…)` → `min` | the function returns the RAREST script, not the dominant one |
| `counts.get(name, 0) + 1` → `- 1` | the script tally counts downward |
| `counts.get("Latin", 0) + 1` → `- 1` | the same for the Latin branch |

The first is the one worth pausing on. The function is *called* `dominant_script`, its docstring
promises that "an English paragraph quoting one Chinese phrase stays Latin", and **nothing tested
that it picks the majority script over a minority one.** Inverting the entire purpose of the
function left the suite green.

`untell/html_report.py` — the artefact a person actually reads when deciding whether an accusation
is fair:

| survivor | what it meant |
|---|---|
| `if prev < len(text)` → `>=` | **every character after the last locked span is dropped from the report** |
| `if start < prev` → `>=` | the overlap guard fires on adjacent spans too, losing the second |
| `round(100.0 - pct, 1)` → `+` | the score bar's overlay is wider than the bar |

MEASURED, each mutant re-applied in a worktree with only the new test file present: **6 of 6
killed**, from a clean baseline of 0 failures. The verification matters more than the tests. A test
written while looking at a mutant tends to assert the thing the mutant does not change, and the only
way to know is to introduce it again.

## ✗ And two of my own assertions were wrong before the code was

The first run of the new tests failed twice, both times because **I had guessed instead of
measuring**: I asserted the Han document would report script `Cjk` (it reports `Han`), and I guessed
a crossover point for a two-script document without counting the letters. MEASURED, `LATIN` carries
67 letters and `CYRILLIC` 69, so a single copy of each already tips Cyrillic — the crossover I had
assumed sat elsewhere.

Neither was a defect in the code. Both were a test asserting a number nobody had checked, in a round
whose subject is tests that do not check anything, written immediately after two rounds about
guessing instead of measuring. The comment beside the loop now states the letter counts rather than
implying a threshold.

## The conservation property, which is stronger than any mutant

The `html_report` tests do not only pin the three survivors. They assert that **the rendered report
contains every character of the input**, across six span layouts — empty, leading, trailing,
whole-document, disjoint, and boundary. That property is stronger than the mutants that motivated
it, and it is what a reader is entitled to assume of a document shown to them as evidence.

Writing to the mutant alone produces tests shaped like the mutation operator, which is how a
mutation score is gamed. Writing to the property the mutant violated is what makes the exercise
worth doing.

## ✗✗ And then the verification caught the harness itself

The third module, `untell/rich_output.py`, is where it went wrong. Its survivor at line 104 is
`length = stop - start` inside `_unified_range` — a function whose docstring promises output
*"identical to what `difflib.unified_diff` would print"*. So the test compares it directly against
`difflib._format_range_unified` over nine ranges, and MEASURED, the mutant differs on **five of the
nine**. It cannot survive that test.

The harness reported it as **surviving**.

**CPython invalidates a `.pyc` on `(mtime, size)`.** Every mutation this tool makes is a
single-character swap — `-` for `+`, `<` for `>=` — so the source file's size is unchanged, and a
write landing inside the same mtime second leaves the cached bytecode valid. The mutated source is
never loaded. The tests pass. The mutant is recorded as a survivor.

Re-run in a fresh worktree, the same mutant failed **7 tests**.

**The bias is one-directional, which is the only reassuring part.** Stale bytecode runs the
*unmutated* code, so a mutant can only ever be wrongly recorded as surviving, never as killed. Every
reported kill in rounds ninety-three to ninety-five is trustworthy. Every mutation score was an
under-estimate and every survivor list an over-count.

MEASURED after disabling bytecode (`-B`, `PYTHONDONTWRITEBYTECODE`, and a purge of any
`__pycache__` the checkout inherits):

| measurement | as published | corrected |
|---|---|---|
| round ninety-three, 2 modules, 97 mutants | 46.4% | **46.4%** — unchanged |
| round ninety-four, 56 modules, 108 mutants | 54.6% | **58.3%** |

**Round ninety-three was unaffected and round ninety-four was not, which explains the mechanism.**
The hazard needs two writes inside one mtime second. Round ninety-three's two modules have slow test
selections, so its mutants were seconds apart; round ninety-four swept many small modules with fast
tests, and rapid successive writes collided. **The bug bites hardest exactly where mutation testing
is cheap enough to do at scale** — which is where anybody would want to run it.

It also explains something round ninety-five nearly published: `rich_output.py:425` still survives
after the fix, correctly, because the new test covers `humanize_diff` and not the `tells_delta` line
in `print_humanize_result`. Two of three closed, one honestly open.

## Running all of them, not a third of them

Round ninety-four sampled 3 mutants per module — 108 of 1,397 candidates — because the serial run
would have taken about four hours. That was the right call for an estimate of the score and the
wrong one for the list: **a sampled survivor list names some of the uncovered lines and gives no way
to tell which it missed.**

`run_parallel` spreads the sweep across several worktrees, dealing modules round-robin so one slow
module does not leave a worker holding the tail. On this four-core machine that is the difference
between an afternoon and an hour, which is the difference between a measurement somebody reruns and
one they quote.

---

# Round ninety-four — the same question, across the whole package

Round ninety-three mutation-tested two modules against test selections written by hand. That is the
reflex rounds eighty-nine and ninety already caught once: **pick the thing that looks important and
measure it.** A hand-written map does not reach 65 modules, and a mutation score covering only the
files somebody remembered is the selection bias this repository keeps finding in everything else it
audits.

`discovered_targets()` derives the pairing instead. A test file's imports say which modules it
touches, and its **breadth** says how much it is about any one of them: a test importing one
`untell` module is about that module, one importing twelve is an integration test that happens to
touch it. So a module's tests are ranked by fewest imports first and capped, which spends a small
budget on the tests most likely to notice.

MEASURED across **56 measurable modules** — 58 paired automatically, 2 skipped:

| | |
|---|---|
| mutants introduced | 108 |
| killed | 59 |
| **survived** | **49** |
| **mutation score** | **54.6%** |

> ⚠️ **54.6% is an under-estimate; the figure is 58.3%.** Round ninety-five found that CPython's
> bytecode cache was masking some mutations entirely — every mutation here is a single-character
> swap, so the file size is unchanged, and a write landing in the same mtime second leaves the stale
> `.pyc` valid. Re-run with bytecode disabled, the same 108 mutants give **63 killed, 45 survived,
> 58.3%**. The bias is one-directional: stale bytecode runs the unmutated code, so it can only ever
> manufacture survivors. Corrected in round ninety-five; this entry is annotated rather than edited.

Round ninety-three's two hand-picked modules scored 46.4% against hand-written selections. The
package as a whole, against selections nobody chose, scores **54.6%** as first MEASURED and
**58.3%** once round ninety-five's bytecode-cache defect is fixed — either way close enough to the
hand-picked pair that it was not unrepresentative, which is worth knowing since it was the evidence
for the claim at the time.

The survivors are spread rather than concentrated: `api_server.py`, `html_report.py`,
`languages.py`, `rewriter/local_policy.py`, `rich_output.py` and `scripts/run.py` each carry three,
and the list names file and line for every one.

## ✗ And the first full-package run was wrong, in exactly the way round ninety warned about

The first run reported **50.0%**. It was corrupted, and the mechanism is one this ledger has already
written down.

`_failures()` returned **10,000** when a test selection timed out or died before reporting. As a
*baseline* that is catastrophic: no mutant can ever exceed 10,000, so **every mutant for that module
is scored a survivor** — silently, and indistinguishably from a genuinely uncovered line. MEASURED:
3 of 58 modules timed out at baseline and contributed up to 9 spurious survivors.

This is round ninety's finding verbatim — *a zero meaning "could not test" and a zero meaning "does
not matter" are the same number and opposite facts* — committed in a harness written **two rounds
after** the round that established it, by the same author, in code whose subject is checks that
cannot fail. Round ninety-three made the same class of error twice in one afternoon. Knowing the
lesson is not the same as applying it, and this ledger now has three consecutive rounds of evidence
for that.

The sentinel is negative now, so a module whose baseline is unusable is **skipped and listed**
rather than scored. With a longer timeout only two modules remain unmeasurable —
`fast_detectgpt.py` and `hc3_roberta.py`, whose tests genuinely cannot run without `torch`, which is
absent by organization policy — and the corrected score is 54.6%.

## ⚠️ Nine modules have a red baseline and are still measured

`back_translation.py` starts at 6 failures, `mage.py` at 6, `local_policy.py` at 2, and six others at
1–2. A red baseline is a **higher floor, not a reason to stop**: a mutant counts as killed when it
adds a failure to what was already failing. Distinguishing that case from the unusable one is the
whole content of the fix — one is a floor, the other is an absence of information.

## What is and is not claimed

54.6% is measured against selections capped at five test files per module. It is therefore a
**lower bound**: round ninety-three established, on a sample, that 40% [17%, 69%] of survivors die
when re-run against a much wider selection. The number to act on is not the percentage but the
enumerated list of file-and-line survivors in `eval/data/mutation_package.json`, each one a place
this code could be wrong today with its tests green.

---

# Round ninety-three — if the detector were wrong, would anything fail?

Rounds ninety-one and ninety-two found the same defect twice: a verification performed once by a
person, recorded in prose, and therefore not performed again when the thing it covered changed. Both
were fixed by making the verification executable.

**A test that cannot fail is that same defect written in code.** It runs in CI, it is green, and it
guards nothing — and green is the one property it shares with every test that works. This repository
has more than ten thousand tests and exactly one family of them, the audit checks in
`tests/test_every_audit_check_can_fail.py`, has ever been shown able to fail. Round sixty-two is the
warning: a fix there recreated a documented vacuity, caught only because somebody re-ran the negative
case by hand.

So: break the detector on purpose. `eval/mutation.py` makes single-token edits to a shipped module —
a comparison flipped, an operand swapped, `max` for `min` — and runs the tests named for it.

## The score

MEASURED over the two core scoring modules, both baselines clean (0 failures unmutated):

| | |
|---|---|
| mutants introduced | 97 |
| killed | 45 |
| **survived** | **52** |
| **mutation score** | **46.4%** |

**More than half the single-token ways of breaking the detector go unnoticed by the tests named for
it.** The survivors cluster in `_repetition_signal` and `_single_sentence_signal` — which
independently corroborates round seventy-eight, where the `rep` component was found never to fire on
the eval corpus at all. Two routes, one conclusion: that branch is the least exercised code in the
detector.

## ⚠️ That is against a named selection, and the whole suite does better

A mutation score is a property of the test selection as much as of the code, so quoting 46.4% alone
would overstate the case. A sample of 10 survivors re-run against a **1,543-test** selection:

| | |
|---|---|
| killed by the wider suite | 4 |
| **still surviving 1,543 tests** (MEASURED, n = 10) | **6** |
| wider-suite kill rate among survivors | 40%, Wilson [17%, 69%] |

So the suite as a whole catches meaningfully more than 46.4% — and six of ten sampled survivors are
uncaught by 1,543 tests, which is the half of the result that is not reassuring. Both figures are
published because either alone misleads, in opposite directions.

## ✗✗ Two defects in my own harness, and the second nearly published a false result

**Kill detection read an exit code.** An exit code answers "did anything fail", which is the wrong
question wherever the baseline is already red — and it is red here, `torch` being absent and
`huggingface.co` blocked at the egress proxy by organization policy, so a broad selection starts at
7 failures. `_failures()` counts instead, and the baseline is reported rather than assumed. That
guard earned itself immediately: the first run flagged `untell/humanness.py`'s selection as failing
unmutated, so every mutant against it had been scored killed for the wrong reason.

**The follow-up compared pytest's summary line, which contains the elapsed time.** So every mutant
"differed from baseline" and the wider-suite check reported **10 of 10 killed**. MEASURED correctly,
by counting failures instead, the answer is **4 of 10**. It was caught by reading the output rather than the conclusion — the rows showed
`7 failed, 1543 passed` on both sides and differed only in `102.70s` against `107.37s`.

That second one is worth dwelling on. It is the round-eighty-eight defect exactly — a comparison
against the wrong field producing a plausible number — and it arrived **in the round whose entire
subject is checks that cannot fail**, in code written to detect precisely that. A tool for finding
vacuous verification is not itself immune to being vacuous, and nothing about having just written
the docstring on the subject helped.

## What the number is for

46.4% is not a target to optimise. A mutation score can be driven to 100% by tests that pin
arithmetic nobody cares about, which is how the measure becomes the goal. What the survivor list is
for is naming **specific lines where the detector could be wrong today with every test green**, and
those are now enumerated with file and line in `eval/data/mutation.json` rather than summarised.

The ratchet is on the score not collapsing, not on it rising. A test that used to catch a broken
detector and no longer does is a regression; a survivor nobody has got to yet is a backlog item.

---

# Round ninety-two — the same question, asked about other people's papers

Rounds eighty-six to ninety-one audited this repository's claims about itself: its survey
parameters, its constants, its headline figures against the tools that produce them. Its claims
about **other people's work** had only ever had an advisory checker — `--cross-check`, described in
its own docstring as "a REVIEW TOOL, not a pass/fail check".

Round ninety-one's thesis applies directly and the stakes are higher. Getting our own number wrong
is embarrassing. **Attributing a number to a paper that does not contain it is a claim about
somebody else's work**, and it is the one class of error here that would damage a third party.

## The triage

MEASURED: 33 findings after two checker fixes, every one read. **None is a misattribution.** They
fall into six groups, each legitimate for a different reason:

| finding | why it is not a misattribution |
|---|---|
| `research-to-build.md` / ICNALE bias study, ×12 | our own `--by-length` measurements; the command that produced them is named two lines above |
| `ROADMAP.md` / Beemo, ×6 | credited to a different author by name in the same sentence — "Karr et al. put light edits at 64–80% for Pangram" |
| `ROADMAP.md` / Liang et al., ×6 | our own README figures with their Wilson intervals, in a row about our interval discipline |
| `research-verification.md` / MASH, ×6 | the ledger entry that **describes an earlier defect of this very checker** and quotes its example figures |
| `research-verification.md` / SenDetEX, ×2 | our own re-measured figures, in a parenthetical that says so |
| `ROADMAP.md` / resume corpus, ×1 | marked "(derived, see note)" at the point of use, with the arithmetic shown below |

The last of those is worth naming as good practice rather than as noise: a derived figure that says
it is derived, beside the paper's own numbers it was derived from, is exactly what a citation should
look like when it is not a direct quote.

## ✗ The defect was not in any of them. It was that reading them did not stay read.

An earlier round found this tool reporting 35 findings, fixed two checker defects to bring it to 25,
**read all 25**, established that none was a misattribution, and recorded that conclusion in prose.

It reports 35 today. The fixes held — the documents grew, including this round's predecessors. And
because the triage lived in a sentence, **nothing could tell a new finding from one already
cleared.** The honest options were to re-read all 35 or to trust a sentence about a different 25,
and the count had drifted by ten without anyone noticing which ten.

`eval/data/citation_triage.json` records a reason per finding, keyed on document, paper and figure
rather than on a line number — a line-keyed baseline goes stale the first time a paragraph is
inserted above it. `python -m eval.litreview --untriaged` reports only what is new and exits
non-zero when there is any. Reading a finding once is now permanent, which is what turns a review
tool into something that can gate a commit.

**The entries are not a silencing mechanism and the format enforces it**: a test rejects any cleared
finding whose reason is shorter than a sentence, and the file's own `how_to_add` field says never to
add an entry for a finding you have not read.

## ✅ And two checker fixes, worth 2 of the 35

* **A cross-reference to one of our own rows is not a figure.** "row 28 was blocked" produced a
  finding against a paper containing no 28 — true and meaningless.
* **Digits inside an identifier are not a measurement.** The `2` in `H2L` was reported as an
  unsupported figure.

Both are the same shape as the two defects the earlier round fixed, and the same shape as round
ninety-one's proximity failure: a checker that matches the wrong thing produces findings that are
individually true and collectively useless. This repository's own note on it — *"a checker that
cannot recognise the most common form of the thing it looks for produces false alarms, and false
alarms are how a checker gets ignored"* — has now been cited in three consecutive rounds about three
different checkers.

## What the round is an instance of

Round ninety-one made a manual verification durable by pinning figures to artefact keys. This one
does the same for a manual *reading*. The pattern is identical and so is the failure it prevents:
**work done once by a person, recorded in prose, and therefore not done at all the next time the
documents change.**

---

# Round ninety-one — attribution is not agreement

`untell-audit` enforces that every bolded figure in these documents carries a stated provenance.
MEASURED at this round: **1,045 claims pass it, 0 do not.** It is a real guard and it has caught real
defects, and it is strictly weaker than it sounds.

**Naming a source and agreeing with it are different properties.** Round eighty-four is the proof: a
published AUROC of **0.3538** carried a reproduction command that printed **0.3529**. The claim was
attributed. The attribution named the right tool. The number was still not the one the tool produced.
That was found by reading, one figure at a time, and nothing would have found the next one.

## ✗ The obvious way to mechanise it does not work, and the failure is structural

The first design linked a figure to an artefact by proximity: if the prose near a number names a
tool, the number should appear in that tool's committed output. Nine artefacts are committed, so the
mapping seemed free.

MEASURED, it reported **15 contradictions of which every single one was false**, and narrowing the
scope three times did not help:

| scope | contradictions | true |
|---|---|---|
| 900-character window | 15 | 0 |
| blank-line paragraph | 15 | 0 |
| markdown table row / list item | 15 | 0 |

Each narrowing fixed a real defect in the scoping — a `ROADMAP.md` status table has no blank lines,
so one "paragraph" was seventy rows and every row borrowed every tool named in the table — and the
count did not move, because **the premise is untrue.** A sentence may legitimately name a tool and
quote a figure from somewhere else. `ROADMAP.md` row 33 names the corpus tool and quotes 6,810, the
pre-LLM corpus size, which that tool does not report. There is no window small enough to fix a rule
that is false.

It is recorded rather than deleted so the next person to have this idea finds it already tried. The
version that ships took the opposite direction.

## ✅ An explicit registry instead

`eval/claim_verification.py` names the artefact key behind each headline figure and checks that the
documents still agree with it. **19 registered figures, 19 verified, 0 drifted.** No false positives
are possible, because nothing is inferred; the cost is that coverage is what somebody registered
rather than every figure in the repository.

For a check that gates a commit that is the right trade, and this repository already wrote down why:
*"a checker that cannot recognise the most common form of the thing it looks for produces false
alarms, and false alarms are how a checker gets ignored."*

## ✗ And the gap it found on the way

The repository's most-quoted numbers, all MEASURED by `eval/detection_power.py` — **10.7%** of
machine abstracts flagged, **30.4%** of human ones, **AUROC 0.3529** — had **no committed artefact
at all.** Eight artefacts covered the survey,
both filter sweeps, the register work and the constant audit; the headline itself was the one set of
figures with nothing machine-readable behind it, and so the one set this check could not have
verified. `eval/data/detection_power.json` is committed now.

## ⚠️ This check found nothing today, and that is what it is for

19 of 19 passed on the first run. The registry was written from the current values, so of course it
did. **Its value is entirely prospective**, which makes proving it can fail the only part that
matters. All three failure modes are exercised as tests and all three exit non-zero:

| mode | what it catches |
|---|---|
| artefact moves, prose does not | round eighty-four's defect, mechanised |
| prose loses the figure | a rewrite that drops a number the tool still reports |
| key vanishes from the artefact | a check silently ceasing to check |

A fourth was worth ruling out rather than assuming: superseded figures still standing as current in
live documents. MEASURED — `0.3538`, `604`, `27%`, `44%` and the old undefended count all appear in
`ROADMAP.md`, and every occurrence is inside a row *about* the correction. No stale claim is
presented as current, so there was nothing to fix and the check for it would have found nothing.

## Why the ledger is excluded, and why that is not a dodge

`docs/research-verification.md` is deliberately outside this check. It is an append-only record:
round thirty-one reports 108 volumes and 38,231 abstracts, round eighty-five reports 186 and 46,905,
and **both are correct as statements about when they were made.** This document's own convention is
that superseded entries are annotated in place, never rewritten. Checking a historical record against
today's artefacts asks every past round to have known a later round's numbers — a category error,
and MEASURED it produces 22 "contradictions" of which every one is a correctly-preserved historical
figure.

The ledger keeps the attribution check, which asks a figure to name its source rather than to agree
with today's.

---

# Round ninety — "undefended" is about the comments; "load-bearing" is about the code

Round eighty-nine counted the constants nobody defended and swept **five** of them — the five in
`lite_score`, picked by hand because they were obviously load-bearing. That is the same move rounds
eighty-six and eighty-seven made, one level up: pick the parameter that looks important and test it.
It leaves the question it was supposed to answer still open, for every constant nobody picked.

**Undefended is a property of the comments. Load-bearing is a property of the code, and only one of
the two has been measured.** `eval/constant_influence.py` measures the other: perturb each
undefended constant, re-score both arms, and record what moved.

## ✗ First it corrected round eighty-nine's headline

The census walked upward from a constant collecting comment lines and stopped at the first line that
was not one. Constants in this repository are written in **groups under a single comment**, so the
walk stopped at the sibling assignment above and the group's justification was never seen. Eight
constants across six files — `_NLL_MID`, `_COMMON_SCALE`, two `_CAL_SCALE`s, `_LENGTH_SLACK_SHARE`,
`_MIN_BLOCKS_FOR_LONE_NOTE`, `_MIN_SENTENCES_FOR_SPREAD`, `_OTHER_FUNCTION_WORD_FLOOR` — were
reported bare while sitting under a comment explaining them.

It was inconsistent rather than uniformly wrong, which is why it survived review: `_NLL_SCALE` and
`_SPREAD_MID` passed because the *next* comment block happened to fall inside the four-line
lookahead, while `_COMMON_SCALE`, two lines from the justification I had written for it the same
round, did not.

**MEASURED after the fix: 41 undefended, not 49. 36.9%, not 44%.** The entry in round eighty-nine is
annotated rather than edited, per this document's convention. The correction makes the repository
look better by its own metric, and that is precisely why it is stated at the top of this entry
rather than folded in quietly — a ledger that only publishes corrections which cost it something is
not keeping a ledger.

## The register

MEASURED, target `lite_score`, corpus the two arms behind the published AUROC:

| | |
|---|---|
| undefended constants | 41 |
| unreachable by perturbation | 6 |
| tested | 35 |
| **that move the published score** | **0** |

## ✅ And the control that makes a zero mean something

**"0 of 35 constants move the score" and "the harness is broken" are the same output.** Round
eighty-eight spent twenty minutes producing `0 scored` from a wrong dictionary key and caught it only
because zero was implausible. Here zero is entirely plausible, so implausibility cannot do the work.

So the register runs a positive control first — `_BURST_WEIGHT`, a constant already known by round
eighty-nine's sweep to reach the target — and **refuses to report at all** unless perturbing it
moves the score. MEASURED: it moves **99.6% of documents**, max Δ 0.1416. The zero is a finding.

## ⚠️ Six constants that cannot be tested this way, and are not therefore harmless

| constant | why perturbation cannot reach it |
|---|---|
| `WINDOW_WORDS` | bound as a function default argument |
| `_RESTATEMENT_COVERAGE` | bound as a function default argument |
| `RELAXED_SIM_BAR` | bound as a function default argument |
| `score.DEFAULT_THRESHOLD` | bound as a function default argument |
| `_MAX_INPUT_CHARS` | read at import time into another object |
| `detection_power.DEFAULT_THRESHOLD` | bound as a function default argument |

A default argument is evaluated when the `def` runs; rebinding the module global afterwards does not
reach it, and the perturbation reports **zero change** — the identical output to "this constant does
not matter". Both are detected statically and listed separately, because **a zero meaning "could not
test" and a zero meaning "does not matter" are the same number and opposite facts.**

`score.DEFAULT_THRESHOLD` is the clearest case: it is the loop threshold every flag rate in this
repository is computed against, and a naive register would have printed 0.0000 beside it.

## What the arc from eighty-six to ninety actually establishes

| round | question | answer |
|---|---|---|
| 86 | does the survey's recall window decide its ratio? | no — 9.3x to 14.0x, published interior |
| 87 | does the topic pattern's breadth decide it? | no — 7.5x to 14.2x, shipped rung most discriminating |
| 88 | is the inversion's *explanation* real? | yes in direction, and 0.34% of the variance |
| 89 | is the inversion a calibration artefact? | no — 30 settings, none above 0.5 |
| 90 | is any *other* unchosen number reaching it? | no — 0 of 35, with a control at 99.6% |

**Every parameter anyone can reach has been varied, and the published conclusions do not move.** The
honest residue is small and named: six constants that perturbation cannot reach, one target
(`lite_score`) rather than every published number, and one corpus. A constant that does not reach
`lite_score` is off-target, not harmless — several of the 35 govern the rewriter and the entailment
gate, which this register says nothing about.

## What this round is an instance of

Round eighty-nine built a census and then hand-picked what to sweep from it. That is the reflex the
census existed to replace, and it survived the building of the tool meant to remove it. Automating
the choice is what found both the grouping defect and the six unreachable constants, neither of
which a person scanning a list would have noticed — one because it was inconsistent rather than
absent, the other because it looks exactly like good news.

---

# Round eighty-nine — how many numbers here did anybody actually choose?

Rounds eighty-six and eighty-seven each found one unchosen parameter under a published claim, swept
it, and reported what moved. Two instances is an anecdote. This round counts them, and then sweeps
the ones that carry the most weight.

## The census

`eval/constant_census.py`, MEASURED across `untell/` and `eval/`: **111 module-level numeric
constants, 49 of them — 44% — with nothing anywhere saying why they hold that value.**

> ⚠️ **49 is wrong; the figure is 41 (36.9%).** Round ninety found the census stopped its upward
> walk at the first non-comment line, so a block comment heading a *group* of constants justified
> only the one directly beneath it. Eight constants across six files were reported bare while
> sitting under a comment that explained them. Corrected in round ninety, which also records why
> this entry is annotated rather than edited. The correction runs in this repository's favour, which
> is the reason to be loud about it rather than quiet. The bar is
deliberately low: a comment near the number naming a measurement, a round, a paper, a standard, or a
reason. Not that the reason is good — that somebody wrote one down.

Among the undefended are `_NLL_MID`, `_NLL_SCALE`, `_SPREAD_MID`, `_SPREAD_SCALE`, `WINDOW_WORDS`
and `DEFAULT_THRESHOLD`: the calibration of the detector every headline figure here comes from.

## ✗ And the census's own blind spot was the sharpest thing it produced

The five numbers that actually decide the stdlib score were **not constants at all.** They were
literals written into an expression, where a scan of assignments cannot see them:

    common_signal = clamp01((common - 0.30) / 0.30)
    burst_signal  = clamp01((0.55 - burst) / 0.55)
    return clamp01(max(rep, 0.6 * burst_signal + 0.4 * common_signal))

The 30.4% false-positive rate, the AUROC inversion, round eighty-eight's register finding — all of
them are that expression evaluated on a corpus. **The most load-bearing numbers in this repository
were also the least examinable, and for the same reason: nothing could name them.** They are named
constants now, and MEASURED, naming them changed nothing: 6,912 documents scored under both trees,
**0 differ**. `humanness()`'s two burstiness cut-offs got the same treatment.

## ✅ Then the sweep: is the inversion a calibration artefact?

`eval/constant_sensitivity.py` varies each of the five over the same two arms that produced the
published figure. It refuses to run unless `score_from(features(t), DEFAULTS)` equals `lite_score(t)`
exactly — sweeping a reimplementation is the defect round eighty-four found and round eighty-eight
repeated, and this one checks rather than promises.

MEASURED over 30 settings of five parameters (n = 56 machine, 634 human):

| parameter | AUROC range across its sweep | shipped |
|---|---|---|
| common_mid | 0.3522 – 0.4131 | 0.3538 |
| common_scale | 0.3229 – 0.3854 | 0.3538 |
| burst_mid | 0.3103 – 0.3593 | 0.3538 |
| burst_scale | 0.3281 – 0.3633 | 0.3538 |
| burst_weight | 0.3216 – 0.4127 | 0.3538 |

**Not one setting of any of them brings the AUROC above 0.5.** The full range is 0.3103 to 0.4131,
entirely below a coin flip. **The inversion on academic abstracts is not reachable from the
detector's calibration** — it is not something a different choice of these numbers could have
avoided, which is a considerably stronger statement than the inversion on its own.

⚠️ **Which figure this is.** The sweep reports **0.3538** at the shipped values and the repository
publishes **0.3529**. Both are right, and round eighty-four already established why: 0.3529 is
`score_text`, the shipped detector; 0.3538 is `lite_score`, the function underneath whose constants
are being swept. MEASURED on these same arms, the two differ by 9 parts in 10,000. Quote 0.3529 for
the detector and 0.3538 only for this sweep.

## ⚠️ And one result that is awkward for the shipped weights

`_BURST_WEIGHT` at 1.0 — burstiness alone — gives AUROC 0.4127. At 0.0 — common-word signal alone —
it gives 0.3457. **Further from 0.5 means better discrimination, so on this register the common-word
signal is the stronger of the two and it carries the smaller weight.** That independently reproduces
round seventy-nine's component AUROCs (burst 0.4122, common 0.3459), measured a different way.

The source comment beside the weights says "burstiness weighted higher — it's the stronger of the
two weak signals." On HC3, where it was fitted, that is presumably true. On academic abstracts it is
backwards. The weights are **not** being changed: they were fitted on a corpus where the ordering is
correct, and refitting them to the corpus that exposed the inversion would be fitting to the
evidence. The comment now says both things.

**A related inconsistency this surfaced.** The torch path sets `_PPL_WEIGHT = 0.55` and comments
"perplexity carries most of the signal". The stdlib path weights *its* perplexity proxy — the
common-word ratio, described in the source as "a heuristic stand-in for a real LM" — at 0.40. **The
two scoring paths weight the same conceptual axis in opposite directions, and each asserts its own
direction in a comment as though it were a fact about the world.**

## ✗ Two defects in the census itself

**A dead exemption with a comment that described it.** `inline_literals` skipped `ast.Compare` nodes
"to exclude length guards". It excluded nothing: `ast.walk` yields the `Constant` inside a
comparison as its own node, so the branch never fired. A dead branch is ordinary; a dead branch with
a comment explaining its behaviour is worse than either, because it answers the question a reader
would otherwise ask.

**The two halves applied different bars.** Named constants were tested for a nearby justification and
inline literals were not, so `humanness`'s neutral `50.0` — which has a reason written beside it —
was reported alongside genuinely unexamined calibration. Where a number is written should not change
what is asked of it.

## What the count does when you are honest

Surfacing `humanness`'s two burstiness cut-offs from inline literals into named constants took this
repository's undefended count **from 47 to 49**. It got worse by its own metric, and that is the
correct direction: a hidden number is worse than a visible one that admits it has no evidence behind
it. A census that could only ever improve would be measuring effort rather than state.

The transferable claim is narrow. Rounds eighty-six and eighty-seven showed two parameters were
unchosen; this one shows that is the normal condition here — **37% of the constants (see the
correction above), and until now 100% of the ones that decide the published score.** The instrument that finds them is committed, so
the number is checkable rather than a confession.

---

# Round eighty-eight — testing the explanation, on 6,841 documents and no machine text

Rounds seventy-six to eighty-three are this repository's most consequential measurements, and they
end in an *explanation*: the lite detector's features "measure how closely a document reads like a
standard academic abstract, and in this corpus that is the human writing."

That sentence is published in `docs/index.md` and the README. It was inferred from **56 machine
documents written by one model** — the weakest link in the arc by a wide margin, and the one every
stated limitation points at.

It did not have to be. **If the explanation is true, it is testable with no machine text at all.**
Among documents that are all unambiguously human, the more prototypically academic ones should score
as more AI. That converts a 56-document inference into a 6,841-document measurement on a corpus
whose label nobody can dispute, and removes the generating model from the question entirely.

`eval/register_conformity.py` does it two independent ways:

* **vocabulary commonness** — the mean log document-frequency of a document's words over the corpus
  itself. High when a document is built from words nearly every abstract uses, which is what "reads
  like a standard academic abstract" means once you have to write it down. No model, no download.
* **venue class** — main/long, findings, short, workshop/student, demo/industry. A proxy for
  register that **never looks at a single word**, so it cannot inherit the detector's own features.

## ✅ Supported, in direction

MEASURED on 6,841 pre-2022 ACL abstracts:

| length band | n | rho(prototypicality, AI score) |
|---|---|---|
| 40–60 | 31 | +0.0633 |
| 60–80 | 158 | +0.1381 |
| 80–100 | 445 | +0.0826 |
| 100–150 | 3,032 | +0.0285 |
| 150–250 | 3,141 | +0.0407 |
| 250+ | 34 | +0.0827 |

Pooled **rho +0.0586**, bootstrap 95% CI **[+0.0357, +0.0842]** — excludes zero. **All six bands
point the same way**, which is a sign test at p = 0.031 on its own, and the bands matter because
length is the known confound: prototypicality correlates −0.28 with length and the score correlates
−0.10 with it, so a pooled figure alone would be worth nothing.

## ⚠️ And bounded, by the same measurement

MEASURED over the same 6,841 documents: **rho +0.0586 is 0.34% of the score's variance** (n = 6,841).
Register conformity is a real component of what
this detector measures and nowhere near all of it. It accounts for the **direction** of the
inversion and not for its **size** — the AUROC inversion is 0.3529 against 0.5, a far larger effect
than this within-human gradient.

The published wording did not say that, and it now does. This is a case of a claim being confirmed
and weakened by the same experiment, which is the more common outcome than either alone and the one
this ledger keeps finding.

## ✗ The venue check, and a wrong prediction that was mine

MEASURED, length-standardized (direct standardization onto the corpus length distribution, because
workshop papers are shorter and this detector scores shorter text higher):

| venue class | n | raw mean | length-standardized | mean prototypicality |
|---|---|---|---|---|
| workshop/student | 125 | 0.3668 | **0.3594** | −2.7567 |
| short | 139 | 0.3463 | 0.3342 | −2.7270 |
| main/long | 5,347 | 0.3381 | 0.3385 | −2.8261 |
| findings | 870 | 0.3306 | 0.3302 | −2.7593 |
| demo/industry | 274 | 0.3184 | **0.3088** | −2.9873 |

**I predicted main/long would score highest and was wrong.** Workshop and student-research papers
score highest, and the difference from main is real: MEASURED **+0.0287, bootstrap CI
[+0.0053, +0.0520]** (n = 125 against n = 5,347).

The prediction was wrong, not the hypothesis, and the difference matters. I had assumed "main
conference" meant "most prototypical academic prose". It does not, MEASURED: workshop papers use
**more common** vocabulary (−2.7567 against −2.8261), and demo/industry papers use the **rarest**
(−2.9873) and score **lowest**. The extremes line up with prototypicality exactly. So the venue result is
consistent with the vocabulary result, by a route that never reads a word.

**But it is corroboration and not a second test, and the honest figure says so.** Rank the five
classes by prototypicality against the score. MEASURED: on raw means the agreement is rho 0.80;
with length held fixed it drops to **rho 0.50 across five classes**, which has no power either way. The
middle three shuffle. The tool prints that caveat rather than the 0.80, because the 0.80 is the
number that has the length confound still in it.

## ✗ And the first attempt scored zero of 6,842 documents

The probe read `result["score"]` from `score_text`. That key does not exist — the documented one is
`max`, and per-detector values live under `detectors`. `dict.get` returned `None` for **every one of
6,842 abstracts**, the loop skipped them all, and the run reported `0 scored` after twenty minutes.

`docs/result-shapes.md` exists in this repository precisely because "guessing wrong returns a
plausible value rather than raising", and I guessed wrong anyway while holding the document that
says so. The fix is not care: `score_one` now routes through `eval.detection_power.score_arm`, the
same helper that produced the published AUROC. Round eighty-four's defect — a reimplementation
disagreeing with the shipped path in the third decimal — and this one are the same defect, and
calling the shipped helper is the only fix that stays fixed.

## What made the third cut affordable

Scoring 6,841 abstracts takes about twenty minutes, and this round needed three cuts of the same
numbers: pooled, within length band, and by venue within length band. The third is the one that
matters — without it the venue table is a length table — and at twenty minutes a question it is
exactly the check that gets skipped.

So scoring is now separated from analysis. `score_rows()` produces the rows, `analyse()` reads them,
`--dump` and `--rows` move them across runs, and `eval/data/register_conformity_rows.json` commits
all 6,841 (90 KB compressed) so anyone can ask a new question of this measurement in seconds rather
than re-deriving it. **The reason the length confound got checked here is that checking it was
cheap.** That is a fact about the tooling, not about diligence, and it is the transferable part of
this round.

---

# Round eighty-seven — the second filter, and the one that could actually break the claim

Round eighty-six swept `DETECTION` and found the imbalance robust to every recall setting. That was
the safer of the two sweeps available, and worth noticing: **the survey runs two regexes in series,
and the sweep that could overturn the conclusion is the other one.**

`DETECTION` selects 612 papers. A topic pattern then selects a row inside them, and the row this
project's strategy rests on is four alternatives long and returns **13 papers**. Thirteen. A pattern
that narrow missing eight relevant papers moves the ratio by a third; missing forty ends the
argument. Round eighty-six could only ever have confirmed a corpus-level property. This round is the
one with a real chance of a negative answer.

`TOPIC_LADDERS`, `topic_sensitivity()` and `python -m eval.litreview --topic-sweep` broaden each
load-bearing row in rungs that still mean the topic.

## The answer, MEASURED on the 612 detection papers

| false-positives pattern | papers | share | lift |
|---|---|---|---|
| shipped | 13 | 2.1% | **7.1** |
| + type I error, specificity | 16 | 2.6% | 3.6 |
| + wrongly, mistakenly | 16 | 2.6% | 3.4 |
| + human text misclassified | 17 | 2.8% | 3.6 |
| + over-flagging, accusation, unfairness | 21 | 3.4% | 3.3 |

Robustness over its own ladder: **157 → 176 → 184**. Across all twelve combinations the ratio runs
**7.5x to 14.2x** and never approaches parity.

✅ **The claim survives, and two details make the survival worth more than the headline.**

**The shipped count is the conservative end.** Every broadening adds papers — 13 to 21, a 62%
increase — and some of them plainly belong (*Almost AI, Almost Human: The Challenge of Detecting
AI-Polished Writing*, `2025.findings-acl.1303`). The row is therefore reported with its range rather
than quietly rewritten, on the round-thirty principle that a survey states its error term instead of
picking the filter it prefers. The honest summary of this row is **13–21 papers**, not 13.

**The shipped pattern has the highest lift of any rung.** 7.1 against 3.6, 3.4, 3.6 and 3.3: every
widening buys papers by spending discrimination. A filter tuned to produce a conclusion would look
exactly the other way round — narrow where it helps, and no more informative than its neighbours.

## ⚠️ One rung takes the ratio to 1.3x, and it is in the shipped table on purpose

Adding `reliab|trustworth|consequence` lifts the row from 21 papers to **123**, and the ratio from
7.5x to 1.3x. Printed on its own that is a refutation of this project's central claim.

It is not one, and `term_lift()` is the instrument that says why. MEASURED against the whole
46,905-abstract corpus rather than the detection subset:

| term | share of the WHOLE corpus | share of detection papers | lift |
|---|---|---|---|
| `false positive` | 0.3% | 1.6% | **6.1** |
| `falsely flag/accus` | 0.0% | 0.3% | **51.1** |
| `FPR` | 0.0% | 0.5% | **12.1** |
| `reliab` stem | **7.1%** | 14.7% | 2.1 |
| `trustworth` stem | 1.0% | 2.3% | 2.3 |
| `specificity` | 0.4% | 0.5% | **1.1** |

A `reliab` stem is in one abstract in fourteen across the entire Anthology, including papers about
parsing and speech. A pattern built on it is not measuring a topic within the detection subset; it
is measuring English. `specificity` at lift 1.1 is the purest case — it looks like a
false-positives term and carries essentially no information at all.

**That rung stays in the shipped output, marked and measured.** A reader who doubts the count will
broaden the pattern, and the first words they reach for are exactly these. They should find the
result already computed and already explained rather than conclude they have overturned something.
This is the same reasoning as keeping the off-topic noise floor in `--noise-floor` instead of
excluding it: the failure mode is more useful documented than hidden.

## What the two sweeps establish together

The survey's conclusion now has both of its filters varied:

| filter | swept over | ratio range | conclusion |
|---|---|---|---|
| `DETECTION` recall (round 86) | 0–400 char window, 343–768 papers | 9.3x – 14.0x | holds |
| topic pattern breadth (round 87) | 5 rungs x 3 rungs | 7.5x – 14.2x | holds |

**The published ratio is interior to both ranges.** Neither parameter was chosen, and neither, when
varied deliberately and adversarially, produces a number that favours the claim more than the one
already shipped.

The residual honest caveat is unchanged and is not a parameter: this is the ACL Anthology, so it is
what the NLP community publishes, not what the field of AI-writing research contains. Rounds 22, 23
and 30 each retracted a "nobody does X" claim that a keyword search had supported.

---

# Round eighty-six — the number nobody chose, swept from 0 to 400

Round eighty-five found that the survey's count moves with concatenation order. That is a defect in
how the instrument is called. This round asks the harder question about the same instrument: **what
is inside it that nobody ever chose?**

One thing, and it carries everything. `DETECTION` matches a detection term only when an AI term sits
within `DETECTION_WINDOW` characters of it. Round fifty-seven wrote that rule to cut a 40% noise rate
and needed *a* window; the value in the source is 40, and it is what that round happened to use. No measurement selected it. Every count in ROADMAP section 7, every share in
`docs/index.md`, and the ratio this project's entire strategy rests on sit downstream of it.

`DETECTION_WINDOW`, `detection_pattern(window)` and `window_sensitivity()` exist so that number can
be varied. The regex is now built by a function rather than frozen in a string literal — checked
byte-identical against the published one, because a refactor that changes the pattern changes every
figure in the repository. `python -m eval.litreview --window-sweep` reruns the whole thing, and
`eval/data/window_sweep.json` commits the result so it can be checked without the 99 MB corpus.

## What the sweep found

**The windows nest.** MEASURED: widening from 0 to 400 in nine steps loses **zero** papers at every
step. So the parameter is a recall dial along one axis, not nine different corpora, and nothing
below is a reshuffling artefact.

**The corpus size is very sensitive to it. The shares are not.**

| window | detection papers | off-topic floor | robustness | false positives | fairness |
|---|---|---|---|---|---|
| 0 | 343 | 3.2% | 27.1% | 2.9% | 1.7% |
| 20 | 525 | 11.4% | 26.1% | 2.3% | 2.3% |
| **40 (published)** | **612** | **13.2%** | **25.7%** | **2.1%** | **2.1%** |
| 80 | 708 | 14.5% | 24.2% | 1.8% | 2.3% |
| 200 | 764 | 15.4% | 23.8% | 1.7% | 2.4% |
| 400 | 768 | 15.5% | 23.7% | 1.7% | 2.3% |

A **2.2x range** in the corpus produces a largest share move of **4.3 points**, and no topic ever
overtakes another. The shares drift downward because the denominator takes on noise as the filter
loosens — which is why a share is now quoted with its window rather than on its own.

## ✅ The finding is not the stability. It is the saturation.

MEASURED, absolute counts across the sweep:

| topic | w=0 | w=40 | w=400 | saturates at | further papers entering with none of them this topic |
|---|---|---|---|---|---|
| robustness/paraphrase | 93 | 157 | 182 | w=200 | 4 |
| multilingual/cross-lingual | 57 | 82 | 102 | w=400 | 0 |
| calibration/thresholds | 9 | 22 | 28 | w=200 | 4 |
| fairness/non-native bias | 6 | 13 | 18 | w=120 | 24 |
| **false positives/accusation** | **10** | **13** | **13** | **w=30** | **192** |
| **disability/neurodivergence** | **0** | **1** | **1** | **w=20** | **243** |

**The false-positives row reaches 13 papers at a 30-character window and never moves again.**
Between there and w=400 the corpus admits **192 further detection papers and not one of them is
about false positives**, while robustness nearly doubles across the same sweep and multilingual work
is still growing at the widest setting.

This answers an objection that until now could only be met with a defence. "Your filter is too
strict to find the false-positive literature" is a testable claim, and it is false: buying recall at
any price in precision recruits none of that literature, because there is none to recruit. The
documented near-zero on disability is the same result harder — one paper at w=20, and 243 further
papers enter behind it without a second.

**And the ratio moves against the objection.** Robustness-to-false-positives is **9.3x at the
tightest window and 14.0x at the widest**. The published **12.1x** is an interior point, not the
sweep's best case — so the window was not, and could not have been, chosen to flatter the claim.
`tests/test_the_survey_ratio_survives_every_recall_setting.py` asserts exactly that: the published
window must lie strictly between the sweep's extremes.

## ✗ And a figure that matched nothing

`docs/index.md` summarised the survey as "**27% against 2%**". No row in this repository produces
27%. The published share is **25.7%**, the sweep's maximum is 28.0% at w=10, and the figure carried
no `MEASURED` attribution — so it had survived every attribution check by never claiming to be a
measurement. It now reads **24–28% against under 3%, at every filter setting swept**, which is the
range the sweep actually establishes and is a stronger statement than the point estimate it replaces.

That is the fourth time a number in this repository turned out to be unattributed rather than wrong,
and the second time (after round eighty-four) that building a way to *rerun* a measurement was what
exposed a figure nobody could rerun.

## ✗✗ And staging the sweep exposed the worst defect in this ledger

`git add -A` did not pick up `eval/data/window_sweep.json`. `.gitignore` carries `data/` for
downloaded corpora, and that pattern matches `eval/data/` at any depth. Checking what else it had
swallowed:

    $ git ls-files eval/data/
    $

**Nothing. Four artefacts, built across rounds seventy-nine to eighty-five and described in this
document as committed, were never in the repository at all:**

| artefact | what it is | rounds resting on it |
|---|---|---|
| `eval/data/generated_abstracts.py` | the 70 machine-written abstracts — **the entire AI arm** | 76–86 |
| `eval/data/generated_registers.py` | the same-author register corpus | 79–83 |
| `eval/data/survey_counts.json` | the survey figures the audit checks documents against | 82–86 |
| `eval/data/tell_base_rates.json` | how often humans use each tell | 81–86 |

The consequences are as bad as they look. **The most consequential measurement in this repository —
that the detector's ordering is inverted on academic abstracts — was not reproducible from the
repository.** `python -m eval.detection_power --run` names its download when the Anthology cache is
missing, but nothing can download the machine arm: a language model wrote it, and outside this
working tree it did not exist. Every test reading those files passed here and would have failed on a
fresh clone. Round eighty-four's whole point was making the arc rerunnable; it made it rerunnable on
one disk.

**Nothing caught this, and the reason is general.** Every check in this repository — the audit, the
doc guards, the whole suite — runs in a working tree where the files are present. `git status` was
clean because ignored files do not appear in it. The document asserting the artefacts were
reproducible was itself the only evidence offered that they were.

`.gitignore` now un-excludes `eval/data/` explicitly, with the reason written next to the rule (git
cannot re-include a file whose parent directory is excluded, so the directory has to be un-excluded
rather than the files re-added). All five artefacts are committed.
`tests/test_every_artefact_the_tests_rely_on_is_actually_committed.py` asks **git** rather than the
filesystem, and fails on any untracked file under `eval/data/` — verified against a probe file, not
just asserted. It deliberately does not test `.gitignore`'s text: the rule that caused this was
correct for its purpose and wrong only in reach, so the thing worth asserting is the outcome.

⚠️ **This is the third distinct defect this round, and the first two were found by looking.** The
window sweep was a deliberate investigation; the unattributed 27% turned up inside it; this one
turned up because `git add -A` printed one fewer line than expected. The ratio of defects-found to
defects-looked-for is not encouraging about what an eighty-six-round audit trail is worth as
evidence that a repository is in the state it says it is in.

## What this round is an instance of

Rounds thirty and fifty-seven established the corpus and the noise floor as conditions on the
survey's numbers. This one establishes the third: the filter's recall. All three point the same way
— **the shares are robust and the counts are not**, so the counts travel with their conditions.

The general lesson is narrower and worth stating plainly: **a parameter that cannot be varied has
not been tested, and a constant regex is a parameter that cannot be varied.** `{0,40}` sat inside a
string literal for twenty-nine rounds, visible to every reader and testable by none of them, under a
ratio that carries the project's strategy. Making it an argument took eleven lines. Finding out what
it was worth took one command.

---

# Round eighty-five — the survey's own count depends on which order it reads a paper

Rounds seventy-six to eighty-four produced a method: **hold authorship constant and vary register.**
The obvious question is whether anyone else does that, and the survey corpus can be asked.

Searching all 612 detection papers, MEASURED by keyword over title and abstract:

| | papers | share |
|---|---|---|
| mention register, genre or domain | 70 | 11.6% |
| …and also a control or confound word | 3 | 0.5% |
| mention holding the author constant | **0** | — |

The three that pair the two: *The Million Authors Corpus* (2025.findings-acl.1335),
*How to Generalize the Detection of AI-Generated Text: Confounding Neurons*
(2025.findings-emnlp.1388), and *Explainable Disentangled Representation Learning for Generalizable
Authorship Attribution* (2026.acl-long.2018).

⚠️ **The zero is a fact about abstracts and phrasing, not about the field.** Rounds twenty-two,
twenty-three and thirty of this ledger each retracted a "nobody does X" claim that a keyword search
had supported and a reading had refuted. A paper can hold authorship constant without any of these
words appearing in its abstract. What the search establishes is that **no abstract in this corpus
advertises it**, which is weaker and is all that is claimed.

## And running that search found a defect in the survey itself

The search returned **604** detection papers where every published figure says **612**.

`DETECTION` is proximity-based — round fifty-seven rewrote it that way to cut a 40% noise rate — so
which words sit near which decides a match. My analysis joined `abstract + title`; the survey joins
`title + abstract`. **The words either side of the join change, and eight papers change with them.**

MEASURED: 612 title-first, 604 abstract-first, difference exactly 8. And the eight are not arbitrary
— they are the noise-floor cases: `InfoSurgeon` (fake news), factual-inconsistency detection over
long documents, and *Centering the Margins* (toxicity). **The papers that flip are precisely the ones
the proximity rule exists to adjudicate**, which is where it is doing the most work and where its
inputs matter most.

Four call sites did the concatenation inline, **two in each order, by luck rather than by choice.**
Any of them could have been the published one. `searchable()` is now the only place it happens, and a
test fails if a fifth appears.

## The shape, for the fifth time

Round sixty-two: a checker and its auto-fixer. Round seventy-one: two sibling checks, one of which
had already learned the lesson. Round eighty: two surveys a single-number pattern could not tell
apart. Round eighty-four: a published figure and its own reproduction command.

**This one is the same defect inside a single function's callers** — an instrument whose reading
depends on a detail nobody chose, repeated in four places, disagreeing with itself in two of them.
Every time, the fix has been to make one implementation and route everything through it, and every
time the defect was invisible until something outside the code asked the same question a different
way.
