# Lanes

`audit_next.py` assigns the lane. Seven kinds of pass, on a fixed schedule weighted toward
auditing, because auditing is the lane that has actually found things here. Each lane has a
mechanical exit condition — you never decide "is this good enough".

---

## L1 — audit a component

The default lane, roughly half of all passes. Target and recipe come from
`.claude/audit-targets.md`, chosen for you. Run the probe, compare against the invariant,
fix what the printed output says is broken. Full procedure in `.claude/audit-loop.md`.

EXIT the probe's output either satisfies the invariant or it does not.

---

## L2 — hunt tests that prove nothing

```bash
.venv/Scripts/python.exe .claude/mutate.py <module> --max 15
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
