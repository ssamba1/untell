# Ruff exemption policy for `.claude/probes/`

Status: **active, enforced** — resolved by issue #41 (commit "Closes #41").

## What is exempted

Every `*.py` file directly under `.claude/probes/` is exempted from **all** ruff lint
rules, via the blanket per-file-ignore in `pyproject.toml`:

```toml
[tool.ruff.lint.per-file-ignores]
".claude/probes/*.py" = ["*"]
```

This is the *documented per-file exemption policy* the issue's acceptance calls for: the
probes do not pass `ruff check` on their own (718 errors at resolution time, across the
tracked probe set), so they are exempted **explicitly and by pattern**, never by accident.

## Why probes are exempted (rationale)

1. **Not shipped code.** `untell/`, `tests/` and `scripts/` are what users install, run
   and get quality guarantees about; probes are one-off audit/diagnostic scripts that live
   inside `.claude/` and are never installed or imported by the package. The repo's
   zero-tolerance lint gate (dedicated `ruff` job in `.github/workflows/ci.yml`) applies
   to shipped code, and that gate is what protects users.
2. **Their conventions are deliberate.** Probe scripts are written fast during an audit
   session and frequently copied/adapted between probes. They routinely use
   `sys.path` shims before imports (E402), multi-import one-liners (E401/E701/E702),
   imports kept purely for side effects (F401), and single-letter loop variables in
   throwaway loops (B007). Enforcing the shipped-code style on them would slow the audit
   loop down for zero user-facing benefit.
3. **Autofixing them is risk without reward.** 581 of the 718 errors are auto-fixable,
   but the fixes churn 259 tracked files and can change probe behaviour (removing an
   import that matters for its side effect, reordering an import block that a `sys.path`
   shim depends on). The probes' real correctness gate is that the audit loop *runs*
   them; linting them adds noise, not safety.
4. **`ruff check .` stays a working tripwire.** Because the exemption is scoped to
   `.claude/probes/*.py` only, every *other* Python file in the tree — shipped code,
   `.claude/guard.py`, `.claude/audit_next.py`, `.claude/collect_swarm.py` — is still
   linted by the whole-tree check. A blanket `extend-exclude` of `.claude` (the option
   the wave-3 queue entry floated) would have hidden the tooling too; the per-file
   policy does not.
5. **Syntax errors are still caught.** Per-file-ignores suppress lint *rules*, not
   parse errors: a probe that cannot parse still fails `ruff check .` and any run of it.

## How coverage is enforced (drift protection)

`tests/test_probe_ruff_policy.py` asserts, on every CI run:

* the policy document exists and names the exemption pattern;
* **every** `*.py` file under `.claude/probes/` is matched by at least one
  per-file-ignore pattern (a new probe dropped outside the pattern fails the build);
* every listed pattern still matches at least one file (a dead pattern = policy drift);
* `ruff check .` exits 0 end-to-end (ruff installed), which also proves the exemption
  actually takes effect in the version of ruff CI resolves.

So the debt is zero-tolerance *by policy*: the number of exempted files is always equal
to the number of files the policy lists, by construction.

## History

* 2026-08-15 (wave 3, slice 9): 259 probe scripts (~705 ruff errors) committed by the
  fanout campaign; shipped-code lint fixed in `fca0c0c`; the probe debt was queued as a
  structural decision in `.claude/human-queue.md`.
* 2026-08-16 (wave 4, slice 1, issue #41): shipped-code lint reduced to zero again
  (11 errors fixed, incl. the `text_split.py` W605 the queue entry tracked); this
  exemption policy adopted as the resolution; dedicated `ruff` job added to CI.
