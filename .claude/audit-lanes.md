# Lanes

`audit_next.py` assigns the lane. Nine kinds of pass on a fixed schedule: seven that make the
repo harder to break, and two (L8, L9) that measure whether it still works — a different
question, with a different answer every run, because the free rewriters are randomised.

Weighted toward auditing, because auditing is the lane that has actually found things here.
Each lane has a mechanical exit condition — you never decide "is this good enough".

---

## L1 — audit a component

The default lane, roughly half of all passes. Target and recipe come from
`.claude/audit-targets.md`, chosen for you. Run the probe, compare against the invariant,
fix what the printed output says is broken. Full procedure in `.claude/audit-loop.md`.

EXIT the probe's output either satisfies the invariant or it does not.

---

## L2 — hunt tests that prove nothing

```bash
.venv/Scripts/python.exe .claude/mutate.py <module> --max 15 --record
```

It breaks one line at a time and runs the tests that name that module. A mutation no test
catches is a **survivor**: a line the suite does not pin, with mechanical proof attached.

For each survivor, write ONE test that fails against the mutation and passes against the
original. Verify that by hand — apply the mutation, watch the new test go red, revert.

This lane exists because a green suite is not evidence. Five tests in this repo asserted the
bug they were written to catch, and a quoting fix in a sibling project survived 27 human and
agent review passes because its test mocked the engine it was supposed to exercise. Reading
a test cannot tell you whether it pins anything. Breaking the code can.

EXIT every survivor either has a new killing test, or a one-line note in the log saying why
it is unkillable (dead code, `__main__` guard, defensive branch that cannot be reached).
"Unkillable" three times on the same line means the line is dead — propose deleting it.

---

## L3 — find the test that eats the clock

```bash
.venv/Scripts/python.exe -m pytest -q --durations=25 2>&1 | tail -30
```

Anything over 30 seconds is a finding. Almost always it is a test doing real work to assert
something trivial — the usual shape is an assertion about *routing* that runs the entire
pipeline to check one argument reached one function.

Fix by stubbing at the entry point, never by deleting the assertion. The rewritten test must
assert at least as much as it did before.

EXIT the offending test is under 30s and still fails when its subject is broken (verify by
mutation, as in L2). A suite people avoid running is worse than a slower one they run.

PRIOR One test consumed 578.89 of a file's 578.96 seconds. Two rounds of guessing at the
cause saved 150s and concluded the rest was "pre-existing import overhead". `--durations`
found it in one run. Measure before optimising, exactly as before debugging.

---

## L4 — prove every pattern and list is alive

Enumerate every compiled regex, every hard-coded word list, and every lookup table in one
module. For each, construct a string that MUST match, and assert it does. Print name, source
repr, and match count.

EXIT every pattern matches its known positive. A pattern matching nothing is deleted or
fixed — never left in, because zero hits reads on every dashboard as a clean score.

PRIOR Three patterns held a literal 0x08 byte where `\b` was meant inside an `r"..."`
string. They matched nothing, scored a perfect zero, and 2526 tests were blind to it.

---

## L5 — hygiene

```bash
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q 2>&1 | tail -3
.venv/Scripts/python.exe -c "import untell, untell.api_server, untell.mcp_server"
untell --help; untell-score --help; untell-loop --help
```

Every console entry point in `pyproject.toml` must launch. Every module must import without
an optional dependency installed.

EXIT all commands exit 0. A broken entry point is a defect; fix it. Formatting nits that
change no behaviour are not findings — do not commit churn.

---

## L6 — drift between what is claimed and what runs

Read a claim in `README.md`, `untell/SKILL.md`, or `docs/`. Run the thing it describes.
Compare.

**This lane never edits those files.** Documentation carries measured numbers a human owns.
Write every mismatch to `.claude/human-queue.md` with the command you ran and its output,
and move on.

EXIT one claim checked, one queue entry written, or an explicit "claim verified" note.

---

## L7 — check the harness itself

The loop's own tooling is code, and untested code in the thing that reports correctness is
the worst place for it.

```bash
.venv/Scripts/python.exe .claude/audit_next.py record --verdict defect-fixed \
    --tests-before 10 --tests-after 20 --note "harness self check, expect refusal"
```

That must be REFUSED (no commit). Try all four refusals: missing commit, suite not grown,
suite shrank, note too short. Then confirm `mutate.py` leaves its target byte-identical:
run it, then `git diff --stat` must be empty.

EXIT all four refusals fire and `mutate.py` restores cleanly. If any does not, that is a
defect in the harness — fix it, and treat every earlier record it let through as suspect.

---

## L8 — measure, and change nothing

```bash
.venv/Scripts/python.exe .claude/research.py list       # every recipe, cost, runs so far
.venv/Scripts/python.exe .claude/research.py run <recipe>
.venv/Scripts/python.exe .claude/research.py sweep <family>   # next unmeasured in a family
.venv/Scripts/python.exe .claude/research.py table <family>   # the family side by side
.venv/Scripts/python.exe .claude/research.py report            # every ledger, one screen
```

A recipe that names a corpus file refuses to run without it. Build it first, exactly as the
refusal says:

```bash
.venv/Scripts/python.exe .claude/corpus.py build --dataset hc3 --bucket long --n 10
```

The recipe is chosen for you. It runs at fixed settings, refuses to record a result whose
rewriter never loaded or which rewrote nothing, appends the numbers to
`.claude/measurements.jsonl`, and compares against the last run of the same recipe using the
spread each run reports.

**Ledger policy (issue #17):** `measurements.jsonl` is append-only and every line is one real
run. The recorder (`research.py run`) appends unconditionally; the ledger cannot distinguish
a deliberate reproducibility re-run from a double-append, so since 2026-08-17 the recorder
*warns* (`WARNING: a byte-identical ... row is already in ...`) when the line it is about to
append already exists — append-only is unchanged, the double-append is just no longer silent
(`duplicate_rows()` in `research.py`). Identical lines that are recorded are retained as
recorded (deleting a *real* run is RED; the wave-3 slice-8 precedent). The one known
byte-identical pair — the two 64.6s `lite-builtin` rows that sat at lines 2-3 since before
issue #17 was filed — was confirmed by duplicate-row scan to be a byte-identical double-append
of a single run, and was *deduplicated on 2026-08-17*
when issue #17 closed (the second, byte-identical line removed; original first occurrence and
order preserved; 40 → 39 rows). `tests/test_research_contract.py` pins that the ledger now
holds no byte-identical pair, so any future double-append shows up as a test failure as well
as a recorder warning. A recipe's run count (`load()`/`report`) counts every retained row.
keys are a subset of `RECIPES` in `research.py` (pinned by
`tests/test_claude_instruments_match_recipes.py`); an instrument may only exist for a recipe
that exists.

**Schema (one JSON object per line, appended by `research.py run`):** `recipe` (a `RECIPES`
key), `seconds` (wall-clock time of the run, one decimal), `argv` (the exact command that
produced the numbers), `metrics` (the recipe's `metrics` fields that came back non-null),
`raw` (every non-list/non-dict field the ceiling command emitted — corpus, n, rewriter, tier,
spread, liveness flags). The `metrics`+`raw` split is what `compare()` reads: metrics drive
the noise band checks, raw carries the liveness evidence that the rewriter actually loaded.

**This lane edits no source and no document.** Its output is evidence, not a decision. If
something MOVED beyond the noise band, write it to `.claude/human-queue.md` with the command
and the output. If everything is inside the band, that is the result: record it and say so.

EXIT one recipe run to completion and recorded, or a refusal explained in the log. A run that
timed out is not a measurement — record it as `clean` with a note, do not report partial
numbers.

WHY it needs its own lane: one run cannot tell a regression from noise. The free rewriters are
randomised — about +/-0.02 on the score and +/-0.08 on the flagged rate, wider than most real
changes, and neural is four times as variable as composite. Every recipe here carries its
repeats, its corpus and its tier, because a number without those three is a number about
nothing.

---

## L9 — ask what a knob actually does, then put it back

```bash
.venv/Scripts/python.exe .claude/experiment.py list
.venv/Scripts/python.exe .claude/experiment.py run <knob> --recipe lite-hc3
```

Applies one candidate value to one tuning constant, measures before and after at identical
settings, **restores the file unconditionally**, and appends both sides to
`.claude/experiments.jsonl`.

It refuses a recipe that has never been calibrated, and a recipe calibration showed to be
deterministic. Calibration is two identical runs — if nothing moves with nothing changed, that
instrument cannot tell an effect from its absence, and every knob measured through it reads as
"no effect". That is not hypothetical: it happened here, on `lite-builtin`, and the refusal now
quotes the measured deltas rather than an opinion.

```bash
.venv/Scripts/python.exe .claude/research.py calibrate lite-hc3
```

Nothing RED is ever staged, so the guard needs no exception and no branch is left carrying a
forbidden change. The knob is chosen for you; do not invent one, and do not adopt a value —
adoption is a human decision made from several runs, not from this one.

EXIT the ledger has a new row and the working tree is clean (`git status` empty for that
file). A delta inside the noise band is a real finding: it means the knob does not do what it
looks like it does at this corpus and tier. Say that plainly.

WHY it is safe: the loop learns the slope of a constant without ever owning it. Measuring is
reversible; shipping is not.
