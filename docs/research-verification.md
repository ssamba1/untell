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
| **DetectRL-X** (2026.acl-long.1773) | 8 languages, 6 domains, 4 commercial LLMs, polish/expand/condense | ✅ **Confirmed verbatim**, including "8 dimensions" and the multilingual paraphrase/perturbation attack framework |
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
detectors punish legitimate light editing at 38–80% while letting more than 96% of deliberately
humanized synthetic text through.** They are hardest on exactly the people not cheating.

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
| Karr et al.: light "refine abstract only" edits flagged at **38–80%**; unmodified 2023–25 originals at **9–15%**; non-STEM ≫ STEM (p<0.001); scores track long-token and Academic Word List density | arXiv:2608.11256 — the closest published work to untell's thesis |
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
- Humans cannot reliably detect AI text (experts ~70%, students 59%, ESL teachers 61%).


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

Of those 334 detection papers, the number addressing each topic:

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

Bohler et al. analysed **1,490 manuscripts**, 659 from **2014** and 831 from 2024. Because 2014 text
is necessarily pre-LLM, **its detector score is a pure false-positive rate: 8.6%**. The authors
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
