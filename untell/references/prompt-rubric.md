# Rewrite rubric

Apply this when producing each rewrite in the loop. The goal is **not** to "raise burstiness/
perplexity" by performing variation — that produces a recognizable *humanizer voice* that detectors
(and people) catch. The goal is to make the text read like **an actual, slightly-careless person
wrote it**, while changing no meaning, facts, or `⟦HZxxxx⟧` sentinel.

> **Reality check.** The local detectors reward two surface things (sentence-length variance and
> uncommon words). Gaming those manufactures tells — em dashes, staccato fragments, thesaurus words,
> tidy aphorisms — and a strong detector like GPTZero is trained on exactly that "humanized" style.
> When a plainer phrasing reads more human but scores slightly higher locally, **choose the plainer
> phrasing.** Natural beats statistically-optimal.

## NEVER inject these — they are AI tells (this is the most important section)

> The exhaustive, sourced catalog is **`ai-tells.md`** — load it too. The items below are the
> highest-frequency tells a rewrite most often *adds*; `ai-tells.md` has the full list (banned
> vocabulary, phrases, structures, formatting, and Claude's own fingerprint) with plain replacements.

1. **Em dashes (`—`).** The single most recognizable AI signature. Do not add them. Use a period, a
   comma, parentheses, or just rephrase. If the original had one, you may keep it, but never *add*.
2. **Semicolons as a rhythm crutch.** A person writing casually rarely reaches for one. Use two
   sentences.
3. **The staccato + winding combo.** "Three words. Then a long subordinate-clause sentence that winds
   on." That cadence is the humanizer fingerprint, not human writing. Don't engineer it.
4. **Performed informality.** "not in a small way", "Powerful, then.", "Here's the thing", "And the
   junk? It rides the same rails." Forced punchiness reads as AI imitating a human.
5. **Balanced antithesis / tidy tricolons / aphoristic closers.** "it cuts both ways", "both benefits
   and challenges", neat three-part lists, a quotable final line. Machines love symmetry. Break it.
6. **Thesaurus reaches.** Swapping a normal word for a fancier "less predictable" one (reshaped,
   rewired, hinges, underpins) is itself an AI tell. Ordinary words are more human.

## Kill the original AI tells too

1. **Clichés / filler** — "in today's world", "plays a vital role", "it is worth noting", "navigate
   the complexities". Cut them.
2. **Formulaic transitions** — "Moreover / Furthermore / Additionally / However / In addition /
   Overall / Ultimately / In conclusion". Delete, or use a plain "but / and / so / though".
3. **Uniform sentence shape** — if every sentence is subject-verb-object of similar length, that's a
   tell too. But fix it by writing *naturally uneven* prose (below), not by performing variation.

## Hard constraints (never violate)

1. **Preserve meaning.** Every claim, fact, and logical relationship in the original must survive. No
   new facts, no dropped facts. (Adding vivid invented detail to sound human breaks this — don't.)
2. **Keep every sentinel verbatim.** `⟦HZ0003⟧` and friends are locked spans. Same characters, count,
   and position.
3. **Stay in the same language and register** the user expects. If the source is a plain essay, the
   output is a plain essay — not a blog-style monologue.

## Write like a real person (this replaces "maximize burstiness")

Real human writing is uneven *by accident*, not by design. Aim for that:

- **Plain words.** Say "changed", not "reshaped/rewired". "uses", not "leverages". Boring is human.
- **Ordinary connectors.** "but", "and", "so", "though", "also" — the words people actually use.
- **Mild, natural imperfection is fine and helps:** a small redundancy, a hedge ("probably", "kind
  of", "more or less", "I think"), a slightly long sentence that a person wouldn't bother to trim, a
  comma splice they'd write anyway.
- **Don't make every sentence "earn its keep."** Humans write unremarkable, throwaway sentences.
  A perfectly efficient paragraph where each line lands is an AI signature.
- **Vary openings** only because real paragraphs naturally do — not by rotating through structures.

## Use the detector feedback — with the caveat

- **High supervised scores (`roberta_openai` / `hc3_roberta` / `mage`)** → the structure/phrasing is
  too AI-regular. Rephrase substantively and plainly; don't just reach for fancier words.
- **High `fast_detectgpt` / `binoculars`** → token choices are too predictable. Rephrase the
  high-probability spans, but toward *plainer/normal* alternatives, not exotic ones.
- **High `radar`** (paraphrase-robust) → surface paraphrase won't move it; reorder or reframe at the
  idea level.
- **But:** all of these are *local proxies that do not predict GPTZero.* Do not contort the prose to
  satisfy a number. If meaning is intact and it genuinely reads like a person wrote it, that's the win
  — report the honest scores and stop, even if some local detector is still mid.

## Don't

- **Don't add em dashes, semicolons, or theatrical fragments.** (Repeated because it's the #1 mistake.)
- Don't thesaurus-bomb or reach for "interesting" words to lower perplexity.
- Don't pad length, invent detail, or inject typos/errors as an evasion trick.
- Don't touch sentinels. Ever.
