# Auditing a detector with untell

A guide for the people who have to decide how much a detector score is worth: integrity offices,
procurement and IT teams, researchers, advisors, and students or their representatives facing a
flag. Everything here runs on a laptop; nothing is uploaded unless you point untell at a
commercial detector's API yourself.

## Which question are you asking?

| question | tool | output |
|---|---|---|
| "This one document was flagged. Does the flag hold up?" | `untell brief` | an evidence brief (Markdown, HTML or JSON) |
| "Is the verdict on this document stable?" | `untell stability` | per-variant scores and a one-sentence finding |
| "What does a 1% false-positive rate mean for 2,000 students?" | `untell flagmath` | Bayes on a flag, per-person false-flag risk |
| "How does this detector do on *our* writers?" | `untell report-card` | false-positive rates by slice, with 95% intervals |
| "Did the vendor change something since last term?" | `untell drift` | significant changes between two report cards |
| "We need human text nobody can dispute is human." | `untell capsule` | prose from git history before 2022-11-30 |

## 1. One flagged document

```bash
untell brief --file essay.txt --detector gptzero --documents 12 --format html --out brief.html
```

`--documents` is how many documents this person has submitted in total, which is what turns a
per-document error rate into a per-person one. `--writer non-native` selects published rates
measured on non-native English writers, where they exist; a general-population rate is never
silently applied to a population it was not measured on.

**For a detector with no API** (Turnitin, most web interfaces), generate the scoring kit, score each
file in the detector's own interface, and fill in the CSV:

```bash
untell variants --file essay.txt --out kit       # kit/base.txt, kit/N1.txt ... kit/scores.csv
untell brief --file essay.txt --detector manual:kit/scores.csv --name turnitin --documents 12
```

`scores.csv` accepts a probability (`0.87`) or a percentage (`87`) in `score`, and an optional
`yes`/`no` in `flagged` when the interface shows a verdict rather than a number. `--name` is used to
look up the detector's published error rates. The browser kit (`docs/brief.html`) does the same
thing offline.

With only the score the detector reported, and no time to score the variants yet,
`untell brief --file essay.txt --detector turnitin --score 0.82 --flagged yes` still builds the
brief from the published rates and the Bayes arithmetic; the stability section says it was not
run. A brief never shows untell's own detector as if it were the one named: when the two differ
(`--detector local --name turnitin`), section 1 says the scores are untell's.

**Reading the result.**

- *Null* variants contain exactly the same words in the same order — checked mechanically, and a
  variant that fails the check is dropped. If the verdict flips across them, the score is
  responding to typography, and that is strong evidence it should not be relied on for that
  document.
- *Light* variants are routine copy-edits (contractions, an Oxford comma, US/UK spelling). They
  change characters inside words, so they are reported separately and never pooled with null.
- **No flips is not exoneration.** It means this test found no instability, nothing more.
- Wilson 95% intervals accompany every flip rate; with ten variants the interval is wide, and the
  brief says so.

## 2. A detector over your own corpus

```bash
untell report-card --detector pangram --detector-version "4.1" \
  --human students-2021.jsonl --human esl-2021.jsonl --ai generated.jsonl \
  --json-out cards/pangram-2026-11.json --out cards/pangram-2026-11.md
```

A corpus is a `.jsonl`, `.json` or `.csv` with a `text` field, or a folder of `.txt`/`.md` files.
Optional fields:

- `group` — the slice the document belongs to: `non-native`, `grade-9`, `engineering`, … These
  are where published evidence finds detectors failing. A report card without them measures the
  easy case.
- `author` — lets the card report the share of *writers* flagged at least once, which is what an
  honest student actually experiences.
- `label` — `human` or `ai`; defaults to the flag you loaded the file with.

**Designing a corpus that means something**

- **Provenance first.** Text written after late 2022 may be partly machine-assisted, and a
  "human" corpus contaminated with AI text makes a detector look worse than it is. Prefer work
  that predates the tools (archived submissions, `untell capsule` on old repositories), and record
  how you know.
- **Consent and privacy.** Student work is personal data. Get consent or use work you are licensed
  to process, and keep the corpus local — report cards store document IDs and scores, not text.
- **Size.** A false-positive rate from 40 documents has a 95% interval about ±9 points wide at
  zero. If the rate you care about is 1%, you need hundreds of human documents per slice to say
  anything; the card's intervals make this visible rather than hiding it.
- **Length.** Report by length; the card buckets automatically (<150, 150–299, 300–599, 600+ words).
- **Recall at a capped false-positive rate.** With an AI corpus the card reports how much AI text
  is caught when no more than 0.5%, 1% or 5% of humans may be flagged — the operating point an
  accusation needs, and how the strongest independent study reports results.

## 3. Silent model changes

Vendors update models without notice. Re-run the same card on the same corpus and compare:

```bash
untell drift cards/pangram-2026-05.json cards/pangram-2026-11.json
```

`drift` checks that the corpus fingerprints match, flags any metric whose 95% intervals do not
overlap, and lists every document whose verdict changed. It exits 1 when something changed
significantly, so it can gate a CI job. The repository's own
[observatory workflow](../.github/workflows/observatory.yml) does this monthly for every
detector with a configured key.

## 4. Things to check before you publish

- **Terms of service.** Some commercial licences restrict benchmarking or publishing results. We
  have not reviewed every provider's current terms; check them before publishing a report card.
- **Cost.** A report card calls the detector once per document, plus up to ten times per document
  in the stability sample (`--stability-sample`, default 20; set 0 to skip).
- **Version.** Record `--detector-version`. Pangram's adapter records the model version the API
  reports; for the others, note what the vendor says on the day.
- **Thresholds.** Commercial adapters flag at `--threshold` (default 0.5) on the score the API
  returns. If the vendor's interface flags at a different level, pass it, and say which you used.
- **Published figures.** [`published_rates.json`](../untell/evidence/published_rates.json) marks
  each entry `primary` (read in the source), `summary` (seen in a secondary report) or `vendor`
  (the detector's own claim). Quote them with that label.

## Over MCP or HTTP

The same commands are tools (`brief`, `stability`, `variants`, `flagmath`) on the MCP server and
endpoints (`POST /brief`, `/stability`, `/variants`) on the REST server. On those surfaces
`cmd:` and `manual:` detector specs are refused — they would let a remote caller or a
prompt-injected model run commands or read files — and recorded scores are passed inline as
`scores={"base": 0.91, "N1": 0.12, …}` instead. The REST server refuses commercial detectors
unless the operator sets `UNTELL_API_ALLOW_COMMERCIAL=1`, because each call spends their credit.
`brief` also takes the verdict as the detector reported it (`score`, `flagged`); with a `name` and
neither `detector` nor `scores`, it skips the stability test rather than running untell's own
detector in the named one's place.
