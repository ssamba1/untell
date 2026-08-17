# Determinism contract

What is byte-reproducible in this repository, what is reproducible only given a seed, and
what is not reproducible at all — and how the loop enforces it.

## The guarantee

**Same input, same `--seed`, same flags, fresh processes → same output bytes.**

Verified by `tests/test_reproducibility_across_processes.py`, which runs each entry point in
separate processes and compares stdout byte-for-byte: `untell_text`, `score_text`, and the
`untell-humanize` CLI are identical across processes at the lite tier (the documented CLI
environment), and the sampled T5 path is identical once its torch RNG is seeded from the loop
seed (see below).

## How the seed reaches everything

`untell_text` (run.py) seeds the **process-global `random` module** from either the explicit
`--seed` or a blake2b digest of the input text, under a lock, and restores the caller's RNG
state afterwards. Every Python-random consumer draws from that one stream:

| Component | RNG source | Reproducible with seed? |
|---|---|---|
| `structural` rewriter (27 draw sites) | global `random` | yes |
| `surgical` rewriter | none — pure substitution | yes, trivially (deterministic by construction) |
| `composite` (structural+surgical chain) | global `random` | yes |
| `ensemble` contest | global `random` | yes |
| loop candidate selection (`_selection_subset`) | global `random`, resampled per iteration | yes |
| `local_policy` rewriter (Qwen policy) | torch RNG, re-seeded per generate from global `random` (`_next_torch_seed`) | yes |
| `t5_paraphrase` rewriter, `sample=True` | torch RNG, re-seeded per generate from global `random` | yes (was NOT, see below) |
| `t5_paraphrase` rewriter, `sample=False` (default) | none — beam search | yes, trivially |
| `mt_pivot` rewriter | none — beam search | yes, trivially |
| detectors (all tiers) | torch forward passes, no sampling | yes (eval mode) |
| `score_text` / `untell-score` | none | yes, trivially |

Three rewriters declare `deterministic = True` (`surgical`, `mt_pivot`, and `t5_paraphrase`
at `sample=False`): the loop draws them once per round instead of `best_of` times.
`tests/test_declared_determinism_matches_behaviour.py` checks every declaration against
behaviour so a rewriter that starts drawing cannot silently claim otherwise.

## What the seed deliberately does NOT reach

- **Remote rewriters** (anthropic/openai): the model is a remote service; sampling happens
  on someone else's machine. The loop cannot make it reproducible, and the CLI does not
  pretend otherwise.
- **`--browser` detectors** (zerogpt, detecting-ai): live web checkers with their own noise.
  The `--margin` flag exists because of this: the loop keeps iterating until the max score is
  below `threshold - margin` so a noisy checker cannot flip a borderline pass.
- **Retry jitter** (`_retry.py`): draws from a *private* `random.Random()` stream, so a retry
  never advances a caller's reproducible sequence. It affects only when a retry fires, never
  the bytes of the eventual output.
- **Timestamps**: no output surface (JSON, rich panel, or plain render) carries a timestamp,
  so byte-identity is not defeated by the clock.

## What was fixed to get here

- **`t5_paraphrase` sampled path never seeded torch** (fixed in this slice). `untell_text`
  seeds Python's `random`; torch's global RNG was left at its OS-entropy seed. MEASURED
  before the fix: two fresh processes, same input, same seed, `T5ParaphraseRewriter(
  sample=True)` produced 320 bytes vs 304 bytes. `local_policy` had the same defect and was
  fixed earlier the same way: `torch.manual_seed(_next_torch_seed())` before each
  `generate(do_sample=True)`, drawing the seed from the already-seeded `random` module so
  best-of-N still samples N different candidates. The fix is per-generate, not per-run:
  seeding once per run would collapse best-of-N into one draw (measured: 33% -> 0%
  still-flagged).
- **First-call model loads draw from the RNG** (documented in
  `test_the_loop_is_reproducible.py`): lazy model loading consumes draws from the global
  stream, so the first call in a process differs from later calls at the same seed. It does
  not break the cross-process contract — every fresh process pays the same loading cost in
  the same order — which is exactly why the reproducibility test compares fresh processes
  rather than warm ones.

## How to run the proof

```
pytest tests/test_reproducibility_across_processes.py
```

Subprocesses run with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, so the test cannot
depend on the network; the sampled-T5 case additionally requires the model in the HF cache
and reports a skip (not a failure) when it is absent.

## Manifest mode (`--manifest PATH`)

The contract above is **operable** through `untell humanize --manifest PATH`, which writes a
JSON manifest of one run (issue #31):

```json
{
  "manifest_version": 1,
  "untell_version": "0.3.0",
  "input_sha256":  "...",
  "output_sha256": "...",
  "seed": 42,
  "rewriter": "composite",
  "tier": "lite",
  "threshold": 0.0,
  "pre_max": 0.4846,
  "post_max": 0.2121,
  "iterations": 1,
  "determinism": "reproducible",
  "determinism_reason": "same input + seed reproduce identical bytes ..."
}
```

- `input_sha256` / `output_sha256` pin the exact bytes that went in and came out; `seed`,
  `rewriter`, `tier` and `threshold` are the four inputs those bytes depended on. `pre_max` /
  `post_max` record the detector maxima so a reader sees the score moved.
- **`determinism` is classified honestly**, on the same line the table above draws: remote
  rewriters (`anthropic` / `openai`) and `--browser` detectors are marked
  `"non-deterministic by design"`, everything else `"reproducible"`.
- The manifest carries **no timestamp** (`determinism.md` bans clock stamps from output
  surfaces), so for a reproducible run the manifest file is itself byte-identical across
  runs — pinned by `tests/test_manifest_mode.py::test_manifest_is_byte_identical_across_processes`
  in fresh processes, the same way the loop output is.
- `pytest tests/test_manifest_mode.py` verifies the field set, the determinism classification,
  and the byte-identity contract.
