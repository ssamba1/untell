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

**These channels are open and were used as primary sources:**

- **PubMed / PMC via MCP** — full metadata, and full text for open-access records. This covers
  *Nature Human Behaviour*, *Trends in Cognitive Sciences*, *Patterns*, *Science Advances*,
  *PeerJ CS* and more, which is most of the prevalence and fairness literature.
- **github.com via WebFetch** — author repositories, dataset cards, reference implementations.
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
does not require the distributions to converge, only the population to be diverse. *(Tier B — the
arXiv host is blocked; corroborated across index and ResearchGate summaries.)*

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
| "Your Brain on ChatGPT" characterised as small and non-peer-reviewed | **Correct, and now citable:** still a preprint, with a formal published Comment (arXiv:2601.00856, Stanković et al.) faulting sample size, EEG methodology, reproducibility, reporting consistency and transparency | `ai-writing-research.md` §6 |

## Claims that survived unchanged

- No peer-reviewed quantification of neurodivergent-writer false-positive rates exists. Checked
  from three directions; sources actively warn that circulating numbers trace to no study.
- Detection is unreliable and beatable; paraphrase attacks transfer; watermarking only covers
  cooperating generators; retrieval defence works but needs provider-side logging.
- Humans cannot reliably detect AI text (experts ~70%, students 59%, ESL teachers 61%).
