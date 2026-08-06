# Building a Superior AI-Text Humanizer — Research Synthesis

**Question:** Technical + market research to build a superior AI-text humanizer product — detector internals, humanizer landscape, working bypass techniques, academic robustness evidence, watermarking/arms-race dynamics, and solvable gaps.

**Method:** `deep-research` workflow — 5 search angles → 109 agents → 27 sources → 129 extracted claims → 25 claims put through 3-vote adversarial verification. *The original run's synthesis step died on a Claude spend limit; this report is the synthesis completed from the cached, verified corpus. Sources prioritized 2024–2026.*

**Verification legend:** ✅ confirmed (≥2/3 verifiers upheld) · ❌ killed (≥2/3 refuted — usually an over-claim, see note) · ⚠️ unverified (verifier votes lost to the spend limit — claim is *not* refuted, just not re-checked; treat as plausible-pending).

---

## TL;DR — the build thesis

The evidence is one-sided: **detection is fundamentally losing the arms race**, and the winning humanizer architecture is already visible in the 2025–2026 literature but *not* yet in the commercial products. The decisive technique is **closed-loop, detector-feedback adversarial paraphrasing that explicitly targets perplexity + burstiness, trained/optimized against a detector ensemble rather than one detector.** Commercial tools mostly do blind synonym-swap paraphrasing and plateau around 60–80% bypass; the research-grade attacks hit 88–98% and transfer to unseen detectors. The exploitable gap is the delta between those two.

---

## 1. How detectors actually work (and where they break)

**Two signal families underlie almost everything:**

- **Perplexity** — how predictable each token is under a reference LM. AI text is *too* predictable (low perplexity). ✅ This is the primary signal, and the same signal that produces the non-native-speaker bias (below).
- **Burstiness** — sentence-to-sentence *variance* in perplexity. Humans spike and dip; models are flat. ✅ Effective humanizers target this directly.

**Specific detectors:**

| Detector | Mechanism | Real-world result |
|---|---|---|
| **GPTZero** | Multi-signal trained classifier (≈7 indicators), perplexity + burstiness as layer one | ❌ The popular "perplexity > 85 = human" threshold claim was **refuted 0–3** — GPTZero is *not* a static threshold; it's a trained classifier. ✅ Strong in one 2026 test: 97% acc, 0% FPR. |
| **DetectGPT** | Probability-curvature: text sits in negative curvature of the LM's log-prob surface; measured via perturbation discrepancy (T5 rephrasing, ≈negative Hessian trace) | Vendor-claimed 99% but ✅ **54.6% real-world accuracy — no better than random** (PMC12453642). Crushed by DIPPER (below). |
| **Binoculars** | log-perplexity / **cross-perplexity** ratio between two related models (Falcon-7B + Falcon-7B-Instruct); zero-shot, no training | ✅ Beats commercial GPTZero/Ghostbuster with no ChatGPT-specific tuning. ✅ But **most fragile to real paraphrasing** (F1 0.75→0.55) and ❌ 58% false-negative on GPT-4. The exact "95% TPR @ 0.01% FPR" headline was **refuted 0–3 / 1–2** as over-precise. |
| **Pangram / Copyleaks** | Commercial trained classifiers | Strongest measured: both hit **100% AI + 100% human** in a 30-tool 2026 test (small n). These are the hard targets. |
| **Originality.ai / ZeroGPT** | Commercial | Repeatedly the **hardest two to evade** across independent humanizer benchmarks. |
| **Writer / Grammarly detectors** | Commercial | ✅ **0% AI detection** — useless as detectors. |

**Takeaway for the build:** optimize against Originality.ai + ZeroGPT + Pangram + Copyleaks. Beating GPTZero/Turnitin alone is table stakes. Note **Turnitin shipped a Feb-2026 update with a dedicated "AI-paraphrased" category** — naive paraphrasers are now a detected class, raising the bar.

---

## 2. Bypass techniques — ranked by evidenced effectiveness

| Technique | Best measured result | Status | Verdict |
|---|---|---|---|
| **Detector-feedback adversarial paraphrasing** (iterative LLM rewrite using real-time detector confidence) | **−87.88% TPR@1%FPR** avg across detectors; −98.96% vs Fast-DetectGPT; transfers to neural/zero-shot/watermark detectors; quality 4–5/5 rated 87% of the time; **training-free** | arxiv 2506.07001 | **Strongest single technique. This is the core to build.** |
| **RL paraphrase vs ensemble** (StealthRL: GRPO+LoRA on Qwen3-4B) | **97.6% ASR**, mean AUROC 0.79→0.43, TPR@1%FPR→0.024 across 4 detectors; **transfers to held-out detectors** (trained on RoBERTa+Fast-DetectGPT, beat unseen Binoculars+MAGE) | ✅ **re-verified** (2602.08934 — paper real, all numbers + transfer confirmed) | Highest ceiling; needs training infra. **The moat.** |
| **Black-box alignment humanizer** (MASH: style-injection SFT → DPO → inference refinement) | **92% ASR** across 5 detectors / 6 datasets, beat 11 baselines, **quality preserved**, no white-box access | 2601.08564 | **The deployable product architecture.** |
| **DIPPER** (11B paraphraser, controllable lexical diversity + reordering) | DetectGPT **70.3% → 4.6%** TPR@1%FPR, semantics intact | ✅ confirmed (2303.13408) | Proven, but defeated by retrieval defenses where they exist. |
| **Synonym-perturbation (HMGC)** | Log-Likelihood AUC 0.913→0.185 (essays), 0.808→0.020 (Reuters) | ✅ (2503.08708) | Great vs metric detectors, weak vs trained classifiers. |
| **Token-mixing (TOBLEND)** — sample tokens from multiple LLMs | ChatGPT-Detector AUC 0.727→0 | ✅ (2503.08708) | Cheap, strong vs model-based detectors. |
| **Recursive paraphrasing** | Strong evasion | ✅ but **quality collapses** (cosine <0.65, ROUGE-L <0.3) | Avoid alone — fails the quality bar. |
| **Prompt-based "rewrite to sound human"** | — | ✅ **preserves quality but FAILS evasion** (can *raise* AUC) | What weak products do. Do not ship this alone. |
| **Self-edit / refinement prompt** | ChatGPT essay detection 100%→13%; abstracts 68%→28% | ✅ (2304.02819) | Cheap pre-pass, stackable. |

**The governing constraint — the "impossibility triangle" (2503.08708):** no single attack simultaneously maximizes *evasion + quality + low cost*. Synonym-swap is cheap+evasive but low-quality; prompt-rewrite is high-quality but non-evasive; recursive paraphrase is evasive but destroys meaning. **The product win is engineering the best point inside the triangle — which the alignment approach (MASH) and detector-feedback loop (2506.07001) demonstrably do, and which no shipping commercial tool currently does.**

---

## 3. Commercial landscape — what's actually shipping

Independent benchmarks (blog-grade, small-n, treat directionally):

- **Bypass rates cluster 60–80%** for the pack; only a handful clear a 4-detector gauntlet at <15% AI: StealthGPT, Monica, WriteHuman (one test); StealthWriter 97% / Undetectable.ai 96.5% (another test).
- **The winners restructure at sentence-architecture + burstiness/perplexity level. The losers (QuillBot 40%, BypassGPT 45%) do word substitution.** This is the clearest signal in the whole market.
- **StealthGPT reality check:** vendor claims 95–98% human; **independently measured 24.5% AI still detected** (June 2026), degrades past ~1,500 words, soft-caps ~50 uses/day. Marketing ≫ measured performance is the norm.
- **Pricing:** ~$8–30/mo (Humbot $7.99 worst-performing; Undetectable.ai $14.99 strong; StealthWriter $19.99).
- **Quality-aware differentiators that exist but are rare:** TextPulse exposes perplexity/burstiness/Flesch-Kincaid metrics + intensity modes + verbatim citation locking (APA/IEEE/MLA/Chicago/Vancouver).

**Incumbent weaknesses to attack:** blind single-pass paraphrasing, single-detector tuning, no closed-loop feedback, quality cliff on long docs, opaque black-box UX, no citation/meaning guarantees, no non-English focus, no on-device option, inflated marketing inviting a "measured proof" competitor.

---

## 4. Academic robustness / fragility evidence

- ✅ **Non-native bias is the headline finding (Liang et al., 2304.02819):** 7 detectors → **61.22% avg false-positive rate on non-native TOEFL essays** vs ~5% on native; **19.78% of human TOEFL essays unanimously flagged AI**, 97.8% flagged by ≥1 detector. Driver = perplexity (non-natives write lower-perplexity English). Confirmed independently for GPTZero in scholarly abstracts (25% false-accusation non-native vs 11% native; 44% of human abstracts flagged by ≥1 tool).
- ✅ **Theoretical ceiling — re-verified (Ghosal et al. survey, 2310.15264; *corrected attribution* — not Sadasivan):** as human/machine text distributions overlap (TV(M,H)→0), **any detector's AUROC → 0.5** (random) — **confirmed verbatim**. Detectors trained on small models (GPT-2) lose efficacy on large ones (GPT-3) — **confirmed** (cited to Gambini et al.). The "−71% from PEGASUS on watermarking" figure is **PARTIAL/mis-attributed**: the verbatim 71% is DetectGPT degradation via a *T5* paraphraser, not watermarking; the **−75% via 5× recursive paraphrase on retrieval methods is confirmed verbatim.**
- ❌ **Over-claims that got killed:** "paraphrasing evades ALL four major detectors" was refuted — a **retrieval-based defense catches 80–97% of paraphrased text @1%FPR** *where the provider logs all generations* (not applicable to local/open models). "Fine-tuned RoBERTa is robust to paraphrasing" refuted 0–3. So: paraphrasing is devastating, but not literally universal, and retrieval defenses are the one real counter (and they're impractical for most deployments).
- **Net:** the academic consensus leans hard toward *detection is unreliable and beatable*; the credible counter is **ensembles + retrieval logging**, which are operationally hard and which the strongest attacks (adversarial feedback, RL) still transfer past.

---

## 5. Watermarking & arms-race trajectory

- **Deployment is real and large:** Google SynthID — 100B+ images/videos, 20M Gemini responses; adopted by Nvidia, OpenAI, ElevenLabs, Kakao. **EU AI Act Art. 50 (effective Aug 1, 2026) mandates machine-readable watermarking**, penalties up to €15M / 3% global turnover. This is the forcing function pushing watermarking adoption.
- **But text watermarking is structurally fragile:**
  - ✅ **re-verified (SIRA, 2505.05190, ICML 2025):** entropy-token schemes embed in high-entropy tokens for quality — SIRA exploits exactly that via self-information rewriting, **~100% ASR across all 7 tested schemes, no algorithm/model access, $0.88/M tokens, runs on mobile-class models** — all confirmed verbatim.
  - ✅ **re-verified (2411.05277):** green-list-informed DIPPER drops UNIGRAM TPR 99.3%→0.2%, SIR 93.3%→3.8% — **confirmed verbatim**. Green-list reverse-engineerable from ~200k tokens at F1>0.80 — confirmed (note: their *generation-based* F1, not vanilla). Quality preserved: P-SP **0.78–0.88** (claim understated upper bound), perplexity ~10–11 — confirmed.
  - ✅ **SynthID-Text Mean Score has a "layer-inflation" vulnerability** — append tournament layers to make 87% of watermarked text read as unwatermarked (its Bayesian Score variant resists this).
  - ✅ **re-verified (CDG-KD, 2504.17480):** knowledge-distillation scrubbing makes KGW watermark p-value 2.22e-10 → 0.348 (undetectable) at low perplexity — confirmed exactly; works black-box via "watermark radioactivity" — confirmed. SynthID harder to scrub than KGW/Unigram — confirmed. Spoofing (falsely attribute harmful text to a watermarked model) is even stronger than the corpus stated: **paper reports ASR 6% → 94%** (corpus understated as "<10%→>60%").
  - ✅ Pre/post-processing watermarks (char/synonym/Unicode) break under trivial substitution; metadata strips on social upload; open-source watermarks "disable by commenting out a line." **No scheme satisfies all four EU-AI-Act criteria simultaneously.**
- **Practical conclusion:** watermarking is **not a near-term barrier** for a humanizer — most providers don't watermark, the common schemes break under informed paraphrasing, and the one robust-ish variant (Bayesian SynthID) is paraphrase/back-translation-evadable anyway. Design for it, don't fear it.

---

## 6. Ranked exploitable gaps → concrete build strategy

**Ranked gaps (highest leverage first):**

1. **Closed-loop detector-feedback rewriting.** No shipping product does iterative rewrite against live detector scores. Evidence says it's the single strongest lever (−88% TPR, training-free, quality-preserving). **Build this first.**
2. **Explicit perplexity + burstiness optimization** as the objective, not a side effect of synonym swap. This is literally what separates market winners from losers.
3. **Ensemble + held-out generalization.** Optimize/RL against Originality.ai + ZeroGPT + Pangram + Copyleaks + a *held-out* detector to force transfer (StealthRL/MASH show this transfers; single-detector tuning doesn't).
4. **Hit the impossibility-triangle sweet spot via alignment (style-SFT → DPO → inference refinement)** instead of recursive paraphrasing — gets evasion *and* quality, the thing nobody nails.
5. **Citation/meaning integrity** — lock citations + named entities + numbers before rewrite (TextPulse proves demand; most tools mangle them). Opens the credible academic niche.
6. **Non-native-writer positioning** — a large, sympathetic, underserved market that is *falsely* flagged even when genuinely human. "Restore fair treatment of your real writing" is a defensible, less-gray framing than "cheat."
7. **On-device / local model** — SIRA-class quality runs on mobile-scale models; nobody offers private, no-API-logging humanization. Privacy + the one real defense (provider-side retrieval logging) literally can't see you.
8. **Measured-proof transparency UX** — incumbents inflate ("98% human" vs 24% measured). A tool that shows live per-detector scores + honest benchmarks wins trust.

**Reference architecture:**

```
Input → [Preserve-lock: citations, entities, numbers, quotes]
      → [Style-aligned rewriter: SFT on human corpora + DPO for human-ness]   (MASH-style base)
      → [Perplexity/burstiness shaper: raise variance, lift token-surprise]
      → [Closed-loop refiner: score vs detector ensemble, iterate until all < threshold]  (2506.07001 core)
      → [Quality gate: semantic similarity ≥ 0.76, fluency check; reject + retry if failed]
      → Output + live per-detector report
```

- **Base attack:** alignment (MASH) for the deployable always-on path; **detector-feedback loop (2506.07001)** as the finishing pass for hard cases.
- **Stretch:** RL-against-ensemble (StealthRL) once you have detector-API throughput to train it; this is the moat (transfers to detectors you didn't train on).
- **Quality guardrail:** enforce semantic similarity ≥ 0.76 and reject recursive-paraphrase-style degradation — the triangle is real, so make quality a hard gate, not a hope.
- **Targets:** tune for Originality.ai / ZeroGPT / Pangram / Copyleaks / Turnitin-Feb-2026; the rest fall out for free.

---

## Source list (27 sources, by quality)

**Primary (papers):** 2304.02819 (non-native bias / Liang) · 2303.13408 (DIPPER) · 2401.12070 + openreview iARAKITHTH (Binoculars) · 2605.14240 (paraphrase fragility benchmark) · 2310.15264 (theoretical limits / PEGASUS) · 2411.05277 (green-list reverse-engineering) · 2602.08934 (StealthRL) · 2601.08564 (MASH) · 2603.03410 (SynthID layer-inflation) · 2505.05190 (SIRA) · 2504.17480 (CDG-KD scrubbing) · 2506.07001 (detector-feedback adversarial paraphrasing) · 2503.08708 (impossibility triangle, HMGC/TOBLEND) · 2511.03641 (EU-AI-Act watermark survey) · PMC12453642 (GPTZero scholarly bias) · 2503.18156 · 2504.17480.
**Secondary:** infoq SynthID content-detection (2026-05).
**Blog (directional, small-n benchmarks):** humanizerai, hayimsalomon "25 tools", skywork "12 humanizers", untellmy/stealthgpt, textpulse, pangram best-detectors, gptzero perplexity explainer (primary-vendor), DetectGPT explainer.

## Verification update (re-checked after spend limit lifted)
Re-ran adversarial verification on the 4 sources whose votes were lost to the spend limit. Outcome — **the unverified pillars hold:**
- ✅ **StealthRL (2602.08934) is a real paper** (Ranganath & Ramesh, Feb 2026) — 97.6% ASR, AUROC 0.79→0.43, TPR@1%FPR 0.024, and held-out-detector transfer **all confirmed verbatim.** Not a hallucinated citation. This is now solid evidence for the ensemble+transfer gap.
- ✅ **Theoretical AUROC→0.5 ceiling** confirmed; **small→large model generalization failure** confirmed (source is the **Ghosal et al. survey**, not Sadasivan — attribution corrected above).
- ✅ **Watermark green-list collapse + reverse-engineering + quality-preservation (2411.05277)** confirmed (minor nuances: generation-based F1; P-SP range is 0.78–0.88).
- ⚠️→PARTIAL **Binoculars score formula (2401.12070):** the formula *direction* (log-PPL ÷ cross-PPL) and model roles (Falcon-7B observer / Falcon-7B-Instruct performer) are **correct**; only the prose gloss of cross-perplexity was imprecise. So the earlier "killed" verdict was too harsh — the mechanism is right.
- Minor downgrades: the "−71% from PEGASUS on watermarking" figure is mis-attributed (real 71% = DetectGPT via T5 paraphraser); recursive-paraphrase −75% is fine.

**Net effect on strategy: unchanged and strengthened.** StealthRL confirming real + transferable raises confidence in gap #3 (RL-against-ensemble as the moat).

## Caveats
- ✅ **All deferred claims now re-verified.** SIRA (2505.05190, ICML 2025) and CDG-KD (2504.17480) both confirmed real with numbers checked; the only correction is that CDG-KD spoofing is *stronger* than the corpus stated (6%→94%, not <10%→>60%). No surviving ⚠️ unverified pillar.
- Commercial bypass-rate numbers are vendor/blog benchmarks with small samples and shifting detector versions — directional only.
- Detector performance is model-specific and date-specific; Turnitin's Feb-2026 anti-paraphrase update means any technique needs continuous re-testing.
