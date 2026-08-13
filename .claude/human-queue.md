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
