# Measured: the first head-to-head against a competing humanizer

Every comparison this repository has published against another humanizer was made by reading their
paper. [`why-best-open-repo.md`](why-best-open-repo.md) ranks
[`chengez/Adversarial-Paraphrasing`](https://github.com/chengez/Adversarial-Paraphrasing)
(NeurIPS 2025, [arXiv:2506.07001](https://arxiv.org/abs/2506.07001)) above this repo on evasion and
below it on completeness, and says that packaging their mechanism behind these meaning gates *"would
beat this repo outright"*. The only mention of that project anywhere in the tree was
`tests/test_docs_claims.py` asserting that the **documentation** names it.

This is the first time any of it was run.

The census already recorded the correction that motivates this: on chengez's *mechanism*, reading
the README gave the wrong answer and reading the source gave the right one — *"README and abstract
are not the source."* That rule was applied to their mechanism and never to their numbers.

## What was measured, and what was not

Their repository ships the **saved outputs** of every run in the paper, so their model never had to
be executed. `kgw_wm/wm_mage` is a checked-in source corpus and
`outputs/guided_generations_kgwwmmage/` holds the matching rewrites, row for row: `noadv` is a plain
paraphrase, `adv/{radar,mage,roblarge,robbase}` are paraphrases guided by each of those detectors.
2000 aligned rows, median 146–179 words — comfortably above `score._MIN_WORDS_FOR_A_VERDICT` (40)
and `tells._MIN_WORDS_FOR_REPETITION` (60), so the length problem that made the MAGE row of
[Result 11](free-ceiling-measured.md) inconclusive does not apply here.

**No detector number appears below, and no meaning verdict either.** The environment this ran in
blocks `huggingface.co` at the network layer, so nothing model-backed was available: not the full
ensemble, not the RADAR holdout, not the NLI entailment gate, not the role-swap veto, not the
embedding similarity metric. What ran is the pure-stdlib half of the gate stack — numerals,
certainty, tells, token overlap — and `eval/head_to_head.py` prints every gate that did not run
rather than approximating it. The token-overlap metric is reported with its own
`confidence: low`, because `references/thresholds.md` says of it, in as many words, that *"it cannot
actually judge meaning"*. Substituting it for the meaning gate and publishing the number would be
the exact error this repository exists to measure.

## The first run was not a comparison, and saying why matters more than the table

Run naively — untell's loop at its shipped defaults against their outputs — untell posted 100% on
every preservation gate. It was meaningless. **The loop rewrote 37 of 200 documents.** 179 of 200
already scored below the 0.30 threshold on the lite detector (mean `max` 0.1778, 4 of 200 flagged),
so the loop correctly declined to touch them and returned the input unchanged. A 100% preservation
rate over 81.5% identity is the identity control wearing a costume.

chengez rewrites unconditionally. To compare like with like the loop was forced to rewrite every
document (`threshold=0.0`), and the table below is restricted to the **154 of 200 documents the
forced loop actually changed**, with every competitor arm scored on those same 154 rows.

## The table

`untell composite`, lite tier, `best_of=3`, `max_iters=5`, forced. n = 154 documents.

| arm | numerals kept | certainty kept | both | token overlap | tells / 100w | empty outputs |
|---|---|---|---|---|---|---|
| **untell composite (forced)** | **100.0%** | **100.0%** | **100.0%** | 0.972 | 1.06 → **0.74** | 0 |
| chengez `adv/radar` | 65.4% | 15.7% | 10.5% | 0.407 | 1.07 → 1.52 | 1 |
| chengez `adv/mage` | 62.7% | 15.0% | 9.8% | 0.427 | 1.07 → 1.99 | 1 |
| chengez `adv/roblarge` | 66.9% | 12.3% | 10.4% | 0.413 | 1.06 → 1.73 | 0 |
| chengez `adv/robbase` | 60.4% | 14.9% | 5.2% | 0.425 | 1.06 → 1.80 | 0 |
| chengez `noadv` (plain paraphrase) | 64.3% | 24.0% | 14.9% | 0.518 | 1.06 → 1.39 | 0 |

Three findings, in descending order of how much they survive scrutiny.

**1. Roughly a third of their documents lose a quantity.** 51–61 of 154 documents drop at least one
number, 114–126 numbers in total per arm. Their census record already said `fact_preservation:
"none"` — no numeral locking, no citation locking, nothing byte-exact — and this is what that costs
on their own published output. Inspected by hand, the drops are **compression, not fabrication**: a
source listing dates and figures comes back with the prose intact and the specifics thinned. An
earlier draft of this document called one of them a hallucinated substitution; re-reading the full
source showed the error was in the source and faithfully carried through, and the claim is
withdrawn here rather than quietly reworded.

**2. Their tell rate goes UP, on every arm, including the unguided one.** 1.06 → 1.52–1.99 against
untell's 1.06 → 0.74. Detector-guided paraphrasing makes text read *more* machine-written by the
catalogue's measure while making it score *less* machine-written to a detector. That is the
anti-correlation `humanizer-comparison.md` records from the other direction, reproduced on a
competitor's output, and it is the one result here that needed no gate untell could not run.

**3. The certainty column is real but overstated, and it is the weakest row in the table.** A 12–16%
pass rate reads as devastating and should not be quoted as though 85% of their rewrites firm up a
claim. Sampled by hand: some are genuine — `"might be diagnosed through compromised arterial flows"`
→ `"can be detected through compromised arterial flows, ensuring early intervention"` upgrades a
hedge and adds a benefit the source never claimed. Others are borderline, where the hedge survives
and an assertion is appended around it. The control that bounds it is the `noadv` arm: a *plain*
"rephrase without changing meaning" paraphrase, with no detector in the loop at all, passes only
24.0%. The gate is strict about heavy rewording in general — which this repository already knew and
documented, since the strict similarity bar rejects 6 of 8 faithful rewrites. **Read the certainty
column as directional, not as a rate.**

## What this does and does not settle

**Settled.** The completeness claim is now measured rather than asserted. On the same 154 documents,
untell keeps every quantity and every hedge and lowers the tell rate; chengez keeps about two thirds
of the quantities and raises the tell rate. Their outputs contain empty documents — 17 of 2000 for
`adv/radar`, 3 of 2000 for `adv/mage` — which score a perfect zero on every detector and every tell
category, and which `eval/head_to_head.py` excludes and counts rather than banking.

**Not settled, and the reason to be careful.** untell's token overlap is **0.972**; theirs is
**0.41**. Preservation is cheap when you barely edit. These are two operating points, not a
scoreboard: they rewrite heavily and lose fidelity, untell edits lightly and keeps it, and nothing
here shows untell could hold 100% at their edit distance. The honest form of the claim is *"at
untell's operating point the gates hold, and at theirs the fidelity does not"* — not *"untell
preserves meaning better"*.

**Untouched.** Their −87.88% TPR@1%FPR is not contradicted by anything above, because no detector
was run. The question `why-best-open-repo.md` actually poses — whether their evasion survives
untell's meaning gate — needs the NLI gate and the held-out detector, and therefore needs an
environment with model access. `eval/head_to_head.py` takes `--tier` and reports the entailment and
roles gates as unavailable rather than skipping them silently, so the run that answers it is one
command on a machine that can reach Hugging Face.

## Reproduce

```bash
git clone --depth 1 https://github.com/chengez/Adversarial-Paraphrasing
# convert the arrow outputs to jsonl (one {"text": ...} per line, row-aligned), then:
untell-head-to-head --source kgw_source.jsonl --rewrite kgw_adv_radar.jsonl \
                    --label "chengez adv/radar" --n 0
```

Worth keeping: **the comparison had been publishable for months and was never run, and running it
cost an afternoon.** The corpus was checked into their repository the whole time. What stopped it
was not access or compute — it was that reading their paper produced a table that looked finished.
