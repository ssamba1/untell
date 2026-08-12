# untell audit loop — one pass

You are auditing `C:\Users\Admin\Humanize`. Do exactly what this file says. Do not improvise
a different plan. Do not read large files. One run of this file = one pass.

## Step 0 — get your assignment

```bash
.venv/Scripts/python.exe .claude/audit_next.py
```

It prints your pass number, your LANE, your ONE target, and the full recipe for both. Work
that target and nothing else. Do not pick a different one, and do not work two.

Seven lanes, described in `.claude/audit-lanes.md`: L1 audit a component, L2 hunt tests that
prove nothing, L3 find the slow test, L4 prove every pattern is alive, L5 hygiene, L6 check a
documented claim against what runs, L7 check this harness itself.

**Before you change anything, read `.claude/audit-envelope.md`.** It says what you may do
alone, what you may do but must write down, and what you must never do without a human. When
something is not obviously allowed, it is not allowed — write it to `.claude/human-queue.md`
and carry on. Recording `queued` is a complete pass.

## Step 1 — baseline

```bash
.venv/Scripts/python.exe -m pytest -q -m "not slow" 2>&1 | tail -3
```

Write down the passed/failed counts. Rules:

- Red before you touched anything → your whole pass is "fix the red". Skip to Step 4.
- Green → continue.
- Never trust a summary line that says "no tests collected". Read the actual tail output.

## Step 2 — probe

Run the probe in your recipe. It is a throwaway script; write it to
`%TEMP%\claude\probe.py`, never into `tests/`.

**The probe must call the real function with real inputs and print real numbers.** You are
not reading code to judge whether it looks correct. Every defect in this repo looks correct
when read: it succeeds silently with a wrong value.

Compare the printed output against the INVARIANT in your recipe. Only two outcomes:

- Output violates the invariant → **DEFECT**. Go to Step 3.
- Output satisfies it → **CLEAN**. Go to Step 4.

Do not reason your way to a third outcome. Do not report a defect you did not observe in
printed output. If your probe crashes, fix your probe, not the repo.

## Step 3 — fix a defect (only if Step 2 printed one)

1. Make the smallest fix that makes the probe satisfy the invariant. Re-run the probe.
2. Add ONE regression test in `tests/`, named after the behaviour.
3. **Mutation-verify it.** This is mandatory and mechanical:
   ```bash
   git stash push -- <the file you fixed>
   .venv/Scripts/python.exe -m pytest -q tests/<your_new_test>.py 2>&1 | tail -3   # MUST be red
   git stash pop
   .venv/Scripts/python.exe -m pytest -q tests/<your_new_test>.py 2>&1 | tail -3   # MUST be green
   ```
   If it is green both times, the test proves nothing. Delete it and write a different one.
4. Full suite must be green before you commit:
   ```bash
   .venv/Scripts/python.exe -m pytest -q 2>&1 | tail -3
   .venv/Scripts/python.exe -m ruff check .
   ```

## Step 4 — record and commit

Commit separately, in this order, only what applies:

```bash
git add <fix files>   && git commit -m "fix(<area>): <what was wrong>"
git add tests/<file>  && git commit -m "test(<area>): <what it pins>"
```

Then record the pass. This command validates you and refuses malformed records:

```bash
.venv/Scripts/python.exe .claude/audit_next.py record --verdict clean --tests-before 5736 --tests-after 5736 --note "one line: what you probed and what the numbers were"
```

Verdicts: `clean` | `defect-fixed` | `coverage-closed` | `red-fixed` | `queued`.
`defect-fixed` and `coverage-closed` require `--commit <sha>` and `--tests-after` greater
than `--tests-before`. Use `queued` when the finding was outside your envelope and you wrote
it to `.claude/human-queue.md` instead of acting on it.

Then push:

```bash
git push origin main
```

## Absolute rules

- **Never invent a finding.** A pass that records `clean` is a good pass. Most passes are
  clean. Fabricating a fix is the only way to fail this job.
- **Never `git reset --hard`, `git rebase`, `git push --force`.** Another session commits to
  this repo. Use `git revert` if you must undo.
- **Never edit** `docs/free-ceiling-measured.md`, `README.md`, `CHANGELOG.md`, or any
  published number. Those are human-owned.
- **Never delete or weaken an existing test** to make the suite green.
- **Never read a file over 100KB.** Grep it instead.
- Commit author email must be `sricharan.samba@gmail.com`.
- If you are stuck for two attempts, record `clean` with a note saying you were stuck, and
  stop. The next pass gets a different target.
