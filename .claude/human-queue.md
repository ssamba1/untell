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
