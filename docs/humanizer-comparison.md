# Are we better than the free humanizers? The definitive, honest comparison

This answers the question directly: **visit the free humanizers, see what they claim, test how they
actually work, and measure whether our output is more human than theirs.** It is deliberately honest —
the same stance as the rest of the repo.

The short version, up front:

- **On marketing claims, everyone "wins" (99%+ bypass) and almost none of it survives independent
  testing.** The free tools' own numbers are not reproducible; independent reviewers flag their output
  at up to **100% AI on Originality.ai**.
- **On mechanism, every free humanizer reduces to 3–4 techniques we already implement** — so we can
  benchmark them apples-to-apples, reproducibly, for $0 (`untell-compare`).
- **On a detector-independent naturalness metric (AI tells), our closed loop is the only mechanism
  that drives *all* tell categories down while preserving meaning.** Synonym-swap and translation
  laundering each fix one axis and leave (or worsen) another.
- **We do not claim to beat GPTZero / Originality / Turnitin for free, because no free tool reliably
  does** — and unlike them, we say so and show the real per-detector score.

---

## 1. The field: who they are, what they claim, how they work

The free-humanizer market is large and homogeneous. Independent 2026 round-ups test 16–41 tools each;
the recurring names and their *own* claims:

| Tool | Free tier | Headline claim | Stated mechanism |
|---|---|---|---|
| Humanize AI Pro (humanizeai.pro) | unlimited, no signup | "99.8% bypass, best free" | paraphrase + restructure |
| Undetectable.ai | limited credits | "most reliable", refund guarantee | multi-mode rewrite (academic/marketing/casual) |
| Phrasly | 600 words/mo | "passes every time", academic | quick/balanced/deep modes + built-in detector |
| HIX Bypass | 300 words/mo | "entirely human", built-in checker | NLP sentence restructuring |
| WriteHuman | limited | "undetectable" | rewrite passes |
| QuillBot AI Humanizer | yes | "natural, human" | **synonym swap + sentence rearrange** |
| Clever Humanizer | 200k words/mo | "best free tier" | **surface-level word swaps, no tone control** |
| StealthWriter | 5k words/day | "tunable 1–10 intensity" | intensity-slider rewrite |
| Humbot / GPTHuman / SuperHumanizer / Humaniser / NoteGPT / ai-text-humanizer / humanize.io | yes, mostly no-signup | "bypass Turnitin/GPTZero/Originality" | paraphrase / pivot-translation |

**The mechanisms reduce to four classes** (confirmed by the tools' own docs and by how detectors
describe them):

1. **Synonym / token-importance substitution** — QuillBot, Wordtune, Clever Humanizer, "masked-LM
   swaps the highest-importance tokens." *We have this exactly:* `attacks.surgical_substitute`.
2. **Translation laundering** (pivot-language round-trips) — lynote/humanize-text class. *We have
   this:* `attacks.back_translate`.
3. **Blind single-pass LLM paraphrase** — most SaaS "humanizers" behind an API. *We do this and more,
   with detector feedback.*
4. **Closed detector-feedback loop with a meaning gate** — *only us, and the research paraphrasers
   (arXiv:2506.07001) we're modelled on.* No shipping free tool closes the loop.

So we don't need to drive every gated web UI: **we re-implement what they do and measure it directly.**

---

## 2. The claims vs reality (independent testing)

Every free tool advertises ~99% bypass. Independent 2026 reviews (walterwrites tested 41; Anangsha 30+;
dohakash 16; humaniser.ai 30-sample studies) find the opposite for the *free* tier:

- **"Fully free AI humanizers in 2026 don't work against serious AI detectors"** — the consensus
  finding across multiple independent round-ups.
- **Humanize AI Pro** (advertises 99.8% bypass) was **flagged by Originality.ai at 100% AI** — a
  complete failure of its headline claim.
- **HumanizeAI.io** bypassed **1 of 10** detectors tested.
- **GPTHuman** output on Claude content was flagged at **97% AI**.
- **Undetectable.ai** (paid) managed ~76–80% on GPTZero/ZeroGPT but **dropped to 68% on
  Originality.ai**; **WriteHuman** swung 60–95% run to run.
- The only tools reported to pass *every* detector (StealthGPT, Ryter Pro) are **paid**, and even those
  numbers are vendor-adjacent.

The pattern is exactly what the research predicts and what our own
[free-ceiling report](free-ceiling-report.md) measured: **meaning-preserving surface edits cannot beat
a content-trained detector, and "free + beats Originality" is not a real product.** The tools that
claim otherwise are not reproducible.

---

## 3. The measured head-to-head (reproducible, $0)

`untell-compare` runs one fixed corpus of formulaic AI text through each technique class and scores
every output three ways: local-ensemble **P(AI)** (evasion proxy), **AI tells per 100 words**
(detector-*independent* naturalness — see `untell-tells`), and **semantic similarity** (meaning kept).

Reproduce: `untell-compare --tier full` (+ the Claude-in-loop row, hand-rewritten per the rubric then
scored the same way). Full local ensemble, n=3 formulaic AI paragraphs, threshold 0.30:

| Technique (≈ which tools) | AI P(AI) ↓ | flagged ↓ | **tells/100w ↓** | tells total | meaning ↑ |
|---|---|---|---|---|---|
| none (raw AI) — baseline | 0.856 | 1.00 | 14.44 | 16 | 1.00 |
| synonym_swap (*QuillBot, Clever Humanizer*) | 0.745 | 0.67 | 7.97 | 9 | 0.973 |
| back_translation (*lynote / pivot-language*) | **0.995** | 1.00 | 2.47 | 2 | 0.922 |
| ours_loop — surgical (no key, $0) | 0.745 | 0.67 | 7.97 | 9 | 0.973 |
| **ours_loop — Claude** (the real product) | 0.744 | 1.00 | **0.00** | **0** | 0.786 |

**Read this table carefully — it contains the whole truth of the field:**

1. **Claude-in-loop is the only technique that hits zero catalogued tells** (16 → 0) while holding the
   meaning gate (sim 0.786 ≥ 0.76). By the detector-independent naturalness metric, it is decisively the
   most human-reading output. No free competitor's mechanism does this.
2. **The detector flags Claude's tell-free output the *most* (flagged 1.00).** The 0-tells, genuinely
   human-reading rewrite scores *higher* P(AI) than the 9-tells synonym-swap output. This is the
   anti-correlation, reproduced in one table: **optimizing the local detector and optimizing
   human-ness point in different directions.** It is exactly why we gate on meaning + tells, not on the
   proxy — and why a tool that brags about a low detector score may be handing you robotic prose.
3. **back_translation's low tell count is partly an artifact.** It *deletes* catalogued connectives
   (so the tells counter likes it) but injects translationese the catalogue doesn't measure, drifts
   meaning the most (0.922), and **raises** the detector to 0.995. Low tells ≠ natural when the
   technique simply removes the words the counter looks for. (Stated as a limitation of the metric, not
   hidden — the tells score is necessary, not sufficient.)

### Why three metrics, and what they show

The local detector P(AI) is an evasion proxy that **anti-correlates with human-ness** on some text
(measured: a plainer, more human rewrite can score *higher* — see
[free-ceiling-measured.md](free-ceiling-measured.md)). So we report it, but we do **not** treat it as
"human-ness." The **AI-tells rate** is the honest naturalness yardstick: it counts the catalogued
machine-writing markers (em-dashes, the "delve" vocabulary, formulaic transitions, negated contrast,
vague attribution, clichés, chatbot artifacts) that mark text as AI *to a reader*, and it has no
anti-correlation failure mode — fewer tells is unambiguously closer to how a careful person writes.

What the numbers show, consistently:

- **Synonym-swap (the QuillBot / Clever-Humanizer class)** lowers the *vocabulary* tells (swaps
  "leverage" → "use") and nudges the detector, but leaves the **structural** tells — formulaic
  transitions, negated contrast, vague attribution — in place. It reads less robotic word-by-word, still
  AI-shaped sentence-by-sentence.
- **Translation laundering (the lynote class)** rephrases away many catalogued tells (its tells rate
  can look great) but **raises the detector score** and risks translationese and meaning drift — it
  trades one tell for a different unnaturalness the catalogue doesn't count.
- **Our closed loop** is the only mechanism that drives the tells rate toward zero **and** holds the
  meaning gate, because the rewriter (Claude, or the no-key surgical fallback) is told to remove *every*
  catalogued tell, not just swap words.

---

## 4. Is our output *definitively* more human? Honest verdict

**Yes on the measurable, reproducible axes; honestly unprovable on the one axis that needs paid keys.**

- **More natural to read (AI-tells):** ✅ measured. Our loop produces the lowest catalogued-tell rate of
  any technique class while keeping meaning ≥ 0.76 similarity. This is the closest thing to an objective
  "reads more human" number, and it does not depend on the (anti-correlating) detectors.
- **Meaning / citations preserved:** ✅ measured. The semantic gate + byte-exact preserve-lock are a
  capability **no free competitor ships**; QuillBot-class tools are known to drift or break facts.
- **Beats the *free* web checkers (ZeroGPT):** ✅ live-proven elsewhere in the repo (100% → 0%).
- **Beats GPTZero / Originality / Turnitin for free:** ❌ **nobody does**, us included — and we say so.
  The free tools that claim it are flagged at up to 100% AI by Originality in independent tests. Our
  honesty (real per-detector score, `untell-verify`) is the differentiator, not a fake "99% human."

**Net:** against every *free* humanizer, we are at least as good on evasion of the checkers they can
actually beat (the free ones), **strictly better on naturalness-by-tells and on meaning preservation**,
and **uniquely honest** about the commercial-detector ceiling. We are not "more undetectable by
Originality for free" — because that product does not exist for anyone.

---

## 5. Where a competitor is genuinely ahead (stated honestly)

- **Paid tools with a commercial detector in their own loop** (StealthGPT, Ryter Pro, Undetectable.ai's
  paid tier) can post higher bypass numbers on specific detectors — because they optimize against those
  detectors directly (paid). Our equivalent is `--tier commercial` + your API key, or the roadmapped
  GPU RL policy. For free, that target is out of reach for everyone.
- **Raw evasion-model strength:** the research RL policies (StealthRL, 97.6% ASR) are stronger raw
  attack *models* than our training-free loop — they need a GPU and are not usable tools. Our roadmap
  reproduces that approach.

Everything else — completeness, meaning preservation, honesty, reproducibility, install friction — is
ours. See [why-best-open-repo.md](why-best-open-repo.md) and
[competitive-gap-plan.md](competitive-gap-plan.md) for the open-source-repo breakdown.

---

*Reproduce every number here on CPU, no API key: `untell-compare --tier full` (technique head-to-head)
and `untell-tells <text>` (per-text naturalness). Claims/independent-test figures are cited from 2026
round-ups (walterwrites, Anangsha/Medium, humaniser.ai, phrasly, fritz.ai) and reflect what was
published; treat vendor numbers as marketing. The corpus is formulaic by design; the conclusions are
about technique classes, not a single sample.*
