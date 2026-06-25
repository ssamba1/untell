# Rewrite rubric

Apply this when producing each rewrite in the loop. Goal: raise perplexity and burstiness (the
two signals detectors key on) **without** changing meaning, facts, or any `⟦HZxxxx⟧` sentinel.

## The 6 AI signals to kill (check every rewrite against these)

Detectors and the strongest competitors key on these. Neutralize each:

1. **Cliché / overused phrases** — "in today's world", "plays a vital role", "navigate the
   complexities", "it is worth noting". Cut or replace with specific wording.
2. **Formulaic transitions** — "Moreover/Furthermore/Additionally/Overall/In conclusion". Remove or
   make concrete.
3. **Sentence-length uniformity** (low burstiness) — vary lengths hard; mix very short with long.
4. **Vocabulary homogeneity** — AI reuses a flat, mid-frequency register. Add precise, varied,
   occasionally unexpected word choices (without thesaurus-bombing).
5. **Low perplexity** (predictable next word) — substantively rephrase the most-expected spans.
6. **Neat parallelism / aphorisms** — tidy antithesis ("it's all of us, or none of us") and balanced
   tricolons read as machine. Break the symmetry; make it a little uneven, like a person wrote it.

If the loop gives you **specific flagged sentences**, rewrite *those* the hardest — that is where the
detector's signal is concentrated.

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
- **High `roberta_openai` / `mage` / `hc3_roberta`** (supervised) → break structural regularity: vary
  openings, remove formulaic transitions, add concrete detail, restructure paragraphs.
- **High `fast_detectgpt` / `binoculars`** → reduce token predictability: more substantive
  rephrasing of high-probability spans, not just surface swaps.
- **High `radar`** (paraphrase-robust — the hardest) → surface paraphrasing won't move it. Restructure
  at the idea level: reorder the argument, merge/split ideas, change the framing, add a genuinely human
  aside. RADAR was trained against paraphrasers, so out-paraphrasing it fails; out-*thinking* it works.

## Don't

- Don't pad length or add filler to change statistics — it hurts similarity and reads worse.
- Don't introduce errors, typos, or unnatural phrasing as an evasion trick.
- Don't touch sentinels. Ever.
