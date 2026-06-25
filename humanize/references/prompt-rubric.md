# Rewrite rubric

Apply this when producing each rewrite in the loop. Goal: raise perplexity and burstiness (the
two signals detectors key on) **without** changing meaning, facts, or any `⟦HZxxxx⟧` sentinel.

## Hard constraints (never violate)

1. **Preserve meaning.** Every claim, fact, and logical relationship in the original must survive.
   No new facts, no dropped facts.
2. **Keep every sentinel verbatim.** `⟦HZ0003⟧` and friends are locked spans (citations, numbers,
   quotes, entities). Carry each one through unchanged — same characters, same count, same place
   relative to its surrounding clause.
3. **Stay in the same language and register** the user expects (academic stays academic, etc.),
   unless they asked otherwise.

## Burstiness — vary sentence architecture

AI text is rhythmically uniform. Break that:

- Mix sentence lengths deliberately: follow a long, subordinate-clause-heavy sentence with a
  short one. Three words. Then something that winds.
- Vary sentence **openings** — don't start consecutive sentences the same way (subject-verb,
  subject-verb, subject-verb reads as machine).
- Occasionally restructure: split a compound sentence into two, or fuse two short ones.

## Perplexity — make word choice less predictable

- Replace the *most expected* next word with a precise, slightly less common synonym — but only
  where it reads naturally. Do not thesaurus-bomb into awkwardness (that tanks the quality gate).
- Cut formulaic connective tissue: "Moreover", "Furthermore", "In conclusion", "Overall",
  "It is important to note that", "plays a crucial role". Replace with concrete transitions or
  nothing.
- Prefer concrete specifics over generic phrasing where the original implies them.

## Human texture (use sparingly, only if register allows)

- A mild aside, a measured hedge ("roughly", "in practice"), or a parenthetical can raise
  perplexity naturally.
- Light, non-uniform punctuation variety (an em dash, a colon) where it fits.

## Use the detector feedback

- **High `perplexity_burstiness`** → the text is too uniform/predictable. Push hardest on
  sentence-length variance and word-choice surprise.
- **High `roberta_openai` / `mage`** (supervised) → break structural regularity: vary openings,
  remove formulaic transitions, add concrete detail, restructure paragraphs.
- **High `fast_detectgpt` / `binoculars`** → reduce token predictability: more substantive
  rephrasing of high-probability spans, not just surface swaps.

## Don't

- Don't pad length or add filler to change statistics — it hurts similarity and reads worse.
- Don't introduce errors, typos, or unnatural phrasing as an evasion trick.
- Don't touch sentinels. Ever.
