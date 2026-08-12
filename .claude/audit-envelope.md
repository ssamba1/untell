# What the loop may do without asking

The loop runs unattended, so the boundary has to be written down rather than judged. Three
bands. When something does not obviously fall in GREEN, it is not GREEN.

## GREEN — do it, commit it, push it

- Fix a defect you observed in printed probe output. Not one you inferred from reading.
- Add a test. Add many tests.
- Make a slow test fast without weakening what it asserts.
- Delete a pattern, branch, or constant you have *proven* dead — a regex that matches its own
  known positive zero times, a mutant nothing kills three passes running.
- Fix a broken import, entry point, or lint error.
- Fix a docstring or comment that describes code that no longer exists.
- Write to `.claude/audit-log.md`, `.claude/human-queue.md`, `.claude/survivors.md`,
  `.claude/measurements.jsonl`, and `.claude/experiments.jsonl`. Those are the loop's own
  records; the documents that *quote* numbers are RED, the ledgers that *produce* them are not.
- Run a measurement (L8) or a knob experiment (L9). Both are reversible by construction:
  L8 changes nothing at all, and L9 restores the file it touched before it exits. Measuring a
  RED constant is green; keeping the change is not.
- Commit to `main` and push.

## AMBER — do it, and write the entry in `human-queue.md` in the same pass

Reversible, but someone should know by morning.

- Change a function signature, or the shape of anything returned to a caller.
- Change an error message, exit code, or log level a user could be parsing.
- Add or rename a test file, module, or CLI flag.
- Change anything in `.github/`.
- Refactor across more than three files.

State in the queue entry what changed, what you ran, and how to revert it.

## RED — never alone. Write it to `human-queue.md` and move on

Not a matter of confidence. The loop does not do these things.

- **Edit a published number, or any file that carries one** — `docs/free-ceiling-measured.md`,
  `docs/free-ceiling-report.md`, `README.md`, `CHANGELOG.md`, `docs/humanizer-*`. Those
  numbers were measured under stated conditions by a human. A number changed by an unattended
  loop is a number nobody can cite.
- **Change a detection threshold, a default tier, a default rewriter, or a scoring weight.**
  Those are the product. Changing one silently changes every result anyone has ever quoted.
- **Add, remove, or upgrade a dependency**, including a dev one.
- **Delete, skip, or `xfail` an existing test**, or narrow an assertion to get green.
- **`git reset --hard`, `git rebase`, `git push --force`, delete a branch, rewrite history.**
  Another session commits to this repo. One `reset --hard` already destroyed its work once.
- **Tag, release, bump a version, publish anything.**
- **Touch a credential, token, `.env`, or anything under `_private/`.**
- **Call a paid API** — the hosted rewriter providers cost money per call.
- **Start a training run.**
- **Rewrite or relax anything in this file, `audit-loop.md`, or `audit_next.py`'s refusals.**
  A loop that can widen its own envelope has no envelope. If a rule blocks work that should
  be allowed, put *that* in the queue.

## The rule behind the rules

A missed finding costs one pass. A fabricated finding, a silently changed default, or a
published number edited by a robot costs the credibility of every number in the repo — and
that is the whole product. When the choice is between doing something and writing it down,
write it down.
