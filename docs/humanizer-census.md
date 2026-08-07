# The humanizer census — 1287 repos found, 435 read

**Method.** A multi-modal sweep run 2026-08-05: 12 discovery angles (GitHub topics, keyword
variants, technique names, research code, detector repos, unicode/watermark tools, prompt guides,
awesome-lists, API wrappers, non-English, package registries, academic integrity), looped until two
consecutive rounds returned nothing new — **3 rounds, 624 distinct queries, 1287 candidate repos**.
The top 435 by relevance were then read individually: README plus source where reachable. Raw data:
[`humanizer-census.json`](humanizer-census.json).

**Read the coverage limits before the numbers** — they are at the bottom, and they are real.

---

## The headline: three of this repo's claims do not survive

| claim as previously written | census finding |
|---|---|
| an inference-time detector-feedback loop is what nobody else has | **49 of 435 put a detector in the loop; 43 at inference time** |
| automated meaning verification is ours alone | **85 of 435 verify meaning; 202 mention a semantic check** (NLI, BERTScore, USE or embedding cosine) |
| we are the most complete open humanizer | **true only for English.** **139 of 435 (32%) target another language**, including four of the eight largest tools in the field |

Counts across the 435 read: **49** detector-in-loop (43 at inference time) · **85** meaning
verification · **131** some fact preservation · **136** any tests · **139** non-English.

---

## What the field actually looks like

| category | n | what it is | ceiling |
|---|---|---|---|
| prompt-guide | 184 | a Markdown pattern list an LLM applies | no measurement, no loop; depends entirely on the model. **42% of the whole field** |
| api-wrapper | 75 | client for a commercial humanizer | inherits that vendor's ceiling and price |
| adversarial-perturbation | 39 | search over substitutions against a detector score | strongest measured evasion; verifies nothing |
| rule-based-rewriter | 38 | deterministic transforms | cheap, weak alone |
| research-code | 19 | paper artifacts | strong numbers, not installable |
| fine-tuned-model | 11 | trained to evade (GRPO/DPO/SFT) | strongest transfer, needs a GPU |
| unicode-trickery | 7 | homoglyphs, zero-width | trivially defeated by normalisation |
| paraphrase-model | 7 | a paraphraser applied wholesale | one-shot, no feedback |
| detector-with-evasion | 5 | detectors shipping attack code | |
| back-translation / dataset / other | 50 | | |

**The field is overwhelmingly prompt guides.** 184 of 435 are a Markdown file telling an LLM what
not to write — no detector, no measurement, no test. Add the 75 API wrappers and **60% of the field
does not implement a humanizer at all**; it either instructs one or bills for one.

## The biggest repos are not the ones we were comparing against

| stars | repo | category |
|---|---|---|
| 71,185 | `binary-husky/gpt_academic` | academic LLM workflow (humanizing is one feature) |
| 68,545 | `kevintsai1202/Humanizer-zh-TW` | prompt-guide, **Traditional Chinese** |
| 33,761 | `blader/humanizer` | prompt-guide |
| 32,043 | `linexjlin/GPTs` | leaked GPT prompts, includes humanizers |
| 14,700 | `op7418/Humanizer-zh` | prompt-guide, **Chinese** |
| 7,019 | `NomaDamas/k-skill` | prompt-guide, **Korean**, 60+ Korean-specific tells |
| 4,182 | `epoko77-ai/im-not-ai` | prompt-guide, **Korean**, 70 patterns |
| 2,826 | `conorbronsdon/avoid-ai-writing` | prompt-guide, Tier-1A/1B evidence split |
| 2,029 | `chi111i/BypassAIGC` | api-wrapper, Chinese |
| 1,551 | `lynote-ai/humanize-text` | back-translation |

**The single largest blind spot this census found is language.** **139 of the 435 — 32% —** target
a language other than English, including four of the eight largest repos in the field. Our 29-pattern
catalogue, the voice matcher's scale constants, and every measurement in this repo are English-only.
Korean repos catalogue 번역체 calque patterns; Chinese ones catalogue Chinese punctuation and
academic-register tells. None of that is portable from our catalogue, and none of ours is portable
to them.

## Who closes a detector loop (49), and how deeply

Sorted by how tightly the detector is coupled, not by stars.

| repo | coupling | meaning gate |
|---|---|---|
| `chengez/Adversarial-Paraphrasing` | **per token.** `Paraphraser.paraphrase()` scores every top-k candidate token's partial decode via `classifier.get_scores()` and picks the least-AI one | none (prompt only) |
| `Qi-Pang/LLM-Watermark-Attacks` | per token, per position, against a watermark detector | none; one attack *deliberately* inverts meaning |
| `RAFT (JamesLWang/RAFT)` | per substitution; accepted only if it strictly lowers the detector score | POS-tag match only |
| `zhouying20/HMGC` | per swap against a distilled **surrogate** of the victim detector | USE cosine ≥ 0.75 |
| `peggywritesforyou` | per sentence, RoBERTa inner loop + Sapling + ZeroGPT | length-ratio guard only |
| `ColinLu50/Evade-GPT-Detector` (SICO) | proxy detector inside prompt optimisation (~6 iters), then a fixed prompt | none |
| `StealthRL` | detector ensemble as GRPO **reward** (training only); single-shot at inference | cosine ≥ 0.90 + BERTScore ≥ 0.80, in the reward |
| `rudra496/StealthHumanizer` | local heuristic between passes; re-humanizes "ai"/"maybe" sentences | computed, **not blocking** |
| `ksanyok/TextHumanize` | `humanize_until_human()` against a 3-layer internal ensemble | structural checks only |
| `samrand96/Undetectable-AI` | polls writer.com until it returns "Human-Generated" | none |
| …39 more | see the JSON | |

**Correction to an earlier correction in this repo's history.** On first pass I read chengez's
README and the arXiv abstract, found neither established token-level decoding, and recorded that the
"token-level" characterisation was unsupported. Reading the **source** settles it the other way: the
loop is per token, in `utils.py`. That is *more* tightly coupled than our per-candidate loop, and
the earlier note was wrong. README and abstract are not the source.

## Who verifies meaning (85), and how well

85 verify meaning at all; 202 mention a semantic check somewhere. The methods, in rough order of strength:

- **Bidirectional NLI entailment** — `Advancing-Machine-Human-Reasoning-Lab/apt` requires both
  s1→s2 and s2→s1 to be predicted *entailment*. Methodologically the same gate as ours. It is a
  paraphrase-detection research tool, not a humanizer, and has no AI-text detector anywhere.
- **BERTScore + cosine thresholds** — StealthRL (0.80 / 0.90), baked into the training reward.
- **USE cosine** — HMGC (0.75), CLARE, GREATER (logged, not gating).
- **Embedding cosine** — AuthorMist (E5-small), `yuvraj-rag` (MiniLM, 0.88).
- **Prompt-based self-check** — several skill repos ask the LLM to confirm meaning survived. Not a
  gate; the model grades its own work.

What remains distinctive here is not *having* a meaning gate but the **stack**: five gates
(similarity, numerals, hedges, NLI both directions, semantic roles) that all run per candidate and
any of which can veto, plus byte-exact sentinel locking of citations and numbers with a tested
round-trip. **131 repos do some fact preservation**, so that is emphatically not unique either — but
no profiled repo combines all of it.

## What this leaves untell able to claim

Narrower than before, and checkable:

1. **The combination**, not any component. The loop is not ours (49 others), the meaning gate is not
   ours (85 others), fact preservation is not ours (131 others), tests are not ours (136 others). No
   profiled repo has all four *and* an installable package.
2. **Measurement discipline.** No profiled repo publishes negative results, refuted claims, or
   corrections to its own headline numbers. That remains genuinely unusual.
3. **Test depth** — 1868 tests against 136 repos having "any tests" at all.

And what it should stop claiming: that nobody else closes the loop, that its evasion numbers are
competitive with the research systems (chengez −87.88% TPR@1%FPR; StealthRL AUROC 0.79→0.43 on
15,310 human / 14,656 AI samples, against our n=6–12), or that it is the most complete humanizer
without the qualifier **"in English"**.

## Coverage limits — what this census still cannot claim

- **GitHub only.** GitLab, Codeberg, SourceForge and Gitea are not covered. Their explore pages are
  JS-rendered and could not be enumerated.
- **435 of 1287 read.** The remaining 852 were ranked below the cut by a keyword heuristic, which
  can misrank. The unread tail is dominated by small Spanish, Portuguese, French, Russian and
  Ukrainian `humanizador`/`humanizer-xx` skill repos — 49 of them died on an API spend limit
  mid-read, so that segment is under-counted even in the 139 non-English figure.
- **The completeness critics did not finish.** Both agents whose job was to find what keyword search
  structurally cannot reach — forks larger than their parents, monorepo subdirectories, renamed or
  DMCA'd repos, Gists, HuggingFace Spaces — died on an API spend limit, along with the synthesis
  step. This document was assembled from the raw profiles instead.
- **Star counts are as reported by the reading agent** and drift daily.
- **No repo's evasion claims were reproduced.** Every number attributed to another project here is
  what that project publishes, not something measured on our corpus.

So: "every single repo" is not what this is. It is the widest sweep this repo has run, with its
edges stated.
