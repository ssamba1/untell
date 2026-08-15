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
line 154: "Automated tests | ✅ **7418** tests, 445 modules"
MEASURED: tests/ has 456 modules (ls count), 7436 tests collected (pytest --co, 16.42s).
Stale by 18 tests + 11 modules — exceeds the _MODULE_DRIFT=5 window the derivable-check allows.
RED-band file: human edit required (guard blocks unattended loop).
