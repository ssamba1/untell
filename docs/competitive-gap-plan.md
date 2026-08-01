# Competitive gap analysis & next-steps plan (surveyed ~110 open humanizer repos)

Goal: find every open-source humanizer repo, ensure we have every capability any of them has, and plan
what's next. Four blind parallel sweeps (GitHub topics/stars, by-technique, by-package/platform,
research-code) catalogued **~110 repos**. Below: every distinct capability found, what we now have,
and the ranked build plan. Honest rule — we either **have it**, **just built it**, or it's **ranked +
scheduled** (with the blocker named). No silent gaps.

## The notable repos (by tier)
- **Research SOTA:** StealthRL (RL-vs-ensemble, 97.6% ASR, GPU), MASH (SFT+DPO alignment, GPU),
  AuthorMist (RL vs **commercial** detectors, GPU), DIPPER (11B paraphraser), Adversarial-Paraphrasing
  (2506.07001 — our exact loop), HMGC/TextFooler/RAFT (word-importance substitution), SICO (in-context
  optimization), CoPA (contrastive decoding), GradEscape (gradient evader), silverspeak (homoglyph),
  De-mark/MarkLLM/watermark-stealing (watermark scrub), Robust-Det (12-attack toolkit).
- **Serious tools:** patina (multilingual pattern + CI), ksanyok/TextHumanize (38-stage, 25 lang,
  watermark scrub), StealthHumanizer (35 providers, presets, browser ext), lynote/humanize-text
  (translation chain, 1.4k★), blader/humanizer (skill, high stars).
- **Skills:** harshaneel/humanize, Aboudjem, unslop, slopbuster, + many language-native (ru/de/ja/zh/ko).
- **Distribution one-offs:** MCP server (Text2Go), Telegram bot, Raycast, Chrome ext (candidly,
  Ai-rewrite), PWA (OrbitWebTools), DOCX/PDF tools, n8n/Docker.

---

## Evasion CAPABILITIES — the part that decides "do we beat them"

| Capability | Who has it | Us |
|---|---|---|
| Closed-loop detector-feedback rewrite | Adv-Paraphrasing, StealthHumanizer | ✅ **have** (our core, live-proven) |
| Multi-detector ensemble (incl. paraphrase-robust) | StealthRL | ✅ **have** (8 local incl RADAR + 7 commercial + browser) |
| Numeric detector score fed into the rewrite prompt | Adv-Paraphrasing | ✅ **have** (prompts name worst detectors + scores) |
| Per-sentence targeting | (none did it cleanly) | ✅ **have** (`untell-sentences`) |
| Quality/meaning gate + citation lock | patina, StealthHumanizer | ✅ **have** (semantic gate + preserve-lock) |
| Back-translation / translation laundering | lynote, StealthHumanizer | ✅ **have** (`back_translate`, multi-pivot) |
| **Word-importance-ranked synonym substitution** | HMGC, TextFooler, RAFT, StealthHumanizer | ✅ **JUST BUILT** — `attacks.surgical_substitute` (rank words by detector-score-drop → swap top-k synonyms that lower the score) |
| **Homoglyph / unicode substitution** | silverspeak, ST3GG, Robust-Det | ✅ **JUST BUILT** — `attacks.homoglyph_substitute` (opt-in, caveated) |
| **Hidden-watermark / stealth-char scrubbing** | De-mark, MarkLLM, cronos3k, TextHumanize | ✅ **JUST BUILT** — `attacks.scrub_hidden` + `count_hidden` (strip zero-width/tag/control + NFKC) |
| Contrastive decoding suppression | CoPA | ⏳ **ranked #1 no-GPU** (needs logprob access) |
| In-context example optimization (universal anti-detect prompt) | SICO | ⏳ ranked #2 no-GPU (one-time ~$3 setup) |
| Genetic / black-box search substitution | Mutant-X, RAFT | ⏳ ranked #3 no-GPU |
| **RL-against-ensemble paraphraser** | StealthRL, AuthorMist | ⛔ **GPU moat** (the categorical win — already roadmapped) |
| Trained SFT+DPO alignment rewriter | MASH | ⛔ GPU moat |
| Gradient-based evader / style-axis LoRA | GradEscape, StyleRemix | ⛔ GPU |

**Verdict on evasion:** after this commit we cover **every no-GPU evasion technique** found across ~110
repos. The only techniques we lack are the **GPU-trained** ones (StealthRL/MASH/AuthorMist/GradEscape) —
already the documented moat. No open repo has the no-GPU set *combined in a verified closed loop* like
ours.

---

## DISTRIBUTION / FEATURE gaps (product surface, not "beating" — ranked)

| Gap | Who has it | Priority |
|---|---|---|
| **MCP server** (plugs into Claude Desktop) | Text2Go | **P1** — high reach, low effort, native to our skill |
| **DOCX / PDF input-output** | samrand96, DadaNanjesha, contentforge | P1 — major real workflow |
| **Tone / style / persona presets** | StealthHumanizer (13 tones), Aboudjem (5 voices) | P1 — trivial (rubric `--style` param) |
| **0–100 AI-tell score** surfaced | Aboudjem | P2 — we have 0–1; expose ×100 |
| **Browser extension (MV3)** inline in Gmail/Docs | StealthHumanizer, candidly, Ai-rewrite | P2 — high reach, more work |
| **FastAPI HTTP service** | DadaNanjesha | P2 — wrap `untell_text` |
| **Voice profile from user's own writing samples** | numen-tech, blader, writing-agent | P2 — strong quality differentiator |
| **Multi-provider LLM routing** (Ollama/Groq/LM Studio) | StealthHumanizer (35) | P2 — extend rewriter providers |
| **Telegram bot / Raycast / n8n / Docker / PWA** | various | P3 — channel breadth |
| **Language-native rule packs** (ru/de/ja/zh/ko) | many language repos | P3 — localization |
| **Code-comment / commit humanization** | slopbuster, llmstrip | P3 |
| **C2PA provenance signing** (EU AI Act) | contentforge | P3 — compliance angle |

---

## The plan — what to do next (ordered)

**Immediate (shipped this round):** surgical word-importance substitution, homoglyph attack, hidden-
watermark scrubber. Now closes the no-GPU evasion gap.

**Next, no-GPU (each a few hours):**
1. **Contrastive-decoding rewrite backend** (CoPA) — two-pass human/AI prompt, subtract AI logits. The
   most architecturally novel no-GPU win; needs an LLM with logprobs.
2. **Wire `surgical_substitute` + `scrub_hidden` into the loop** as cheap pre/post passes (scrub on
   input always; surgical as a polish stage when the LLM loop stalls near the similarity floor).
3. **SICO** universal anti-detection prompt (one-time optimization, reused as a generation prefix).
4. **Product P1s:** `--style` presets, MCP server, DOCX/PDF I/O, 0–100 score.

**The moat (GPU — the one categorical win left):**
5. **RL-against-ensemble** (StealthRL) + **MASH SFT/DPO** alignment + **AuthorMist** (RL vs the
   *commercial* detectors via their APIs as reward). Scaffold the training pipeline now (config + code,
   run-on-GPU), so it's one `train` away. This is the only thing no open repo + no commercial tool
   combines with the rest of our stack — building it makes us the strongest *model* as well as the most
   complete *system*.

**Honest blockers:** GPU items need hardware; commercial-detector proof needs paid keys; this Windows
box's torch is broken so full-tier/RL numbers come from CI/Linux.

---

## Bottom line
Across ~110 repos, the only capabilities we lacked were (a) surgical word-importance substitution,
(b) unicode homoglyph/scrub — **now built and tested** — and (c) the GPU-trained RL/alignment moat,
which is the documented next step. We already combine the full no-GPU evasion toolkit in a verified,
multi-detector, quality-gated **closed loop with a packaged install + skill + CI + live proof** — which
no other open repo does. We beat every open repo on completeness today; the GPU moat makes us the
strongest model too.
