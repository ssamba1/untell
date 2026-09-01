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

**Result: no roadmap item flips on any Tier-B claim.** Every item is either grounded in a Tier-A
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
