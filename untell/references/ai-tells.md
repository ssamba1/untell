# AI writing tells — the avoidance catalog

The single rule for every rewrite: **the output must contain NONE of the patterns below.** These
are the features that mark text as machine-written — to detectors *and* to readers. Load this with
`prompt-rubric.md` before rewriting.

> **Why "avoid", not "invert".** The goal is prose that reads like a real, slightly-careless person
> wrote it — not prose engineered to beat a perplexity score. Several of these tells (ESL-flagged
> uniformity, em-dashes, thesaurus reaches) get *added* by naive humanizers and are exactly what a
> strong detector is trained on. When a plainer phrasing reads more human but scores marginally
> higher locally, choose the plainer phrasing. Natural beats statistically-optimal.

---

## The 20 highest-signal tells (scan for these first)

1. **Em-dashes (`—`).** The most measurable single tell (GPT-4.1 ~10 per 1,000 words, persists even
   when told to stop). Never add one. Use a period, comma, parentheses, or rephrase.
2. **The "delve" vocabulary cluster** — delve, tapestry, testament, realm, landscape, robust,
   pivotal, seamless, intricate, multifaceted, meticulous, showcasing, underscores, garnered. One is
   weak; several in one passage is a strong tell. (delve was +6,697% in science writing post-2022.)
3. **Low burstiness / "perfect rectangle" paragraphs** — every sentence 14–22 words, every paragraph
   3–5 sentences of similar length. No very short lines, no long winding ones.
4. **Negated contrast** — "It's not X, it's Y", "Not only X but also Y", "This isn't about X; it's
   about Y", "All the X. None of the Y." Cut it.
5. **Compulsive rule-of-three / tricolons** — "fast, simple, and effective"; "Fast. Simple.
   Effective."; three-verb chains. Break the symmetry.
6. **Participial-phrase trailers** — sentences ending "…marking a pivotal moment", "…underscoring its
   importance", "…reflecting a broader shift". A floating `-ing` clause that restates the sentence.
7. **Vague attribution** — "studies show", "research suggests", "experts believe" with no name, date,
   or source.
8. **Formulaic transitions as paragraph openers** — Moreover, Furthermore, Additionally, Notably,
   Importantly, In conclusion, Overall, Ultimately — especially starting body paragraphs.
9. **Sycophantic / preamble openers** — "Certainly!", "Absolutely!", "Great question!", "Sure,
   here's…", "Let me break this down."
10. **Promotional register mismatch** — brochure words ("vibrant hub", "thriving ecosystem",
    "nestled within", "rich tapestry") in technical, academic, or journalistic text.
11. **False both-sides balance** — mechanical pros/cons that resolve nothing; "the truth lies
    somewhere in between" with both halves vague.
12. **Over-structured markdown in prose** — 3+ headings in <300 words, 8+ bullets in <200 words, a
    bold lead-in on every bullet, emoji in section headers.
13. **No concrete particulars** — no real names, dates, prices, places; generic examples ("imagine a
    company that…"); placeholder names (Emily/Sarah dominate AI examples).
14. **Closing meta-phrases** — "I hope this helps!", "Let me know if you need anything else", "Feel
    free to reach out."
15. **Inflated copula** — "serves as", "marks", "represents", "boasts", "features" used for plain
    "is"/"has".
16. **Paragraph-reshuffle failure** — body paragraphs that could be reordered without anyone noticing;
    no load-bearing connection between them.
17. **False-range constructions** — "from ancient civilizations to modern startups", "whether you're a
    beginner or a seasoned pro." Unearned breadth.
18. **Specificity-absent + over-comprehensive** — covers every angle at the same shallow depth, drills
    into none, states no actual view. (The two together are more diagnostic than either alone.)
19. **Significance inflation** — routine things called "pivotal", "watershed", "landmark"; paragraphs
    that end on a pseudo-profound pull-quote.
20. **Reader-steering adverb openers** — "Interestingly,", "Notably,", "Importantly,", "Surprisingly,"
    telling the reader how to feel instead of letting the content do it.

---

## 1. Banned vocabulary (use the plain word)

**Always replace (high-frequency AI markers):**
delve→explore/dig into · leverage→use · utilize→use · robust→strong/reliable · seamless→smooth ·
tapestry→(describe it) · testament→shows/proves · realm→area/field · landscape→field/space ·
navigate (figurative)→handle/work through · underscore→show/highlight · pivotal→key/important ·
crucial/vital→important/needed · foster→build/encourage · garner→earn/get · bolster→strengthen ·
elevate→raise/improve · embark→start/begin · harness→use/draw on · unlock/unleash→(say what happens) ·
spearhead→lead · paramount→most important · plethora/myriad→many/a lot of · multifaceted→complex ·
nuanced→(name the nuance) · intricate→detailed/complex · meticulous→careful/thorough ·
comprehensive→complete/full · vibrant→busy/lively · bustling→busy · noteworthy→(say what it is) ·
groundbreaking/cutting-edge→new/latest · transformative→(say how it changes things) ·
innovative→new/creative · boasts→has · serves as→is · nestled→sits in/is in · profound→deep ·
holistic→whole/complete · actionable→practical/concrete · impactful→effective/significant ·
streamline→simplify · empower→enable/let · revolutionize→change · resonate→connect/land ·
align→match/fit · encompass→cover/include · paradigm→model/pattern · ecosystem (metaphor)→system ·
cornerstone/bedrock/beacon→(plain noun) · poised to→ready to/about to · burgeoning→growing ·
quintessential→typical/classic · overarching→main/broad · synergy→(cut it) · endeavor→try/effort ·
commence→start · ascertain→find out · keen→strong/sharp · embrace (metaphor)→adopt/take up.

**Flag when 2+ appear together (cluster tells):** illuminate, cultivate, catalyze, reimagine,
galvanize, augment, elucidate, unpack, interplay, underpin, compelling, unprecedented, exceptional,
remarkable, sophisticated, invaluable, relentless, unwavering, dynamic, scalable, bespoke, world-class,
state-of-the-art, best-in-class.

## 2. Banned phrases & clichés

Openers: "in today's fast-paced/digital/modern world", "in the ever-evolving landscape of", "in an
era where", "as technology continues to evolve", "when it comes to", "at its core", "at the end of the
day", "the world of X", "in the realm of", "this is where X comes in."

Signposting: "it's important to note", "it's worth noting", "it cannot be overstated", "one of the
most important", "plays a crucial/pivotal/vital role", "stands as a testament to", "underscores the
importance of", "reflects a broader trend toward", "marks a significant shift."

Action clichés: "let's dive in", "dive into / deep dive", "shed light on", "pave the way", "navigate
the complexities of", "unpack / unravel", "embark on a journey", "explore the intricacies of."

Closings: "in conclusion / in summary / to summarize", "the future looks bright", "only time will
tell", "one thing is certain", "as we move forward", "the journey doesn't end here", "despite
challenges, X continues to thrive."

Promo: "a vibrant hub of innovation", "a thriving ecosystem", "rich cultural heritage", "breathtaking
landscapes", "a rich tapestry of", "game-changer / game-changing."

## 3. Formulaic transitions

Avoid as connective scaffolding (use plain *but / and / so / though / still*, or nothing):
Moreover, Furthermore, Additionally, Notably, Importantly, In conclusion, In summary, Overall,
Ultimately, Thus, Therefore, As such, Accordingly, Hence, In essence, That said, On the other hand,
Subsequently, Consequently, Nevertheless, Nonetheless, Similarly, Alternatively, Indeed, Essentially,
Arguably. Also drop "Firstly/Secondly/Thirdly" and "First… Second… Finally…" paragraph scaffolding.

## 4. Sentence structure

- **Don't flatten burstiness OR perform it.** Write naturally uneven prose: some short plain
  sentences, the occasional long one a person wouldn't bother to trim. Don't engineer the
  "staccato fragment + long winding clause" cadence — that *is* the humanizer fingerprint.
- No compulsive tricolons; no negated-contrast ("not X, it's Y"); no "not only… but also"; no
  participial-phrase trailers that restate the clause.
- Don't replace "is/has" with serves as / marks / represents / boasts / features.
- Don't stack hedge+modal ("could potentially", "may eventually", "might ultimately").
- Avoid "Let's …" collaborative openers and "which is" appositive padding.

## 5. Rhetoric / discourse

- No five-paragraph-essay shape forced onto every text; no restating the prompt; no conclusion that
  restates the body.
- No over-balanced both-sides hedging that resolves nothing. Take the position the source took.
- No significance inflation, no aphoristic pull-quote closers, no "this represents a broader shift"
  on ordinary points.
- No weasel attribution ("studies show / experts believe" without a name).
- No kitchen-sink over-comprehensiveness; keep the source's hierarchy of importance.

## 6. Punctuation

- **Em-dash = the #1 add-tell. Never add one.** (If the original had one, you may keep it.)
- No semicolons as a rhythm crutch — use two sentences.
- Don't make grammar unnaturally perfect: a real person's comma splice or mild run-on is fine to keep.
- Don't add smart/curly quotes in plain-text output; don't force Oxford commas everywhere.

## 7. Formatting / markdown

Match the source's format. Don't *add* structure prose didn't have: no new headings, no bullet-ifying
flowing prose, no bold on key terms, no emoji headers (🚀✅🔑), no "Key Takeaways/TL;DR" blocks, no
tables for simple comparisons. One bold item per section at most, and only if the source bolds.

## 8. Tone / register

- No sycophancy ("Certainly!", "Absolutely!", "Great question!", "You're absolutely right").
- No customer-service positivity or relentless upbeat flatline; keep the source's actual stance,
  including criticism and doubt.
- No fake-personal anecdotes ("Picture this…", "As a business owner you know…", "what surprised me
  most").
- No self-signaling significance ("Here's the kicker:", "But here's the thing:", "The best part?").
- No infomercial hooks ("but wait, there's more", "you won't want to miss this", "save this for
  later").

## 9. Content tells

- Keep the source's concrete particulars (names, dates, numbers, places) — never generalize them
  into "a study", "a company", "recently".
- Don't invent specifics to sound human either (that breaks meaning). Just don't *strip* the real
  ones.
- No perfectly balanced pros/cons with no stake; no "despite challenges, continues to thrive" filler.

## 10. Conversational / meta tells

Strip every chatbot artifact: "Sure, here's…", "Here's a breakdown", "Let me walk you through",
"In this article we will explore", "I hope this helps", "Let me know if…", "Feel free to reach out",
"Is there anything else", training-cutoff disclaimers, and any citation-leak junk
(`citeturn…`, `oai_citation`, `utm_source=chatgpt.com`, `[INSERT …]` placeholders).

---

## Claude's own tells (the rewriter is usually Claude — avoid these especially)

Claude (the model running `/untell`) has a measurable fingerprint. Watch your own output for:
em-dashes (Claude's natural rate ~9/1,000 — drop it to ~0); "Let me …" openers; heavy hedging
("It's worth noting that…", "Generally speaking…"); frequent first-person self-reference; long
multi-clause sentences with philosophical tangents; a consistently formal even voice. Strip all of
these from the rewrite — they are the exact signature a detector trained on Claude output looks for.

---

## Honesty note (keep the project honest)

These tells are *correlates*, not proof. The same uniformity that flags AI also falsely flags
non-native English writers (~61% false-positive in one study) and some neurodivergent writers, and
human accuracy at spotting AI is barely above chance. The aim here is writing that genuinely reads
as a person wrote it — not gaming a probability. Avoiding these patterns improves real readability;
it is not a guarantee of evading any specific commercial detector.

## Sources

Kobak et al. arXiv:2412.11385 & arXiv:2406.07016 (excess-vocabulary / "delve") · "The Last
Fingerprint" arXiv:2603.27006 (per-model em-dash data) · Wikipedia: Signs of AI Writing · Pangram
Labs pattern guide · GPTZero & Originality.ai (perplexity/burstiness) · Stack Overflow Blog "The AI
Ick" · Matthew Vollmer "Field Guide to AI Tells" · conorbronsdon/avoid-ai-writing · The Conversation
(negation) · OpenAI sycophancy rollback (Apr 2025).
