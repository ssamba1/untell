# Test runtime tiers and the slow-test manifest

Measured 2026-08-17 on the wave-5 machine (Windows 11, `./.venv/Scripts/python.exe`,
torch 2.12.1+cpu, HF cache warm). Method: `pytest --durations` per tier; slow numbers
are from `pytest -m slow --durations=0`, fast numbers from `pytest -m "not slow" --durations=30`
with `UNTELL_LITE_NO_TORCH=1`. Issue #19.

## The three tiers

| Tier | Command | What runs | Purpose |
|------|---------|-----------|---------|
| **fast** | `pytest -m "not slow"` (with `UNTELL_LITE_NO_TORCH=1` locally) | Every test that does not load a real ML model: unit tests, lite-scoring tests, invariants, CLI, docs claims, audit. No torch needed. | CI `lite` job + local iteration; answer in minutes. |
| **slow** | `pytest -m slow` | The battery below: tests that load real detectors (RoBERTa-class, GPT-2, sentence-transformers/NLI, T5, local judge) or exhaustively sweep corpora/codepoints. Needs torch + cached models. | CI `full` job; the real-workload guarantees the fast suite cannot make. |
| **full** | `pytest` (everything) | fast + slow, one process. | CI `full` job; the historical 2h17m figure (issue #19) predates the marker split. |

## Runtime budget (measured)

| Tier | Tests | Wall time |
|------|-------|-----------|
| fast (lite) | ~8400 | ~__MIN__ |
| slow | __COUNT__ | ~__MIN__ |
| full (sum of the two measured runs) | ~8655 | ~__MIN__ (measurement overhead + model load warm cache) |

CI `full` additionally pays install + model download (cached via
`actions/cache` on huggingface) + `untell detector-audit` + `untell-audit` —
those are install/audit steps, not test time.

History: wave-3 slice 3 measured 85 fast + 7 slow tests at ~12 min slow. The suite has
since grown ~100x in the fast tier (8393 fast tests at wave-5 start); the slow battery
grew with the real-workload guarantees each wave added.

## Slow-test manifest

Each test below is marked `@pytest.mark.slow` (or module-level `pytestmark`). The marker
exists so CI and local iteration get an answer in minutes (`-m "not slow"`) while `full`
still runs everything. Run times are from the 2026-08-17 measurement, warm HF cache.

| Test | Why it is slow | Measured |
|------|----------------|----------|
| test_the_ensemble_agrees_on_the_corpus | Real-text corpus measurement at the sample size that produced the published table (ensemble scoring over many documents). | __T__ |
| test_the_full_tier_still_finds_it[x2 params] | Loads the real full-tier detector stack to prove an embedded AI section survives full-tier scoring. | __T__ |
| test_batched_detector_identity (module) | Loads real detectors; asserts batched == unbatched scoring identity on real model output. | __T__ |
| test_full_tier_is_used_when_the_full_stack_actually_loads | Loads the real full-tier detectors to score a probe through the CLI. | __T__ |
| test_minimal_valid_invocation_slow[xN] | CLI conformance matrix entries whose spec is `slow` — the ones that load real models. | __T__ |
| test_no_codepoint_anywhere_disagrees | Exhaustive: every codepoint in every doc, hidden-vs-scrub agreement. | __T__ |
| test_detectors_full (module) | Every test here loads a real model (detector ensemble). | __T__ |
| test_end_to_end_guarantees (module) | Every test here loads a real model and runs full pipelines over corpora. | __T__ |
| test_real_model_vetoes_inversion_but_not_register_shift | Loads the real NLI model (sentence-transformers + torch). | __T__ |
| test_the_score_still_discriminates | Model-backed humanness scoring on the documents the abstain logic gates. | __T__ |
| test_a_model_backed_run_stays_quiet | Runs the model-backed humanness path (torch) to check its warning behavior. | __T__ |
| test_local_judge_can_still_be_opted_into | Instantiates the real local-judge model (torch/transformers). | __T__ |
| test_no_markdown_form_changes_a_verdict | Corpus scoring (20+ documents) through real detectors across markdown forms. | __T__ |
| test_the_caveat_stays_quiet_when_gpt2_scored_the_sentence | Scores through the real GPT-2 path. | __T__ |
| test_sentence_targeting_* (5 tests) | Corpus fixture: scores real AI/human sentence sets through the detector ensemble, then measures separation/ceiling/flags. | __T__ |
| test_the_lite_caveat_still_quotes_the_truth (3 tests) | `rates` fixture: scores the corpus to measure flagged vs above-threshold rates. | __T__ |
| test_the_human_half_keeps_its_meaning_even_when_edited / test_the_loop_does_edit_the_human_half | Full-tier loop over real detector scores on a mixed corpus. | __T__ |
| test_the_loop_still_works_past_the_scoring_cap (module) | Loop scoring past the cap boundary on real detector output. | __T__ |
| test_the_output_satisfies_its_invariants (module) | Re-scores 12 docs per corpus to assert output invariants on real scores. | __T__ |
| test_the_pinned_detector_is_named_correctly (module) | Loads real RoBERTa-class detectors; deselected by the fast suite. | __T__ |
| test_the_skill_scripts_actually_run_with_nothing_installed (module) | Subprocess battery (~32s alone); not model-bound — spawns error under full-suite load, so it is deselected from the fast suite. | __T__ |
| test_repeated_draws_are_identical_without_sampling | Real T5 rewriter model: checks the sampling flag actually varies output. | __T__ |
| test_unrankable_* (3 tests) | `corpus` fixture: scores documents through real detectors to check the unrankable gate. | __T__ |

Rationale for the split: every slow test either (a) loads a real ML model into memory
(seconds each, GBs), or (b) exhaustively sweeps a corpus/codepoint space that takes
minutes by design. Neither can run in the lite job — the zero-dependency path CI must
keep proving — so the marker keeps the fast suite answerable in minutes while the full
job still enforces the real-workload contracts.