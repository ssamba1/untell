# For a human

Everything the loop found but is not allowed to act on, plus everything it did that someone
should know about. Append only — the loop never edits or removes an entry, and never marks
one resolved. A human does that.

Format, newest last:

```
## <date> pass <n> <AMBER|RED> — <one line>

WHAT   what was found, or what was changed
RAN    the exact command
SAW    its output, trimmed to the part that matters
WHY    which envelope band and why it landed there
NEXT   the smallest thing a human could do about it
```

An entry is worth writing when it is specific enough to act on without rerunning the pass.
"Detector scores look off" is not an entry. "`untell-score` flags 19 of 20 human paragraphs
at the shipped threshold, command and output below" is.

---

## 2026-08-13 program run — AMBER — an env var the code reads is undocumented

WHAT   `untell-audit` fails one of its 40 claim checks, so the whole audit exits 1.
RAN    python -m untell.scripts.audit --json
SAW    FAILED: every UNTELL_*/HUMANIZE_* variable the code reads is documented
       -> undocumented: ['UNTELL_POLICY_WHOLE_DOC']
WHY    The fix is a line of documentation, and the files that carry documentation are RED.
NEXT   Document UNTELL_POLICY_WHOLE_DOC where the other UNTELL_* variables are described.
       The other 39 checks pass and 158 claims are attributed.

## 2026-08-13 program run — AMBER — two research recipes cannot record

WHAT   `lite-hc3-ensemble` did not finish inside 90 minutes (3x its 30-minute estimate), and
       `detector-audit` exits 1 for a reason not yet identified.
RAN    python .claude/research.py program --budget 3
SAW    "REFUSED to record: lite-hc3-ensemble did not finish inside 90 minutes"
       "REFUSED to record: detector-audit exited 1"
WHY    Both refusals are correct — a partial measurement is not a measurement — but the
       rewriter family is now incomplete, and the detector-at-threshold recipe is unusable.
NEXT   Ensemble: raise its estimate to match reality (composite took 841s, targeted 810s;
       ensemble runs every backend, so ~1h is plausible) or drop its n. Detector audit:
       reproduce with `python -m eval.detector_audit --pairs 20 --dataset hc3 --json` and
       read the failing field before changing anything.

## 2026-08-13 me2 worker — AMBER — detector-audit failing field identified; both recipe estimates corrected

WHAT   Reproduced `detector-audit` exactly as the queue entry asked. The failing field is
       `broken: ["mage"]`. mage is MISCALIBRATED at the SHIPPED threshold: on 20 HC3 pairs
       (layout collapsed) human mean 0.3477, FPR 0.35 at threshold 0.30, against MAX_FPR 0.20.
       AUROC 1.0, TPR 1.0 — it separates perfectly and still flags a third of human text.
       This is the README's documented number (33% HC3, 0% RAID, 3.3% MAGE), so the audit is
       CORRECT and pass 28's "eval load-order issue" diagnosis was wrong. The recipe can never
       record because `research.py` refuses any non-zero exit and `detector_audit.main` returns
       1 whenever `broken` is non-empty. The recipe's own reason-for-existing is to catch
       exactly this, so the fix is either (a) let the recipe record a finding, or (b) run the
       audit on a corpus where mage is calibrated (RAID). Both are human calls: (a) changes
       what a refusing recipe means, (b) changes what the recipe measures.
RAN    python -m eval.detector_audit --pairs 20 --dataset hc3 --json
SAW    broken: ['mage']; mage MISCALIBRATED hm=0.3477 am=1.0 auroc=1.0 fpr=0.35 tpr=1.0;
       4 other detectors OK/OK_SEPARATED at paragraph granularity
WHY    AMBER — the failing field is identified but the two candidate fixes change either the
       harness's refusal semantics or the recipe's corpus, both of which a human should pick.
NEXT   Pick (a) or (b) above. (a) is one line in research.py: treat a non-zero exit with
       parseable JSON as a recordable finding when the recipe declares no liveness fields.
       (b) is one line in research.py: --dataset raid. Meanwhile both wrong estimates are
       fixed in this commit: lite-hc3-ensemble 30->60 (measured: composite 841s + targeted
       810s + structural 357s + surgical 204s; ensemble runs all), claims-audit 15->45
       (pass 8 killed it at 2x estimate with the audit unfinished; 45 checks incl. pytest
       --collect-only and per-script --help subprocesses).

## 2026-08-13 me2 worker — AMBER — claims-audit's one remaining failing check is a stale module count in a RED file

WHAT   `untell-audit` (the claims-audit recipe) fails exactly ONE of 40 checks: "every 'N test
       modules' claim matches tests/" — `docs/why-best-open-repo.md:154` says "325 modules",
       tests/ actually has 334 (333 at the time of the original entry; worker me added
       test_mcp_real_round_trip.py + test_spelled_decimals_and_big_scales.py). Drift is 9, the
       audit's band is 5. The earlier queue entry about
       UNTELL_POLICY_WHOLE_DOC is already resolved (README line 800 documents it; the check
       passes). The test-count claim (6930) is within the 10% band on a clean run (6964 with
       UNTELL_LITE_NO_TORCH=1, 6980 without) — it only failed in an earlier run because the
       audit's internal pytest --collect-only subprocess raced the loop's own parallel pytest
       suite and collected 1735. The audit runs in ~7 min, not >30.
RAN    python -m untell.scripts.audit --json   (twice; second run on an idle machine)
SAW    ok: False, 40 checks, 1 fail: "docs/why-best-open-repo.md: says 325 test modules,
       tests/ has 333 — stale by more than 5"  [now 334 in the merged tree]
WHY    AMBER — the fix is updating a number in docs/why-best-open-repo.md, which the envelope
       marks RED (a published number in a human-owned file). The audit is correctly refusing.
NEXT   Edit line 154: "325 modules" -> "334 modules" (or the count at merge time — the
       concurrent session's uncommitted tree already shows 339). Optionally refresh the test
       count to 6964 (UNTELL_LITE_NO_TORCH=1) / 6980 (full). Then claims-audit records.

## 2026-08-13 me3 worker — L6 claim verified (pass 56)

CLAIM   untell/SKILL.md: "0.76 for semantic embeddings, 0.50 for the lite
        token-overlap fallback" (recommended_bar per metric).
RAN     PYTHONPATH= python -c "from untell.scripts.quality import method,
        recommended_bar; ..." — method()='embedding', recommended_bar()=0.76.
        MATCH. Also reproduced README's negation-flip example: "runs faster"
        -> "runs slower" similarity 0.9825 (README says 0.983) vs 0.76 bar,
        passes=True without NLI — consistent with "ADMITTED without it."
SAW     No drift. Claim verified.

## 2026-08-13 pass 56 re-audit AMBER — the pass-42 T16 record's premise is false

WHAT   The T16 (API server) pass-42 record says "FastAPI surface itself untestable
       (pydantic_core broken in env, tests skip)". That is an environment artifact, not a
       repo property: a polluted PYTHONPATH (hermes desktop app injecting its own venv's
       site-packages, whose pydantic_core is broken) was shadowing the project venv. With
       `PYTHONPATH=` cleared, the FastAPI surface imports and tests fine.
RAN    PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/test_detector_errors_never_ride_inside_the_scores.py -k humanize_endpoint
SAW    1 passed (67s). Also probed /score with 8 hostile bodies (empty, missing field, wrong
       type, whitespace, unicode-only, null byte, 1MB): no 500s; empty/whitespace ->
       flagged=False, scored=False, warning; malformed -> 422. Invariant holds.
WHY    AMBER: the record's reasoning is wrong, but its verdict (clean) is correct, so there
       is no code defect to fix — yet the false premise would make a future pass skip T16
       again. Anyone running the audit loop outside this desktop app should NOT see the
       "untestable" failure the record describes.
NEXT   Nothing to fix in code. If a future T16 pass reports pydantic_core errors, clear
       PYTHONPATH (or run outside the Hermes desktop app) before treating it as a repo defect.

## 2026-08-13 pass 58 L9 AMBER — lite-hc3 is deterministic; the L9 knob lane has no working instrument

WHAT   Calibrated lite-hc3 (two identical runs): DETERMINISTIC, all deltas
       +0.000000 (pre/post flagged rate, pre/post mean max), spread 0.0014. The
       experiment lane now REFUSES lite-hc3 ("a knob that works and a knob that
       does nothing look the same through it"). lite-builtin is also recorded
       deterministic. Every L9 knob pass assigned through lite-hc3 (18, 38, 58)
       would have measured through an instrument that cannot detect an effect.
RAN    .venv/Scripts/python.exe .claude/research.py calibrate lite-hc3
SAW    "lite-hc3 is DETERMINISTIC: identical output with nothing changed. Good for
       liveness, useless for comparison"; experiment run quality-bar-0.70
       --recipe lite-hc3 -> REFUSED with the deterministic message.
WHY    AMBER: measurement data (instruments.json, measurements.jsonl) — committed,
       but no knob value was adopted and no tuning constant changed.
NEXT   Calibrate a recipe that moves (e.g. full-hc3-composite, ~90 min x2, or
       lite-hc3-surgical) before trusting any future L9 knob reading. Until one is
       calibrated, L9 passes will refuse — that is the harness working, not a bug.

## 2026-08-13 me2 worker — AMBER — claims-audit blocker RESOLVED; verify the recipe records now

WHAT   `untell-audit` now passes 40/40 (exit 0, ok: True) on main after the module-count fix
       (docs/why-best-open-repo.md now says 6982 tests / 334 modules, committed). The recipe
       should record on its next `research.py run claims-audit`. Runtime confirmed ~7 min on
       an idle machine (was mis-reported as ">30 min" by pass 8 under machine contention).
RAN    python -m untell.scripts.audit --json (twice: 423s, 443s; exit 0 both)
SAW    ok: True, 40 checks, 0 failures, 158 attributed claims
NEXT   Run `python .claude/research.py run claims-audit` to close the L8 row. The two earlier
       me2 queue entries (detector-audit failing field, claims-audit stale count) stand as-is.

## 2026-08-13 pass 74 L6 AMBER — docs/why-best-open-repo.md test count drifted again

WHAT   Line 154 claims "6982 tests, 334 modules". Actual (measured just now,
       UNTELL_LITE_NO_TORCH=1 pytest --collect-only -q): **7004 tests**. The fleet's
       earlier note said refresh to 6964/6980; this rotation's killing tests
       (test_env_*, test_retry_class_name_alone, fleet's MCP/decimals/NaN suites)
       pushed it past both figures. Count moves every time a test lands.
RAN    UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe -m pytest --collect-only -q
SAW    7004 tests collected in 60.93s
NEXT   Edit line 154: "6982" -> "7004" (and re-verify the module count: 409 .py files
       under untell/eval/tests minus worktrees — the "334 modules" figure needs the
       same refresh). Then claims-audit records.

## 2026-08-13 pass 88 L8 AMBER — full-hc3-composite headline: the default rewriter cannot move the full-tier score

WHAT   First measurement of the headline recipe (full tier, composite rewriter, 6 real HC3
       documents, 3 repeats, 2 workers): pre_flagged_rate 1.0 -> post_flagged_rate 1.0,
       pre_mean_max 1.0000 -> post_mean_max 1.0000. The rewriter WAS live (rewrote 18
       spans, rewriter_available=True) yet NO candidate ever beat the baseline.
RAN    .venv/Scripts/python.exe .claude/research.py run full-hc3-composite
SAW    appended to measurements.jsonl (1 run of full-hc3-composite)
WHY    AMBER — this is the mage-saturation failure measured end to end at the flagship
       recipe: mage returns exactly 1.0 on AI genre text, the ensemble takes max, so every
       candidate scores 1.0 and `cand < best` never fires. The README documents this
       (selection_key comment: 'composite, the DEFAULT rewriter, returned its input
       byte-identical on 6 of 6 documents'), and the (max,mean) key fixed it for the
       selector — but mean is also ~1.0 when every detector saturates, so the OUTER loop
       sees no improvement and stops. The pipeline is honest about it (flagged stays True,
       no fake pass), but the tool's headline promise — 'untell humanize' reduces the
       score — does not hold at full tier on real AI text with the default rewriter.
NEXT   Human decision needed: (a) accept as documented limitation, (b) drop mage from the
       default full ensemble (README sweep shows it weakly dominates to drop hc3_roberta,
       and mage is HC3-specific saturated), or (c) weight the max aggregation. Do not
       adopt from one run — this needs the repeats/family sweep first.

## 2026-08-14 me2 worker — AMBER — tells-raise-score tests were torch-path-dependent; pinned stdlib; GPT-2 lite path question stands

WHAT   tests/test_adding_a_tell_does_not_lower_the_score.py failed 3-4 tests on this torch
       machine ("2 of 10 HC3 docs scored LOWER with tells added"; salt 0.317 -> 0.286). The
       docstring numbers (salt 0.678 -> 0.748, bridge 0.631 -> 0.727, receipts 0.377 -> 0.541)
       reproduce EXACTLY with UNTELL_LITE_NO_TORCH=1 — the test was written against the stdlib
       lite path, but tier="lite" auto-upgrades to GPT-2 math when torch is importable, and the
       GPT-2 path violates the invariant. Test verified red-at-its-own-commit (471847b).
FIX    Pinned the stdlib path with the repo's stdlib_lite fixture (4 tests). Red-without proven
       (stash -> 3 salt failures on torch machine; restore -> 13/13 green incl. slow corpus test).
OPEN   Product question, NOT fixed here: on the GPT-2 lite path, injecting 8 catalogued tells
       LOWERS the score on some docs (salt -0.031). The full-tier docstring table shows the
       ensemble max rises 20/20 but roberta_openai 11/2/7, fast_detectgpt 11/9/0, hc3_roberta
       10/1/9 — several members are directionless on this manipulation. Whether the GPT-2 lite
       path's directionality is acceptable is a human/scoring call (RED band).

## 2026-08-13 pass 172 L8 AMBER — full-hc3-max: best-of-all-backends beats composite but stays flagged

WHAT   Second headline measurement (full tier, max rewriter, 6 real HC3 docs, 3 repeats,
       2 workers): pre_flagged_rate 1.0 -> post_flagged_rate 1.0, pre_mean_max 1.0000 ->
       post_mean_max 0.9758. Rewrote 18 spans, rewriter live. Unlike full-hc3-composite
       (1.0 -> 1.0, zero movement), the max selector DID find candidates that beat the
       mage-saturated max — first measurable evidence the (max,mean) selection key can
       partially defeat saturation.
RAN    .venv/Scripts/python.exe .claude/research.py run full-hc3-max
SAW    appended to measurements.jsonl (1 run of full-hc3-max)
WHY    AMBER — family comparison now exists:
         composite  1.0 -> 1.0      (no improvement)
         max        1.0 -> 0.9758   (score moved, still flagged)
       The mean-max moved but the flagged rate did not: at best-of-all-backends the tool
       still cannot clear the 0.45 verdict cut on real AI text. This quantifies the mage
       saturation wall from both sides. Same NEXT options as the composite entry: drop
       mage from the default ensemble / weight the max / accept as documented.
NEXT   Human decision (same as full-hc3-composite entry). Do not adopt from single runs —
       the tiers family (lite-hc3 vs full-hc3-composite) and a rewriters sweep exist for that.

## 2026-08-13 pass 210 L8 AMBER — full-hc3-neural: complete rewriter family comparison

WHAT   Third headline measurement (full tier, neural rewriter, 6 real HC3 docs, 3 repeats):
       pre_flagged_rate 1.0 -> post_flagged_rate 1.0, pre_mean_max 1.0000 -> post_mean_max
       0.9999. The neural (MT back-translate) rewriter is live but cannot beat the
       mage-saturated max either.
FAMILY (all full tier, n=6, 3 repeats, real HC3):
         composite  1.0 -> 1.0      (zero movement)
         max        1.0 -> 0.9758   (small movement — best-of-all-backends partially defeats saturation)
         neural     1.0 -> 0.9999   (negligible movement)
       All three stay flagged at the 0.45 verdict cut. The mage saturation wall is
       confirmed from every direction: the default composite selector cannot improve the
       score, best-of-all-backends barely can, MT cannot.
NEXT   Same human decision as the other two entries: drop mage from the default ensemble /
       change the (max,mean) selection key / accept as documented. Do not adopt from single
       runs. This family is now COMPLETE — the L8 lane has its full comparison set.

## 2026-08-13 pass 257 L8 AMBER — lite-hc3: post_mean_max moved -0.026 (outside +-0.020 band)

WHAT   4th run of lite-hc3: pre_flagged_rate 1.0 -> post_flagged_rate 1.0, pre_mean_max
       0.6362 -> post_mean_max 0.5625. Against run 3: post_mean_max 0.589 -> 0.562
       (-0.026, MOVED beyond the +-0.020 noise band). pre numbers identical (+0.000).
WHY    AMBER — the rewriter moved the score DOWN by more than noise on this run (better
       rewriting or a draw that happened to land better). The flagged rate did not move
       (1.0 both), so the headline verdict is unchanged; only the magnitude of the
       post-rewrite score improved. Direction is consistent with the tool's intent.
NEXT   Not an adoption trigger by itself — the band rule exists to catch drift, and a
       single -0.026 could be a lucky draw at n=10. Watch the next lite-hc3 run before
       treating this as a real improvement in rewriter strength.

## 2026-08-13 pass 258 AMBER — lite-hc3 calibration stale: determinism claim contradicted

WHAT   instruments.json records lite-hc3 deterministic=True spread=0.0014 (from the
       fleet's 2-run calibration). The pass-257 4th run moved post_mean_max -0.026
       beyond the +-0.020 noise band — a recipe that was 'identical run to run' just
       differed by more than the band. The determinism claim is stale.
NEXT   Re-run the calibrate step (or accept that lite-hc3 is not deterministic and needs
       3+ runs per measurement). Until then L9 refusals cite a possibly-wrong reason.

## 2026-08-14 me2 worker — AMBER — lite-hc3-ensemble is a >3h measurement; estimate raised to 150m

WHAT   Third attempt at lite-hc3-ensemble (n=10, repeats=3, lite, all free backends +
       selection): killed at the 180-minute budget (2x the 90-minute estimate) with the
       measurement still unfinished. First run killed at 90m (contended), second at 120m
       (contended), third at 180m (solo start, ~1h of light sibling holdout contention).
       Each repeat sweeps surgical (~3.4m), structural (~6m), composite (~14m), targeted
       (~13.5m) and selection re-scores candidates — 3 repeats genuinely exceeds 3 hours.
RAN    python .claude/research.py run lite-hc3-ensemble (3 attempts, all killed at budget)
SAW    >180 minutes, no measurement recorded (REFUSED: partial measurement is not a measurement)
NEXT   Options for a human: (a) accept the 150m estimate and run it overnight via the fleet
       runner (240m budget covers it), or (b) shrink the recipe to n=6 or repeats=2 so a
       session can complete it. The estimate was corrected 30->60->90->150 with measured
       evidence each time; the recipe's shape (4 backends x 3 repeats + selection) is the
       cost driver, not the machine.

## 2026-08-14 pass 394 note — lite-hc3-ensemble retry refused at 180min (contention, not a bug)

WHAT   My fleet attempt at lite-hc3-ensemble (assigned pass 288) hit the 180-min
       kill budget under machine saturation (the fleet's own identical run plus
       other heavy recipes sharing the box). Harness correctly REFUSED the partial
       — pass 394 records this. Same class as the lite-hc3 calibration failure
       (EXIT=127) earlier today: both need a solo machine.
NEXT   Re-run lite-hc3 calibration (settles pass-258 determinism contradiction) and
       lite-hc3-ensemble only when no other heavy recipe is running. Watch
       Get-Process python* CPU totals before launching; ~40min and ~90min solo
       budgets respectively.

## 2026-08-13 pass 429 AMBER — detector-audit recipe fails under Hermes-venv shadow; runs clean with PYTHONPATH=

WHAT   `research.py run detector-audit` exited 1 and refused to record: the transformers
       load path (fast_detectgpt) dies on pydantic_core._pydantic_core missing — the
       known Hermes-desktop-venv shadow artifact (memory note). Same class as the
       FastAPI/API-test failures. With PYTHONPATH= cleared the same command completes:
       20 HC3 pairs, layout_shortcut=1.0, mage listed in `broken` (documented
       saturation), roberta_openai AUROC 0.9283 TPR 1.0 FPR 0.567, radar/local_judge/
       binoculars UNAVAILABLE (heavy/opt-in, not installed).
NEXT   If detector-audit is needed in a cron/recipe context, run it with PYTHONPATH=
       cleared. Numbers above are from the manual run (not appended to measurements
       because the harness refused — correct behavior, no invented rows).

## 2026-08-14 me3 worker — L3 found 2 stale numerals tests; fixed

WHAT   The durations re-audit run surfaced 7 failures. 2 were REAL stale-test defects
       left by fleet commit 524e6a7 ("spelled multi-scale numbers parse as one quantity"):
       - test_thousands_combined_with_hundreds_are_a_known_limit pinned the OLD broken
         parse (["1002","40"]) after the code correctly returned ["1240"]. Renamed to
         test_thousands_combine_with_hundreds_into_one_quantity and updated to the fixed
         value.
       - the fraction parametrize case of test_the_remaining_gaps_are_recorded was xfail
         ("fractions are not numerals") but the gap CLOSED: missing_numbers now reports
         ['1'] for "One third" -> "Half". Converted to a real assertion
         (test_a_fraction_change_is_now_caught). Removed the fraction case from the xfail
         parametrize; unit/ordinal stay xfail (still out of scope).
       The other 5 (style/caveat) were memory-contention artifacts of the fleet's
       concurrent lite-hc3-ensemble run — all pass on a free box.
RAN     pytest tests/test_a_magnitude_word_is_part_of_the_number.py tests/test_spelled_numbers.py
SAW     27 passed, 2 xfailed. Suite 5769 -> 5770.
WHY     AMBER (test rename + xfail scope change are human-owned per the guard).
NEXT    None.

## 2026-08-14 pass 531 L6 AMBER — README MCP tool list stale: 5 documented, 8 registered

WHAT   README.md:149 says the MCP server "exposes score/sentences/untell/verify/scrub
       as tools" (5 tools). Live registration (mcp_server._server().list_tools())
       returns 8: ceiling, compare, score, scrub, sentences, tells, untell,
       verify_commercial. Undocumented: ceiling, compare, tells; the documented
       "verify" does not exist under that name (it is verify_commercial).
WHY    AMBER — documentation understates the MCP surface. The README's phrase
       "verify/scrub" names 2 of 8; a client that discovers tools will find 3 extra
       (plus a renamed verify). Not a functional defect; doc drift.
NEXT   L6 does not edit docs (established rule). Human: update README line 149 to
       list the real 8-tool surface.

## 2026-08-14 lite-hc3 MOVED — determinism contradiction confirmed (pass-258 AMBER resolved)

WHAT   Calibration retry (research.py run lite-hc3, 3 repeats, EXIT=0) appended a 5th
       run to measurements.jsonl. The recipe the pass-258 AMBER flagged as
       contradicted moved AGAIN, confirming the contradiction is real:
         pre_flagged_rate       1.000 -> 1.000  (+0.000, noise)
         post_flagged_rate      1.000 -> 1.000  (+0.000, noise)
         pre_mean_max           0.636 -> 0.636  (+0.000, noise)
         post_mean_max          0.562 -> 0.589  (+0.026, MOVED)
       band: +/-0.020  (2x the wider of the two runs' reported spread)
       Result this run: pre_flagged_rate 1.0, post_flagged_rate 1.0,
       pre_mean_max 0.6362, post_mean_max 0.5887.
WHY    lite-hc3 is NOT deterministic at the 0.020 band. The earlier 2-run
       calibration (deterministic=True, spread 0.0014) understated run-to-run
       movement; post_mean_max has now moved twice (+0.026 this run). The L9 knob
       lane's primary recipe CAN see knob effects at the 0.562->0.589 scale, so
       the earlier 'L9 blocked, instrument blind' AMBER is partially lifted: the
       instrument can see movement, but the band must be re-derived from all 5
       runs before trusting any single-pass verdict.
NEXT   Re-derive the noise band from all 5 measurements.jsonl runs; re-run any
       earlier L9 'clean' passes whose verdict sat within the new band; treat the
       committed instruments.json deterministic=True as stale.
## 2026-08-14 me2 worker — RESOLVED — test-module count drift (339 vs 358) — CLOSED 2026-08-14

STATUS   Sibling fixed the docs (registry counts now match: '8 local'/'7 commercial');
         test_every_free_rewriter_actually_rewrites.py 17/17 PASS; audit derivable-checks
         green. Queue entry superseded.

WHAT   Full audit check "every 'N test modules' claim matches tests/" fails:
       docs/why-best-open-repo.md claims 339 test modules, tests/ has 358
       (drift 19 > band 5). Same class as the pass-74 drift (325->334->339...).
       The count keeps drifting because every test file added re-stales it.
RAN    pytest tests/test_audit.py (audit's own derivable-checks test, red)
SAW    every 'N test modules' claim matches tests/: FAILED
NEXT   Fix the RED doc count (sibling/human). Longer-term: the check could accept
       a "last verified" date or the docs could state a range — but that changes
       the check's semantics, which is a human decision.

## 2026-08-14 L9 band re-derived from 5 runs — instrument defect in calibrate

WHAT   5-run analysis of measurements.jsonl lite-hc3 (all committed):
       post_mean_max: run1 0.5871, run2 0.5887, run3 0.5887, run4 0.5625, run5 0.5887
       -> spread 0.0262, stdev 0.0116. pre_mean_max: 0.6362 in ALL 5 runs (spread 0.0000).
       The harness's +/-0.020 band = 2x the wider per-run internal stdev (~0.0014-0.0016),
       which measures WITHIN-run repeat, not run-to-run stability. Run 4 moved 0.0262
       below the cluster — the band understated movement ~10x.
WHY    ROOT CAUSE (research.py calibrate): deterministic = all(v==0) comparing the LAST
       TWO runs only (line 393). Two consecutive runs can both land in the same stable
       cluster (0.5871/0.5887) while the process genuinely moves between clusters (run 4).
       A 'deterministic=True' verdict from a 2-run window is coincidence-prone; the
       instrument's flag is now known-false for lite-hc3.
IMPACT All L9 'REFUSED - deterministic' passes (18, 38, 64, 78, 98, 118, 138, 158, 178,
       198, 238, 258, 276, 278) refused on a stale premise. post_mean_max CAN move
       (0.5625 vs 0.5887), so knob effects at that scale ARE observable -> L9 knob lane
       is re-openable with a corrected band (use 5-run stdev, not last-2 delta).
NEXT   Fix calibrate to compare against the FULL run history (min-max spread or stdev
       across all runs, min 3-5 runs); re-run the L9 knob passes with the corrected
       band; treat instruments.json deterministic=True as stale until then.

## 2026-08-14 verified-unkillable confirmations (search-backed, fleet should not re-hunt)

1. tells.py:1187 both boundaries (start < c_end -> <=, end > c_start -> >=):
   Exhaustive search over all 20x19 pattern-pair permutations x 8 separators
   ('', ' ', ',', ', ', '. ', '\n', '; ', ')', ']') found ZERO touching-span
   pairs. Every pattern pair is separated by at least a word-boundary/space, so
   'end == c_start' is unreachable with real regex spans; overlapping spans
   behave identically under both comparisons. Prior 'no constructible input'
   note VERIFIED CORRECT by the search.
2. io_utils.py:180 sniff length (4 -> 5): read(5) also contains every BOM
   prefix; head.startswith(bom) is identical; non-BOM files don't enter the
   branch. Genuinely equivalent. Note verified.
3. text_split.py:146 autojunk (False -> True): 2000 random-sequence trials over
   varied lengths/alphabets, plus targeted repeated-word constructions: difflib
   get_matching_blocks() is IDENTICAL with autojunk on/off in all cases (CPython
   3.11 implementation resolves popular elements without changing the final
   decomposition). Genuinely equivalent at the observable level. Note verified.

## 2026-08-15 pass 1025 AMBER — ppl-weight-0.40 MOVED (−0.048, beyond band)

WHAT   Full measurement (fresh before+after, ~40min): pre 1.0/0.6362 -> post
       1.0/0.515 — post_mean_max moved -0.048, outside the +/-0.020 band.
       THE FIRST L9 KNOB THAT ACTUALLY MOVED. Every other knob measured this
       session (quality-bar 0.70/0.82, relaxed-sim-0.20, token-bar-0.40,
       contradiction-bar-0.35) was +0.000.
WHY    AMBER per harness rule — one experiment at one corpus (lite-hc3) is a
       reason to look, not a reason to ship. Harness explicitly: "Do NOT
       adopt the value."
NEXT   Human decision: the perplexity-burstiness weight genuinely affects the
       rewrite loop's outcome at lite tier. Candidate for a follow-up
       experiment sweep (0.3/0.5/0.6) or adoption review. Not adopted.

## 2026-08-15 pass 1051 AMBER — threshold-0.40 MOVED (post_flagged 1.0->0.9)

WHAT   Full measurement: threshold 0.30->0.40. post_flagged_rate 1.0->0.9
       (-0.10, beyond band); pre/post_mean_max unchanged (0.6362/0.5625).
       SECOND moving knob this session (after ppl-weight-0.40 -0.048).
WHY    AMBER per harness: "Never adopt from one run — this one moves every
       claim." The shipped threshold is load-bearing: raising it to 0.40
       changes the rewrite loop's stopping behavior (10% of AI text stays
       flagged after rewriting).
NEXT   Human decision: threshold sensitivity is real. The 0.30 shipped value
       was calibrated; a sweep (0.25/0.35/0.40) would map the tradeoff.
       Not adopted.

## 2026-08-15 pass (L6/full-suite) AMBER — docs/why-best-open-repo.md:154 count stale
RESOLVED + CORRECTED (my count was wrong): tests/ has 458 test_*.py modules
(460 .py total incl __init__.py + conftest.py). The doc's "7436 tests, 458 modules"
is CORRECT — git-tracked .py = 460, audit sees understatement by 2, within
_MODULE_DRIFT=5. My earlier "456" was ls tests/test_*.py missing 2 files.
Fleet's edit was right; audit derivable-checks pass (0 failures). No drift.

## 2026-08-15 full-suite pass — docs/why-best-open-repo.md:154 STILL WRONG (overstated)
SUPERSEDED by the correction above: 458 modules is the correct on-disk count.
The fleet's number was right; my queue entries were based on an incomplete ls.
Audit.run() shows 0 failures. Entry closed.

## 2026-08-14 structural.py:1691 (fresh or options -> and) verified-unkillable

Data check: the gerund-unsafe tables (_GERUND_UNSAFE, _GERUND_OBJECT_UNSAFE)
contain ONLY single-synonym _SYN words ('involves'->1 syn, 'requires'->['needing']).
With a single synonym, fresh is either [syn] (unspent) or [] (spent), and
`(fresh or options)` === `(fresh and options)` in every case:
  - fresh=[syn]: both iterate [syn]
  - fresh=[]: or -> options=[syn] (usable after filter), and -> fresh=[] (empty
    -> return original) — but the single syn is always either usable (same
    result) or in unsafe (both empty -> both return original).
No divergent path exists with the current data. Verified by scanning both
tables for words with >=2 _SYN entries: zero found. The row stays UNKILLABLE
for a data-shaped reason, not an assumed one. If _SYN ever gains a multi-syn
gerund word, re-open.

## 2026-08-15 subagent-swarm L6 findings (RED-band, human edit required)

1. README.md:824-825 — "mage is always null, auto-excluded". STALE: mage.py:44-76 normalizes id2label and loads directly; live-verified MAGE runs (score 0.9999+ on clean text). free-ceiling-measured.md:191-194 confirms "MAGE runs".

2. README.md:787 — bind default "127.0.0.1:8000". STALE: api_server.py:1053 default host is 0.0.0.0 (UNTELL_HOST env fallback), port 8000. docs/api-server.md:21 correctly says 0.0.0.0. Security-relevant (all interfaces vs localhost).

3. docs/why-best-open-repo.md:148 — "Multiple real detectors in the loop (14)". STALE: 15 registered (all_detectors() returns 15; the doc's own line 77 says 8 local + 7 commercial = 15).

4. docs/free-ceiling-measured.md:440 — "_CAL_MID = -0.03, _CAL_SCALE = 0.12". STALE: actual untell/detectors/fast_detectgpt.py:53-54 = _CAL_MID 0.20, _CAL_SCALE 0.08; the doc's own Result 8 table (:599-600) lists the correct values and the file self-corrects at :7649.

5. README.md:538 — "flags 65% of HUMAN text" (lite at 0.30). STALE: project's own re-measurement found 60% (free-ceiling-measured.md Result 24, "60
## 2026-08-15 me2 worker — AMBER — test-module count drift (4th occurrence): docs say 458/7436, live is 482/7527

docs/why-best-open-repo.md:154 claims "7436 tests, 458 modules". Live probe (2026-08-15):
- tests/ has **482** test modules (files) — +24 over the claim
- pytest --collect-only collects **7527** tests — +91 over the claim
- `python -m untell.scripts.audit --json` → check "every 'N test modules' claim matches tests/" FAILS
- Same defect class as the 3 prior drifts (356→358, 339→358, and the "test modules" phrase fix): the count is a RED-file constant that drifts as guard tests accumulate. RED file, human-owned — needs a doc edit. Suggest the doc either drop the exact count or the audit recipe be run before docs edits.

## 2026-08-15 me2 worker — RESOLVED — lite-hc3-ensemble measured twice by fleet (13918.6s / 7412.1s); run-to-run consistent to 4dp


Fresh measured evidence (2026-08-15, solo, no contention): ensemble lite measurement killed by the 1750s harness timeout at EXIT 124. Output shows 3 backend models loaded (256/256, 257/257, 105/105 layers) with the file frozen at 1387 bytes for the remainder — the run was still in model-loading phase when killed. This is the 4th killed attempt (90m, 90m, 180m, 29m+); each confirms the ensemble's ~8 sequential backend loads make the true measurement >2.5h on this machine. The 150m estimate is now CONFIRMED conservative, not just corrected. Recipe shrink (n=6 or repeats=2) or overnight fleet run still required — human decision.

## 2026-08-15 slice-14 worker — AMBER — new `untell explain` subcommand (new CLI surface + pyproject.toml + SKILL.md touched)

New capability shipped: `untell explain "text"` (also `untell-explain`, `python -m untell.scripts.explain`) reports every span the preserve-lock would freeze, which rule(s) locked it, and the documented rationale — the inspection surface the opaque mask never had. Over-locking ("a frozen span is prose the rewriter cannot improve, silently, forever") is now checkable before a rewrite.

Envelope note: this is a NEW CLI surface (subcommand + console script entry in pyproject.toml) and touches untell/SKILL.md, so it is AMBER — queued here in the same commit per the envelope. No existing command, flag, exit code, error message, or signature changed; `lock()`/`restore()` behavior is byte-identical (pinned by tests). Internal refactor: `preserve._collect_spans` now delegates to the new `_collect_labeled_spans` so lock and explain share one source of truth.

Files: untell/scripts/explain.py (new), tests/test_explain.py (new, 40 tests), untell/scripts/preserve.py (labeled-collector refactor), untell/scripts/cli.py (subcommand + one-liner), pyproject.toml (untell-explain entry), untell/SKILL.md (usage note after preserve-lock step).

## 2026-08-15 slice-19 worker — RED — docs/why-best-open-repo.md drift: test count, console-script count, detector count (guard-blocked, edits sit in working tree)

docs/why-best-open-repo.md is in the guard's RED_FILES, so the three repairs below are queued (the edits are applied in the working tree, unstaged, for a human to commit after review):

1. Line 154 "Automated tests | ✅ **7530** tests, 483 modules" — STALE. This is the exact check `untell-audit` runs; `untell-audit --fix-counts` (the repo's own sanctioned repair) rewrites the cell to the live counts. Refreshed at queue time (2026-08-15): **7693 tests, 498 modules** (a lite collection, UNTELL_LITE_NO_TORCH=1). NOTE: the fleet is adding test modules continuously — the count was 489 at first probe and 498 an hour later, so re-run `untell-audit --fix-counts` immediately before committing. tests/test_docs_claims.py::test_why_best_test_count_is_not_stale passes with the fix.

2. Line 80 "**23** console scripts (... -latex)" — STALE. pyproject.toml [project.scripts] now defines **24** (commit 04e3bb2 added `untell-explain` without updating this page). tests/test_docs_claims.py::test_console_script_count_in_why_best_matches_pyproject FAILS on main; passes with the fix (24 + `-explain` added to the list).

3. Line 148 "Multiple real detectors in the loop | ✅ (14)" — STALE. all_detectors() registers **15** (8 local incl. opt-in radar/binoculars/local_judge + 7 commercial: LLM-judge plus 6 key-gated adapters; the page's own line 77 says "8 local + 7 commercial" = 15). Already flagged by a prior queue entry; re-verified live 2026-08-15. The (14)→(15) cell edit is NOT applied in the working tree — included here for the human to do in the same pass.

Suggested commit (human): docs(why-best): refresh test/console/detector counts to the live surface — then `python -m untell.scripts.audit` and tests/test_docs_claims.py both pass.


## 2026-08-15 slice-6 (re-run) — RED — audit_next.py record accepts non-hash commit cells; 15 rows unverifiable

WHAT   .claude/audit-log.md has 15 rows whose commit column is not a hash: 14 cite the literal
       string HEAD (passes 33, 90, 502, 503, 520, 524, 531, 571, 634, 813, 837, 844, 2286, 2480),
       1 cites the literal placeholder COMMIT (pass 714), and 1 (pass 316) cites 2f56d1052f8f...
       which git cat-file -e says does not exist. audit_next.py record validates the commit
       cell only as non-empty, so a defect-fixed row can be recorded with an unverifiable commit.
       Counted at baseline: 2730 rows, 55 duplicate pass numbers (one-row-per-pass violated),
       28 file-order decreases, 0 suite-shrink rows (that guard held).
NEXT   In audit_next.py cmd_record, require [0-9a-f]{7,40} for NEEDS_EVIDENCE verdicts; backfill
       the 15 HEAD/COMMIT rows with real hashes (most fixes are locatable from note text, e.g.
       aligned_chunks -> 1c1482c, restore_layout_lines -> dd034d8). audit_next.py is RED_SELF
       (guard-blocked) so this is a human edit.

## 2026-08-15 slice-6 (re-run) — RED — why-best test/module count stale AGAIN: 7712/500 vs 7693/498

WHAT   Fresh measurement 2026-08-15 (PYTHONPATH cleared, UNTELL_LITE_NO_TORCH=1):
       pytest --collect-only -q -> 7712 tests collected in 33.49s (EXIT=0); tests/test_*.py = 500
       files. docs/why-best-open-repo.md:154 currently claims 7693 tests / 498 modules (restored
       by slice-19 queue work and 4a34d4d). Stale by +19 tests / +2 modules at measurement time;
       the fleet adds test modules continuously (500 -> 510 within the hour), so re-run
       `python -m untell.scripts.audit --fix-counts` immediately before committing. Doc is RED +
       carries a human-owned uncommitted edit; not touched here.

## 2026-08-15 slice-6 (re-run) — AMBER — detector-audit exit-1 root cause CONFIRMED with fresh evidence; companion CLI crash FIXED

WHAT   Reproduced `python -m eval.detector_audit --pairs 20 --dataset hc3 --json` (PYTHONPATH
       cleared, full JSON teed): EXIT=1, broken=["mage"], mage MISCALIBRATED human_mean 0.3477
       ai_mean 1.0 AUROC 1.0 FPR 0.35 > MAX_FPR 0.20 at DEFAULT_THRESHOLD 0.30, TPR 1.0 — numbers
       identical to the me2 entry. Cause chain: mage's genuine calibration on HC3 (README
       documents 33% HC3 false positives; raw-logits probe proves the adapter convention is
       correct) -> detector_audit.main returns 1 by design (line 530) -> research.py refuses to
       record, discarding a complete JSON measurement. Remedy remains me2's human call (a)
       record-a-finding vs (b) RAID corpus; not implemented here. Separately FIXED this session:
       the no-json smoke CLI crashed with KeyError('auroc') at line 495 (radar/local_judge/
       binoculars UNAVAILABLE rows lack an auroc key) — and/or precedence bug, committed with
       6 new render tests.

## 2026-08-15 slice-8 AMBER — lite-builtin determinism record corrected; KNOB_UNSAFE reason text updated (error-message change)

WHAT   instruments.json lite-builtin claimed deterministic=true / run_to_run post_mean_max 0.0 from
       the original 2-run calibration (716890e). The committed measurements.jsonl now holds 5
       lite-builtin runs: post_mean_max 0.1163/0.1163/0.1163/0.1163/0.1259 — full-history spread
       0.0096 (run 5, committed 084785f Aug 14, predates the last instruments.json edit c53cb58
       Aug 15). Same defect class as the lite-hc3 correction 6ddcc9e; per the code's own rule
       (research.py:404-413, deterministic = all full-history spread == 0) lite-builtin is NOT
       deterministic. Fixed instruments.json (deterministic: false, post_mean_max 0.0096, note).
       Experiment.py KNOB_UNSAFE reason still said "identical to 4dp run to run" — a claim the
       ledger contradicts — so its TEXT was updated (error-message change => AMBER) and the test
       pinning the stale "identical" wording was updated to pin the measured spread instead.
RAN    python .claude/research.py report; json parse of measurements.jsonl + git blame of rows
SAW    lite-builtin post_mean_max seq [0.1163 x4, 0.1259]; spread 0.0096; instruments said 0.0
WHY    AMBER: error-message/exit-code change (KNOB_UNSAFE refusal reason text) in experiment.py
NEXT   None required. The refusal itself is unchanged (lite-builtin still KNOB_UNSAFE); only the
       cited reason was corrected to the measured numbers.


## 2026-08-15 slice-5 AMBER — untell-server default bind 0.0.0.0 -> 127.0.0.1 (behavior change)

WHAT   `untell-server` --host defaulted to 0.0.0.0 while EVERY document said localhost: README
       env-var table ("default 127.0.0.1:8000"), api_server.py's own CORS comment ("runs on
       localhost by default"), the CORS test docstring ("runs on localhost by default"), and
       uvicorn's own default (127.0.0.1). The 0.0.0.0 default put a server that ships an
       optional-auth path on the LAN under the documented quick start. Changed the default to
       127.0.0.1 via a new _host_from_env() (env override still wins; empty value falls back),
       with 3 tests pinning default/override/empty. Also corrected the stale README MCP tool list
       (verify -> verify_commercial + tells/ceiling/compare) and the false UNTELL_CORS_ORIGINS row
       ("unset means no cross-origin access" — actual: unset = wildcard any-origin, no
       credentials, per test_cors_never_reflects_with_credentials.py).
RAN    probe: TestClient against /humanize //ceiling with get_rewriter mocked None; pytest batches
SAW    documented default vs live default diverged; CORS claim contradicted by pinned CORS test
WHY    AMBER: changes the default bind address of a shipped console command (behavior change)
NEXT   Human call: keep 127.0.0.1 (matches every doc + uvicorn; default was the outlier) or
       revert to 0.0.0.0 and update README/comments to match. Flagged before merge.


## 2026-08-15 slice-5 RED/QUEUED — README doc-drift fixes blocked by guard (human-owned file)

WHAT   Two README rows contradict the live code (verified against HEAD + running server):
       (1) L149 MCP tool list: "exposes score/sentences/untell/verify/scrub as tools" — there is
       NO `verify` tool (it is `verify_commercial`) and tells/ceiling/compare are omitted. Real
       list: score, sentences, tells, untell, verify_commercial, ceiling, compare, scrub
       (asserted by tests/test_mcp_server.py::test_advertised_tool_names_match_what_the_server_registers).
       (2) L789 UNTELL_CORS_ORIGINS row: "unset means no cross-origin access" — live code: unset
       = allow_origins=["*"], any origin may call, credentials NOT allowed (pinned by
       tests/test_cors_never_reflects_with_credentials.py). The claim is the opposite of the
       behavior. Proposed fix text: "Unset means ANY origin may call, with credentials NOT
       allowed (the spec-legal wildcard); setting a list restricts to exactly those origins and
       enables credentials".
RAN    live probes + tests (297+28 passed); guard.py BLOCKED the README edit
SAW    guard: "BLOCK RED file touched: README.md - a human owns this one."
WHY    RED per guard policy (README.md is human-owned); edits are doc drift, NOT published
       numbers — no performance/threshold figures touched. Same fixes applied to the pyproject
       MCP extra comment (AMBER-warned, committed).
NEXT   Human call: apply the two row fixes above, or reject. Note the pyproject comment already
       landed with the corrected list.

## 2026-08-15 fanout salvage — census count drift (derivable check failing, docs are RED)

WHAT   audit derivable check fails: docs/humanizer-census.md claims 6930 tests; pytest
       collects 7986 (UNTELL_LITE_NO_TORCH lite collection). The count grew because the
       fanout campaign added ~180 tests (text_split 68, coverage 45, explain 40, ...).
RAN    `.venv/Scripts/python.exe -m untell.scripts.audit` → 1 remaining failure
SAW    "docs/humanizer-census.md: claims 6930 tests, pytest collects 7986"
WHY    RED per guard policy (published numbers in docs/); the repo's own repair is
       `untell-audit --fix-counts`, which also rewrites README/ROADMAP/why-best counts —
       human-owned. why-best-open-repo.md already queued in wave 1 (991e9ff/4a34d4d).
NEXT   Human call: run `.venv/Scripts/python.exe -m untell.scripts.audit --fix-counts`
       outside the agent (it also un-stales why-best + README + ROADMAP counts in one pass),
       or reject.

## 2026-08-15 slice 14 wave 3 — AMBER — new CLI subcommand `untell batch`

WHAT   Shipped a NEW capability: `untell batch <dir>` humanizes every .txt/.md
       file in a directory tree, mirrors structure into <dir>_humanized, and
       writes manifest.json (input path, status ok/skipped/failed, pre/post
       scores, rewrote flag) plus a summary line. Supports --out, --tier,
       --threshold, --rewriter, --max-iters, --best-of, --dry-run, --limit,
       --json. Binary files skipped cleanly (NUL sniff + io_utils guard);
       per-file failures reported without aborting; exit 1 if any file failed.
       New console script untell-batch registered in pyproject.toml (AMBER
       file) and cli.py _COMMANDS; tests in tests/test_batch_cli.py (19 pass).
RAN    UNTELL_LITE_NO_TORCH=1 UNTELL_DISABLE_NLI=1 ./.venv/Scripts/untell.exe
       batch C:/Users/Admin/AppData/Local/Temp/untell_batch_demo
SAW    batch: 5 files, 3 humanized (2 rewrote), 2 skipped, 0 failed — manifest:
       ...untell_batch_demo_humanized/manifest.json   (exit 0)
       With a permission-denied file: "failed denied.txt: cannot read:
       Permission denied" and exit 1; dry-run writes nothing, exit 0.
WHY    AMBER by the envelope: a new CLI subcommand/flag, plus pyproject.toml
       (an AMBER file) gained a console-script entry. Nothing RED: no published
       numbers, thresholds, deps, or test deletions were touched.
NEXT   Optional human review: the README's "every subcommand is also a
       standalone untell-<name> script" claim now also holds for batch; docs
       otherwise list no subcommand counts, so no count fix is needed. Run
       `untell batch --help` to see the new command's options.

## 2026-08-15 slice 9 RED — tracked .claude/ probe scripts fail the CI ruff step

WHAT   ci.yml's Lint step (`ruff check .`) cannot pass at HEAD: the fanout campaign
       committed 259 probe scripts under .claude/**/*.py carrying ~705 ruff errors
       (I001/E401/F401/E402/E702/E701/B007/W292/F841/F821/W605/B023/E741/F541).
       The 28 lint errors in shipped code were fixed this wave; the .claude set is
       a structural decision, not a fix. .claude is NOT gitignored, so ruff — which
       respects .gitignore, not intent — checks it.
RAN    ruff check .  (HEAD archive 0d368e9, ruff 0.15.20, the version `ruff>=0.4`
       resolves to today) -> 733 errors: ~705 in .claude, 28 in shipped code.
SAW    untell/text_split.py:230 W605 (`\]` in a non-raw segment) is the sole shipped-code
       leftover — that file is being rewritten by the parallel text_split slice.
WHY    RED per the slice-9 brief ("flag mismatches (queue RED)"). Fixing it means either
       changing CI scope (extend-exclude .claude) or removing 259 probe files — a human call.
NEXT   Either add ".claude" to [tool.ruff] extend-exclude in pyproject.toml (one line;
       keeps CI meaningful for shipped code) or move probes out of the tracked tree;
       then `ruff check .` passes. Also confirm the text_split slice's commit fixed the
       W605 at untell/text_split.py:230.

## 2026-08-15 slice 15 (wave 3) — AMBER — new `--diff` output mode on the humanize path

WHAT   `untell humanize --diff` ships: a unified-diff-style before/after of the
       humanization showing ONLY changed lines (deletions red, additions green, hunk
       headers dim; rich panel + plain fallback, `_Text`-escaped so brackets in user
       text cannot be swallowed as markup). `--diff --json` emits a machine-readable
       payload (format "untell-diff", hunks with 0-based spans and no context lines,
       added/removed counts). Built on the explain/lock machinery: the payload carries
       the locked spans (the same spans `lock()` freezes) and `locks_preserved` — how
       many survived byte-for-byte; the human view prints that count, red if any lock
       did not survive. `difflib.SequenceMatcher(autojunk=False)` is load-bearing:
       the default junk heuristic reported a 100+100-line block swap as one 200-line
       replace (MEASURED). Result-dict contract untouched; `untell explain` untouched.
RAN    `.venv/Scripts/python.exe -m pytest tests/test_humanize_diff.py` in an isolated
       worktree (sibling slices were mid-edit on text_split.py in the shared tree) —
       21 passed. Surrounding families (rich_output*, the-diff-report, explain,
       json-mode error paths, numeric-flag bounds, cli_dispatch) also green. Live CLI
       demo: composite rewriter, lite tier, 4-line paragraph → 4 added/4 removed,
       "2 locked span(s) preserved verbatim".
SAW    @@ -1,4 +1,4 @@  with -/+ pairs and the lock note; --diff --json parsed with
       hunks + locked_spans [Smith (2020), 47%], locks_preserved 2 of 2.
WHY    AMBER per the task envelope: a new CLI flag is an interface addition a human
       should sign off on (flag name, JSON shape). No RED touched.
NEXT   Human: confirm the flag name / payload shape; nothing else pending. The queue
       entry travelled in the same commit as the flag (per the envelope).

## 2026-08-15 slice-20 AMBER — UNTELL_POLICY_MAXTOK invalid value: traceback -> warning

WHAT   UNTELL_POLICY_MAXTOK=abc previously raised a bare ValueError inside
       local_policy._generate_once (`int(budget)` on the raw env string) — the one
       documented env var that crashed on a typo. Fixed: new _env_max_new_tokens()
       parses defensively; non-int or non-positive values now log a warning naming the
       variable and fall back to the computed default (512, or max(512, 1.6x source
       tokens) on the untuned path). Explicit valid values (incl. whitespace-padded)
       still win. Pinned by tests/test_env_var_consistency_matrix.py.
RAN    helper probes (abc/0/-5/700/None), 23-test matrix file, 62-test config/port/
       local_policy regression batch, test_detector_contract (15)
SAW    ValueError traceback before; warning + default after
WHY    AMBER per the envelope: an error-path behavior change (crash -> message). No
       RED touched; no published number, threshold, or dependency involved.
NEXT   Human: no action needed unless the fallback default should be something else.

## 2026-08-15 wave3 slice13 — RED — lite tier still loads spaCy NER (and torch, via thinc) under UNTELL_LITE_NO_TORCH=1

WHAT   The env var is documented as "force the pure-stdlib lite path even when torch is installed".
       This pass fixed the two model-backed MEANING GATES that ignored it (NLI veto + roles veto:
       entailment.available()/roles.available()/parser_available()/role_swap now honor the var —
       meaning_preserved dropped 72.1s -> 0.19s cold on a torch+spacy install, and the loop now
       reports "similarity-only (NLI unavailable)" under the var). One torch-loading path was left
       alone because it is a correctness feature, not a gate: preserve.py's spaCy NER lock.
RAN    score_text(tier="lite") / untell_text(tier="lite") with UNTELL_LITE_NO_TORCH=1, import-hook
       probe of first heavy import, component timing (best of 3 fresh subprocesses).
SAW    score_text(tier='lite') 10.4s, loads spacy+torch; preserve._spacy_entity_spans first call
       17.9s (spacy ~0.5s import, torch ~3.6s dragged in by thinc.compat, en_core_web_sm load, parse).
       load_detectors('lite') is NOT the cost: 0.14s, loads nothing (tier filter short-circuits
       available() probes — earlier hypothesis retracted after direct measurement).
WHY    RED: gating NER off on the lite tier (or moving it to full) removes the README's
       "entities are locked byte-for-byte" guarantee on the most common install; there is no
       other switch for it. A composition decision for a human, not a bug fix.
NEXT   Decide among: (a) leave NER on all tiers (correctness wins; lite stays ~10-18s on spacy
       installs), (b) honor UNTELL_LITE_NO_TORCH in _spacy_entity_spans_impl, (c) add a
       UNTELL_DISABLE_NER switch. Also: the suite count in docs/why-best-open-repo.md is now stale
       by +6 tests (this pass); the human runs `untell-audit --fix-counts` per the established
       process. Without the env var, NLI/roles behavior is byte-identical to before.

## 2026-08-15 slice 19 RED — CHANGELOG [Unreleased] unrecorded since b37cb02 (2026-08-13)

WHAT   CHANGELOG.md's [Unreleased] section has no entries for anything after b37cb02
       ("eleven more user-visible changes were unrecorded", 2026-08-13). Since then the log
       carries ~114 fix/feat commits; ~30 are user-visible and unrecorded: untell batch CLI
       (af37909), untell explain (04e3bb2), NUL stdin refusal (7a0c925), distill degenerate
       args (e1391d4), ceiling/compare bad --file (5fb4c5c), fuzz-found type guards (5b38d76),
       CJK/RTL terminators + zero-width bypass + scriptio-continua (0315a14), lone surrogates
       (bb87f87), lite env gate + spaCy NER cache + quadratic anchor (9e02182), free-rewriter
       refusal + MCP verify_commercial + localhost bind (694f786), instruments determinism
       (e1d558c), detector-audit and/or (607621a), feet-inches/dimensions/semicolon cites
       (b91932f), compound units/time ranges/exponents/spaced phones (1162504), MCP _bad_args
       infinite counts (d57026c), rich bar clamp (e2c18b2), panels markup escape (2e02bb3),
       judge-prompt dedupe (4b1ce4d), initialism cap 6 (0a82920), sentence-final abbreviations
       (180fc97), untell-server no-op (b1ed8d2), emoji tag sequences (b5b0856), NaN/Inf 422
       pin (9b31709), run.py FastAPI-import removal (be9b15d), dockerignore wheel-inputs fix
       (75be76a).
RAN    git log --format='%h %s' b37cb02..HEAD --grep='^fix\|^feat' | wc -l  (114);
       git log --oneline -6 -- CHANGELOG.md  (newest = b37cb02)
SAW    b37cb02 2026-08-13 docs(changelog): eleven more user-visible changes were unrecorded
       (no changelog commit after it)
WHY    RED: CHANGELOG.md is a guard-RED file (`^CHANGELOG\.md$` in RED_FILES); a changelog is
       exactly the "published record" band. tests/test_changelog.py is green (ties the newest
       heading to the shipped version, which still holds).
NEXT   A human records the user-visible subset under [Unreleased] (fleet-internal commits —
       audit-log restores, survivors notes, queue closes — are not changelog material). Keep
       the Keep-a-Changelog shape; do not split by release since 0.3.0 shipped.

## 2026-08-15 slice 19 RED — ROADMAP.md claims 80 attributed claims; audit measures 158

WHAT   ROADMAP.md line 158 says "Currently: 80 claims attributed, 0 unattributed." The audit
       it describes has grown: 158 claims attributed, 0 unattributed.
RAN    python -m untell.scripts.audit --json  (venv python, PYTHONPATH cleared)
SAW    "attributed_claims": 158, "unattributed_claims": []
WHY    RED: a published measured number in a doc. The 80 was accurate at ship (2026-08-08);
       the audit gained checks since.
NEXT   Update ROADMAP.md §2 line 158 to the measured 158 (or state "as of <date>"), ideally
       in the same commit as the census count fix so the audit goes green once.

## 2026-08-15 slice 19 RED — census test count stale (6930 vs 8066 collected) — audit is red

WHAT   `untell-audit` fails its "every 'N tests' claim is close to what pytest collects" check:
       docs/humanizer-census.md claims 6930 tests, pytest collects 8066 (this venv, tree at
       fca0c0c + in-flight sibling tests). Because this check fails, the whole audit exits 1
       and CI's "Audit documented claims" step is red. The 2026-08-13 queue entry about
       UNTELL_POLICY_WHOLE_DOC is resolved (no longer listed); this is the only failing check
       of 40.
RAN    python -m untell.scripts.audit --json
SAW    "- every 'N tests' claim is close to what pytest collects
         docs/humanizer-census.md: claims 6930 tests, pytest collects 8066"
WHY    RED: docs/humanizer-census.md is a guard-RED file; counts are published numbers. The
       collected count moves as sibling slices land tests, so re-measure at fix time.
NEXT   The human runs `untell-audit --fix-counts` (established process) to refresh the census
       number, then re-runs the audit to confirm 40/40.

## 2026-08-15 slice 19 AMBER — pyproject "4 - Beta" vs SECURITY.md "alpha research project"

WHAT   pyproject.toml classifier says "Development Status :: 4 - Beta"; SECURITY.md §Supported
       versions says "This is an alpha research project". Same project, two statuses.
RAN    grep -n -i 'alpha\|beta' README.md SECURITY.md pyproject.toml
SAW    pyproject.toml:15 "Development Status :: 4 - Beta"; SECURITY.md:53 "This is an alpha
       research project"; README.md: no alpha/beta self-description at all
WHY    AMBER: pyproject.toml is an AMBER file and this is a published-metadata judgment call —
       which status is intended is a human decision, not a mechanical fix.
NEXT   Pick one: bump the classifier to "3 - Alpha" (matches SECURITY.md and the 0.x version)
       or soften SECURITY.md's "alpha" wording; keep the two consistent.

## 2026-08-15 slice 19 AMBER — the [api] extra exists but no doc names `pip install untell[api]`

WHAT   pyproject declares an `api` extra (anthropic>=0.40, openai>=1.0) for hosted-LLM
       rewriters. It is the ONLY one of the 13 extras never named by pip-install syntax in
       README/docs/SKILL.md. Its feature IS documented: docs/api-server.md lists the
       anthropic/openai rewriters and untell/rewriter/base.py implements both adapters.
RAN    python scan of every `[extra]` mention in README.md + docs/*.md + untell/SKILL.md
       vs pyproject optional-dependencies (13 declared, 12 mentioned, 0 phantom)
SAW    'declared but never mentioned anywhere: ['api']'
WHY    AMBER: doc gap in a published surface; README.md is RED so the natural home for the
       pip line is docs/api-server.md (not guard-RED), but a sibling slice was mid-edit on it
       and the fix is cosmetic.
NEXT   Add one line near the rewriter options in docs/api-server.md:
       `pip install "untell[api]"` — then every declared extra is reachable from the docs.

## 2026-08-15 slice-18 AMBER — REST OPTIONS preflight now bypasses auth (CORS+auth combo was broken)

WHAT   With UNTELL_API_KEY set, a browser CORS preflight (OPTIONS, no credentials by spec) hit
       the auth middleware FIRST (it is outermost; added after CORSMiddleware) and got 401 — so
       the documented CORS support silently stopped working the moment auth was enabled.
       MEASURED: OPTIONS /score with Origin+ACRM headers, UNTELL_API_KEY=secret -> 401,
       no allow-origin; same request without a key -> 200 allow-origin: *.
       Fixed: auth_middleware passes OPTIONS straight to call_next (CORSMiddleware answers the
       preflight itself; OPTIONS matches no route, so no handler logic is reachable). Also
       pinned with 8 new tests: preflight-with-key 200 + CORS headers, real requests still 401,
       non-preflight OPTIONS still 405, .env UNTELL_CORS_ORIGINS honoured (module now calls
       load_env() at import, same trap _api_key() documents for the key), and /openapi.json now
       declares HTTPBearer + APIKeyHeader securitySchemes with per-route optional security
       [{}, {HTTPBearer: []}, {APIKeyHeader: []}] matching the conditional enforcement.
RAN    TestClient probes + tests/test_cors_preflight_and_openapi_auth.py (8 passed)
SAW    401->200 for OPTIONS preflight with key set; securitySchemes present in /openapi.json
WHY    AMBER per envelope: error-code change for one request class (OPTIONS preflight).
NEXT   No human action needed unless the 401-on-preflight was relied upon; the CORS feature is
       now actually usable with auth. docs/api-server.md Authentication section updated to
       match (UNTELL_HOST default also corrected 0.0.0.0 -> 127.0.0.1, was missed by slice-5).

## 2026-08-15 slice-18 note — wave-2 queue re-verification on current HEAD (CORS/bind entries)

WHAT   Re-checked the wave-2 CORS/bind queue entries against HEAD 0d368e9:
       1. L473 "README.md:787 bind default STALE (api_server.py default 0.0.0.0)" — premise
          now INVERTED: 694f786 (slice-5) changed the code default to 127.0.0.1, README is
          correct. The live drift MOVED to docs/api-server.md:21 (still 0.0.0.0); fixed in this
          slice (docs/api-server.md is not guard-RED).
       2. L590-609 README L149 MCP tool list "score/sentences/untell/verify/scrub" — STILL
          STALE at HEAD: README:148 unchanged; real list (mcp_server.py:31 _TOOL_NAMES) is
          score, sentences, tells, untell, verify_commercial, ceiling, compare, scrub. Entry
          stays queued (README is RED).
       3. L597-602 README L789 UNTELL_CORS_ORIGINS "unset means no cross-origin access" — STILL
          STALE at HEAD: README:789 unchanged; live code unset = allow_origins=["*"] (any
          origin, credentials NOT allowed), pinned by test_cors_never_reflects_with_credentials.
          Entry stays queued (README is RED).
RAN    grep README.md L148/L789 + docs/api-server.md L21; _TOOL_NAMES; live TestClient probes
SAW    Entries 2 and 3 accurate; entry 1's staleness fixed by 694f786, doc drift relocated.
WHY    Record-keeping for the human's README edit pass; no guard-RED file touched here.
NEXT   Human: apply the two README row fixes from entry L590-609 (MCP tool list + CORS row).

## 2026-08-15 slice-20 RED/QUEUED — why-best-open-repo.md "518 test modules" now stale (533)

WHAT   audit derivable check fails: docs/why-best-open-repo.md says "518 test modules",
       tests/ now has 533 (wave-3 fanout added ~15 test files incl. this slice's
       test_env_var_consistency_matrix.py). Same repair path as the census count drift
       entry above: `untell-audit --fix-counts` rewrites why-best counts in one pass.
RAN    `.venv/Scripts/python.exe -m untell.scripts.audit` after staging
SAW    "docs/why-best-open-repo.md: says 518 test modules, tests/ has 533 — stale by
       more than 5"
WHY    RED per guard policy (published numbers in docs/why-best-*); file is human-owned.
NEXT   Human: run `.venv/Scripts/python.exe -m untell.scripts.audit --fix-counts`
       (also fixes the census 6930-vs-8292 count in the same pass), or reject.

## 2026-08-15 slice 10 (wave 3) — AMBER — MCP surface: text-length edge guard + ceiling unknown-rewriter refusal

WHAT   Two MCP refusals added, matching surfaces that already refuse the same inputs.
       1) Every text-taking MCP tool (score/sentences/tells/untell/verify_commercial/scrub)
       now refuses text over MAX_INPUT_CHARS (50,000, the SAME constant REST /score bounds
       every request model with, 422) with an error dict. MEASURED before: `tells` accepted
       a 1,018,136-char payload and occupied the worker 230 s; the mcp SDK runs sync tool
       fns directly in the event loop, so a megabyte payload wedges the whole server and a
       client disconnect cannot interrupt it. untell's voice_sample is bounded too (REST
       bounds it at the same constant). 2) `ceiling(rewriter=<unknown name>)` now refuses
       with an error dict listing the valid vocabulary. MEASURED before: `rewriter="wat"`
       ran the FULL measurement (106 s) and returned `"rewriter": "wat"` — a name that does
       not exist — as the rewriter that produced the numbers; measure_ceiling's aggregation
       drops the per-text error dicts untell_text returns. The CLI refuses the same name at
       parse time (argparse choices) and REST answers 422 "unknown rewriter {name}".
WHY    AMBER per the envelope: both are return-shape changes (new refusal dict where a
       result used to come back) and new error messages on a shipped surface.
RAN    tests/test_mcp_text_guard.py (12), tests/test_mcp_ceiling_rewriter_guard.py (5),
       tests/test_mcp_concurrency.py (13), plus the pre-existing MCP files: 100 passed
       with the guard files RED before the fix (ImportError / 2 failed). Ruff clean.
NEXT   Human: confirm both refusal vocabularies. The README:149 tool-list staleness this
       slice re-verified is already queued (pass 531) — not re-queued. Also note: sync MCP
       tools block the event loop for any long VALID input (SDK property, not fixed here);
       the guard removes the pathological megabyte case.

## 2026-08-15 wave-3 slice-3 — RED — untell-audit exits 1 on two stale doc test-count claims

WHAT   `untell-audit` (no args) exits 1: two claim checks FAIL, both published test counts
       that have drifted as test files were added. The doc numbers are RED — not edited here.
RAN    UNTELL_LITE_NO_TORCH=1 ./.venv/Scripts/python.exe -c "import untell.scripts.audit as m; raise SystemExit(m.main([]))"   (195s)
SAW    FAIL  every 'N test modules' claim matches tests/  (docs/why-best-open-repo.md: says 518 test modules, tests/ has 540 — stale by more than 5)
       FAIL  every 'N tests' claim is close to what pytest collects  (docs/humanizer-census.md: claims 6930 tests, pytest collects 8485)
WHY    RED per the envelope: published numbers in docs/why-best-open-repo.md and
       docs/humanizer-census.md; the human runs `untell-audit --fix-counts`.
NEXT   Run `untell-audit --fix-counts` (or update both counts by hand), then re-run the audit.
       Also: tests/ has 540 modules and pytest collects 8485 tests as of this pass; the CLI
       conformance matrix (tests/test_cli_conformance_matrix.py) asserts the audit's verdict
       semantics (exit 0 or 1) so it stays green either way.

## 2026-08-15 wave-3 slice-3 — AMBER — distill test's "faithful paraphrase" premise is false on this machine

WHAT   tests/test_training.py::test_distill_keeps_a_faithful_paraphrase_the_loop_admits
       fails on the PRISTINE tree (verified via git stash): meaning_preserved(orig, faithful,
       0.32, 0.76) is False, so the test's premise ("the loop admits it") does not hold here.
RAN    UNTELL_LITE_NO_TORCH=1 ./.venv/Scripts/python.exe -m pytest tests/test_training.py::test_distill_keeps_a_faithful_paraphrase_the_loop_admits -q
SAW    E AssertionError: assert False
       E + where False = meaning_preserved('The cat sat on the mat in the warm afternoon sun,
       perfectly content.', 'The feline rested upon the rug during the sunny afternoon, quite
       satisfied.', 0.32, 0.76)
       environment: sentence_transformers+bert_score+torch installed, entailment.available()
       False (NLI weights not downloaded), similarity() measures the pair at 0.32 — below the
       0.50 token-overlap bar, let alone the hardcoded 0.76.
WHY    AMBER: a test asserting loop behaviour that cannot hold in this environment. Not caused
       by slice 3 (proved pre-existing by stash). Not fixed here: the pair/bar choice is a
       test-data question, and skip/xfail on a shipped test is RED.
NEXT   Decide whether the pair should still measure as "faithful" (then similarity/NLI backend
       is the problem) or the pair/bar should change (then the test's data is stale). Reproduce
       with the command above; the pair sims 0.32 under the current stack.

## 2026-08-15 wave-3 slice-3 — RED — README documents UNTELL_BROWSER_SITES wrongly

WHAT   README env-table row for UNTELL_BROWSER_SITES says "comma-separated free web
       detectors for --browser", but the code (untell/browser_check.py:369) reads it as a
       JSON FILE PATH of custom site configs (legacy alias HUMANIZE_BROWSER_SITES, fallback
       ./browser_sites.json). Docs drift; the guard blocks README edits (human-owned).
RAN    grep -n 'BROWSER_SITES' README.md untell/browser_check.py
SAW    README.md:790: "comma-separated free web detectors for `--browser`"
       untell/browser_check.py:362: "Load user-defined sites from `$UNTELL_BROWSER_SITES`
       (a JSON path; ...) or `./browser_sites.json`."
WHY    RED per the envelope: README is human-owned (guard.py blocks it).
NEXT   Change the README row to: "path to a JSON file of custom free-web-detector site
       configs for `--browser` (see `untell/browser_check.py`); unset falls back to
       `./browser_sites.json`".
## 2026-08-15 wave3 slice 7 — AMBER — +8 tests stale the RED count claims again

WHAT   fix(perf) landed a bounded per-text detector-score cache in
       untell/scripts/score.py (loop-level caching round 2: unchanged sentences
       hit, rewritten sentences miss) with 8 new tests in
       tests/test_score_cache_is_content_addressed.py. The suite total moves, so
       the published counts are stale again: 7530/483 (why-best-open-repo.md
       line 154) and 6930 (humanizer-census.md) — both RED, both already known
       to drift on every test landing.
RAN    C:/Users/Admin/Humanize/.venv/Scripts/python.exe C:/Users/Admin/goals/results/s7_pytest.py tests/test_score_cache_is_content_addressed.py -q
SAW    8 passed
WHY    RED files carry published numbers; the human runs untell-audit --fix-counts.
NEXT   Run `untell-audit --fix-counts` at merge time (or the next batch); the
       count moves every time a test lands, so one fix per wave suffices.

## 2026-08-15 slice 10 (wave 3) — AMBER — MCP untell: unknown-rewriter refusal no longer carries a misleading `final`

WHAT   `untell(rewriter=<unknown name>)` returned a SUCCESS-shaped dict
       `{"error": "...", "final": <the UNCHANGED input text>, "seed": ...}`. untell_text
       refuses the name before the loop (run.py returns {"error": ..., "final": text}), but
       the MCP tool passed it through, so a client reading `final` — the key the tool's own
       docstring advertises as "the humanized text" — saw the caller's text returned as if
       the loop had run. On MCP there is no status code (unlike REST's 422), so the shape
       IS the verdict. Now returns the pure `{"error": ...}` dict, the same shape as every
       other refusal on this surface (tier/style/ceiling-rewriter).
WHY    AMBER per the envelope: return-shape change on a shipped surface (a key that used to
       be present — `final` — is now absent on this one refusal path) and error-message
       surface change.
RAN    tests/test_mcp_server.py (37), tests/test_mcp_refusal_matrix.py (38),
       tests/test_mcp_lifecycle.py (5), plus full MCP suite (11 files). New tests RED
       before the fix (`assert "final" not in result` failed with the original text in
       `final`), GREEN after.
NEXT   Human: confirm the refusal vocabulary ("rewriter 'X' is not available — check the
       name (see `untell --check` for the installed list) or install its extra"). Note
       `untell_text` (library level) intentionally keeps `final`=scrubbed-original on its
       error path — only the MCP tool now strips it.

## 2026-08-15 slice 11 (wave 3, track 4) — AMBER — detector calibration study: all README numbers reproduce except mage-on-RAID 0%

WHAT   Ran the queued calibration end to end: per-detector TPR/FPR at the SHIPPED 0.30
       threshold on HC3 human vs AI pairs, calibration gaps (threshold that would bring
       FPR to 20%), and a three-corpus check of the README's mage claims. Also fixed two
       render() defects in the audit's own summary (GREEN, committed here).
RAN    python -m eval.detector_audit --pairs 20 --dataset hc3 --json   (EXIT=1, expected)
       + calibration_sweep/verify_claims companion scripts (worktree at HEAD 0d368e9)
SAW    HC3 20 pairs (n=20, layout collapsed):
         detector               AUROC  human  ai    FPR@0.30 TPR@0.30
         perplexity_burstiness  1.000  0.159  0.656  0.00    1.00
         roberta_openai         0.993  0.051  0.966  0.05    1.00
         hc3_roberta            1.000  0.099  0.999  0.10    1.00
         fast_detectgpt         1.000  0.070  0.635  0.00    1.00
         mage                   1.000  0.348  1.000  0.35    1.00   <- MISCALIBRATED
       ENSEMBLE max (the product's aggregation): human_flagged 0.40, ai_flagged 1.00
       -> README's "40% over 20 HC3 pairs" reproduces exactly.
       Sentence granularity (30 derived sentences/class): 4 of 5 detectors MISCALIBRATED
       (roberta_openai FPR 0.40, hc3_roberta 0.37, fast_detectgpt 0.33, mage 0.57) —
       this is the granularity the rewrite loop actually scores spans at.
       Calibration gaps (threshold for FPR<=0.20): pb 0.219, roberta 0.002, hc3_roberta
       0.002, fdg 0.112, mage 0.999. mage's shipped cut sits INSIDE the human upper mode
       (7/20 human docs 0.83-1.0); all 20 AI docs are exactly 1.0, so TPR holds at 1.00
       even at 0.999 but the AI-side margin above the threshold is zero.
       Three-corpus mage FPR@0.30 (30 pairs each): HC3 0.3333 (=README 33.3%), MAGE
       0.0333 (=README 3.3%), RAID 0.1667 (README says 0% — DOES NOT REPRODUCE; 5/30
       human docs flagged, all deep-learning/image-segmentation abstracts, MAGE's
       training genre; layout collapse predates the claim (02756ca 2026-08-10), upstream
       RAID snapshot unchanged since 2024). hc3_roberta on MAGE: AUROC 0.5311, TPR 0.267
       (=README 0.531/0.267, chance-level confirmed).
WHY    AMBER: measurements + recommendations only; the two candidates for action are
       RED (threshold moves) and the RAID 0% figure is a published number in README
       (RED). The committed GREEN fix is render() honesty: the "Not counted" footnote
       hard-coded "six probes per class is 36 pairs" even on --pairs runs whose table
       showed n=30 derived probes (summary contradicting its own table), and the BROKEN
       label said "dead or inverted" for a MISCALIBRATED mage row. Both fixed + 4 tests.
NEXT   Human decisions, all RED or queued:
       1) mage threshold/calibration: 0.30 ships inside mage's human upper mode on HC3;
          FPR<=20% needs cut ~0.999. Global raise is wrong (other detectors' AI scores
          top out at 0.65-0.97, so 0.999 would clear every AI text those catch); a
          per-detector logistic/scale refit or verdict_threshold-style split is the
          shape of a fix. README documents 33% as "HC3-specific"; with RAID at 16.7%
          that framing is now "worst on HC3", not "only HC3".
       2) README heavy-tier "RAID 0%" figure: re-measure or re-scope (3ba9d02). Measured
          0.1667 at HEAD on the same loader. The audit can now record this honestly.
       3) The queued (a)/(b) from 2026-08-13 me2 entry still stands: detector-audit
          exits 1 while mage is MISCALIBRATED, so research.py refuses to record it.
          With the render fix the JSON already carries the finding; (a) one line in
          research.py to record non-zero-exit JSON findings remains the smallest fix.
       4) Sentence-granularity MISCALIBRATED (4 of 5 detectors, FPR 33-57% on human
          sentences at 0.30): excused from `broken` by the 36-pair rule even when probes
          are 30/class derived; the bar's rationale does not apply at 900 pairs — decide
          whether sentence rows should count at derived sample sizes.

## 2026-08-15 slice 12 — RED — polarity gate vetoes composite's de-duplication on the corpus's most repetitive doc

WHAT   `polarity_kept` compares negation_count(source) == negation_count(candidate) exactly. The
       composite's restatement-drop removes DUPLICATED negative clauses, so a legitimate
       de-duplication lowers the count and the whole rewrite is vetoed. MEASURED on long#1
       (hc3-long.txt doc 1, 424w, 176 tells — the 5x-repeated "you don't do anything" binary
       answer): every one of 15 composite draws was polarity-vetoed (negation count 9 -> 6 from
       dropping 3 of the 5 identical clauses; the surviving claims keep their polarity) and the
       run returned the input unchanged. The docstring's "0 of 30 HC3 + 0 of 30 RAID" measurement
       predates restatement-drop firing at full budget on a doc with repeated negated clauses;
       the set of distinct negation markers is unchanged (src-only == cand-only == empty) — the
       veto is count arithmetic, not a claim flip. Same family: on long#2 the deletion gate vetoed
       15/15 composite draws (restatement drops removed 62w vs a 39.4w allowance) — that one is
       the gate conservatively doing its job; the polarity one is a false positive.
RAN     SLICE12_TIER=lite SLICE12_DOCS=6,4 ./.venv/Scripts/python.exe C:/Users/Admin/goals/results/slice12_harness.py
        (per-draw gate records in slice12_track4_data.jsonl); reproduced with
        polarity_kept(strip_scaffolding(input), strip_scaffolding(candidate)) on draw 0 of long#1
SAW    long#1 composite: draws=15 gate_pass=0 vetoes={'polarity': 15}; adopted=0, sim=1.0
       negation counts: src 9 (five "don't" + four "not"), cand 6 (two "n't" + four "not")
       distinct markers src-only: set() cand-only: set()
WHY    RED-adjacent: changing what the meaning gate admits alters which rewrites ship and makes
       the gate's own docstring measurement stale; the fix is a design decision (clause-aligned
       polarity vs count-with-deletion-allowance), not a one-liner.
NEXT   Decide the semantics: a negation-count drop should be vetoed only when a SURVIVING claim
       flipped. Smallest candidate: run the count comparison per aligned_chunks pair and allow a
       drop inside a chunk whose word loss is within its deletion allowance; or check per sentence
       that every candidate sentence's polarity is present among the source sentences. Needs a
       probe set of real flips (did not reduce -> reduced) to re-verify the flip catch still fires.

## 2026-08-15 slice 12 — RED — composite burns 12 no-op draws per document after iteration 1

WHAT   CompositeRewriter is flagged non-deterministic, so the loop's stall detection never fires
       for it. MEASURED over 10 HC3 docs (slice-12 study, max_iters=5, best_of=3): composite ran
       15 draws on every doc; on all 7 docs where it adopted, the adoption happened in iteration
       1 and iterations 2-5 drew candidates byte-identical to their input (the structural stage
       returns the already-rewritten text unchanged at every intensity). 12 wasted draws per doc,
       each paying a full NLI gate pass (~20-40s) — the largest single wall-clock cost measured
       (~40% of composite's runtime). On the 3 docs where iteration 1 adopted nothing, no later
       iteration adopted either. No adoption was ever observed after iteration 1 in this sample.
RAN     SLICE12_TIER=lite SLICE12_DOCS=6,4 ./.venv/Scripts/python.exe C:/Users/Admin/goals/results/slice12_harness.py
        (draw records in slice12_track4_data.jsonl; iterate inputs per draw == iteration inputs)
SAW    per-doc (adopted, iters): (1,5)x4, (2,5), (3,5), (0,5)x3, (1,5); every adoption in iter 1;
       iters 2-5: all 12 draws per doc unchanged text, gate passed, score tie -> not adopted
WHY    RED-adjacent: a stop-condition change for stochastic rewriters alters loop behavior for
       every LLM/policy rewriter too (their draws are genuinely diverse across iterations, so a
       blanket "stop after a no-op iteration" would be wrong for them). The fix must be scoped to
       rule-based rewriters or driven by an observed no-op draw pattern.
NEXT   Smallest candidate: after an iteration whose every draw left the input text unchanged AND
       nothing was adopted, stop with stopped="stalled_noop" for rewriters whose draws are
       deterministic given (input, RNG state) — but verify on RAID + a policy/LLM rewriter that
       no later-iteration adoption is lost. Needs a probe over more corpora before shipping.
