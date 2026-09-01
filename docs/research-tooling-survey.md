# Research tooling survey — what would make untell's research faster and wider

**Surveyed 2026-09-01.** A survey of repos and services that could improve *how this project does
research*, not what it ships. Every candidate below is matched to a limit this repository has
already written down about itself — mostly in
[`humanizer-census.md` § Coverage limits](humanizer-census.md#coverage-limits--what-this-census-still-cannot-claim)
and [`ROADMAP.md`](../ROADMAP.md).

Star counts are from the GitHub API on the survey date and drift daily. Nothing here was
benchmarked; this is a survey of *options*, and it says so.

---

## 0. Two planes, not one wall

Before recommending anything: what a Claude Code **web/remote** session can actually reach. The
first version of this section had it wrong in a way that matters — it read one wall where there
are two independent planes, and concluded more was blocked than really is.

**Plane 1 — the container's egress proxy.** Everything `curl`, `pip`, a script, or `WebFetch`
sends leaves through a policy-enforcing proxy. Probed 2026-09-01:

| host | result |
|---|---|
| `api.github.com`, repo-scoped | **200** — `repos/{owner}/{repo}/...` only |
| `api.github.com/search/*`, `/graphql` | **403** — "sessions are bound to their configured repositories" |
| `pypi.org`, `registry.npmjs.org`, `files.pythonhosted.org` | **bypass the proxy entirely** — package installs work |
| `arxiv.org`, `export.arxiv.org` | 403 |
| `huggingface.co` | 403 |
| `api.openalex.org`, `api.semanticscholar.org`, `api.crossref.org` | 403 |
| `repos.ecosyste.ms`, `grep.app` | 403 |
| `api.tavily.com`, `api.exa.ai` | 403 |
| `eutils.ncbi.nlm.nih.gov`, `pubmed.ncbi.nlm.nih.gov` | 403 |

Two things worth pulling out. `/rate_limit` cheerfully reports 15,000/hr core and 10,000/hr
GraphQL — real numbers describing a scope that cannot answer a census query, which is the trap
this section exists to mark. And `huggingface.co` being blocked means **`eval/datasets.py` cannot
stream RAID or MAGE from a remote session at all**; the eval harness is local-only here.

The proxy's own README is explicit that a 403 is an organization egress-policy denial, to be
reported rather than routed around. So this plane is not something to be clever about — it is a
list to hand to whoever owns the policy.

**Plane 2 — the MCP connector plane.** Connectors do not use that proxy. They travel via
`mcp-proxy.anthropic.com`, which sits in the proxy's own bypass list. This is not an inference;
it is measured:

```
curl https://eutils.ncbi.nlm.nih.gov/...   →  403, CONNECT rejected by egress policy
PubMed connector, same NCBI backend        →  909 results, live query translation from NCBI
```

Same destination, opposite outcome. **A connector reaches what a script cannot**, and that is the
whole answer to "how do we get access to everything".

### What is reachable right now, with nothing enabled

- **`WebSearch`** — server-side, does not touch the egress proxy. Broad web search works.
- **GitHub MCP tools** — `search_repositories` and `search_code` reach all of GitHub. This is the
  only global GitHub search available here, and it is what `census.py ingest` is built around.
- **PubMed connector** (authless, already connected) — 909 papers for
  `(ChatGPT OR "AI-generated text") AND (detector OR detection) AND (accuracy OR "false positive")`.
  Biomedical-only, so it will not carry the arXiv literature, but false-positive rates on human
  academic writing is exactly untell's headline claim and this is a live corpus for it.
- **`WebFetch`** — egress-bound, so `github.com` works and `arxiv.org` does not.
- **`git clone` of any public repository** — MEASURED 2026-09-01, and the most useful thing on
  this list. The GitHub *API* plane is bound to this session's own repository: `api.github.com`
  returns 403 outside it, and so do `codeload.github.com` and `github.com/…/archive/…`, both of
  which answer with the same "not enabled for this session" JSON. The **git proxy does not**.
  `git clone --depth 1 https://github.com/<owner>/<repo>` succeeds for arbitrary public repos, as
  does `raw.githubusercontent.com`. Sixteen third-party repos cloned in one batch for 18 MB.

  That asymmetry matters more than it looks, because §1's cost argument assumes reading a repo
  means paying an agent to read prose. It does not: the file tree is free. "Metadata cannot see
  whether the Python file beside the Markdown is the product" is true of *search-API metadata* and
  false of a shallow clone, which sees the Python file, its length, and whether it sits under
  `tests/`. Four of the nine confident `prompt-guide` rows below carry source code, and a clone
  separates a build script and a test harness from a product in one `find`.

### What to enable, and why each one

All of these route through the connector plane, so **none of them needs an egress change**. Enable
at claude.ai → Settings → Connectors:

| connector | closes | note |
|---|---|---|
| **alphaXiv** | the arXiv gap — §4's whole problem | `full_text_papers_search`, `get_paper_content`, `embedding_similarity_search`. This is what re-checks [arXiv 2506.07001](https://arxiv.org/abs/2506.07001), the paper the README's strongest external claim rests on. |
| **Exa** *or* **Tavily** *or* **Firecrawl** | §3, general web search | Firecrawl's connector is the widest single pick: `firecrawl_search` plus `firecrawl_research_search_papers` and `firecrawl_research_search_github` in one. Exa is the best semantic search; Tavily the best plain retrieval. |
| **Consensus** | claim-checking against the literature | One `search` tool over scientific papers, aimed at "what does the evidence say" rather than keyword recall. |
| **bioRxiv** | preprints, **authless** | Free to enable, no key. Marginal for this repo; listed because it costs nothing. |

Exa, Tavily, Firecrawl, alphaXiv and Consensus each need an account on the vendor's side.

### What only an egress change can fix

These must be reached *by a script*, so no connector substitutes for them:

- **`huggingface.co`** — without it `eval/datasets.py` cannot load RAID, MAGE or HC3 in a remote
  session. This is the one that blocks actual measurement work, and it is the first to ask for.
- **`api.github.com/search/*`** — would let `census.py harvest` run unaided here instead of the
  two-step MCP-capture-then-`ingest` dance.
- **`repos.ecosyste.ms`** — §2, the non-GitHub forge coverage.
- **`api.openalex.org` / `api.semanticscholar.org` / `api.crossref.org`** — only needed if the
  literature watch is scripted rather than run through alphaXiv/Consensus.

---

## 1. The census is already stale, and re-running it the old way is the wrong fix

The 2026-08-05 census read 435 of 1287 repos. Two things about it:

**It has decayed.** A single GitHub repo-search filtered to `pushed:>2026-06-01` surfaced
[`fromleda/text-humanizer`](https://github.com/fromleda/text-humanizer) — **733 stars, created
2026-08-10**, five days *after* the sweep. A repo that size in this field is not a rounding error;
it would place in the census's own star table. There will be others.

**Its stated failure mode was LLM spend, not GitHub.** The census records that the completeness
critics and 49 non-English reads "died on an API spend limit". The GitHub side was never the
bottleneck: with an ordinary PAT the search API serves 30 queries a minute, so the 624 queries that
produced 1287 candidates fit inside half an hour and cost nothing. What cost money was paying an
agent to read 435 READMEs.

So the fix is not a bigger sweep budget. It is to **stop paying an LLM to read READMEs that a script
can triage**:

1. **Harvest deterministically.** `search/repositories` returns name, stars, topics, pushed
   date, primary language and license, 100 per call. 1287 repos is a few dozen calls, not 1287
   agent turns. Implemented: `python .claude/census.py harvest`.
2. **Classify cheaply first.** The census's own categories (`prompt-guide`, `api-wrapper`,
   `rule-based-rewriter`, …) are partly decidable from metadata: a repo packaged as an agent skill
   is a prompt guide; a repo whose description names a vendor is an API wrapper. Those two
   categories are 60% of the census (259 of 435), which is the *ceiling* on this idea, and the
   ceiling is not reachable. **Measured on the real eleven-angle harvest** (111 repos, 26 of them
   already read by the census): `classify` decides **10.7%** without a reader — 35% on a single
   topic-filtered slice, but a tenth across the full 131-repo sweep. Unsure rows agree **11 of
   24**. Confident rows are now measured properly rather than spot-checked: all sixteen were
   shallow-cloned and read against source on 2026-09-01 (see *Confident rows, verified* below),
   which found one wrong, and the rule that produced it is fixed. The gap to 60% is not a tuning
   problem: those census categories were assigned by *reading source*, and metadata cannot see
   whether the Python file beside the Markdown is the product. A tenth of the reading is the
   honest saving from metadata alone; a clone raises it to roughly a third (see *Reading the
   source* below), and the rest is a reader's.
3. **Spend the LLM on the tail.** The interesting classes (`detector_in_loop`,
   `meaning_verification`) are the ones that need reading. That is where the budget should have gone
   the first time — and, MEASURED, it is where it still has to go. `inspect` reads the file tree
   of every repo for free and takes the decidable share from 6% to 32% of a held-out set, but it
   cannot settle these two, because a humanizer prompt guide names the detectors it aims to beat
   in the same words a pipeline uses to call them. It hands the reader a briefed queue instead.
4. **Store deltas, not sweeps.** `docs/humanizer-census.json` already carries the per-repo profile.
   A scheduled job that re-queries and diffs against it turns a one-off document into a maintained
   one, and makes "the census is from 2026-08-05" stop being a caveat.

### GitHub code search finds what README keyword search structurally cannot

The census names this exact gap — its completeness critics were meant to find "what keyword search
structurally cannot reach" and did not finish. Code search partly closes it, and it is free and
keyless. A probe run during this survey:

```
query: "humanize" "detector" language:python "while" in:file   →  1,562 files
```

with `jenna-russell/human_detectors` and `samrand96/Undetectable-AI` in the first five hits. Code
search matches *the loop itself* rather than the word "humanizer" in a README, which is precisely
the `detector_in_loop` field the census had to read 435 repos to fill. Budget is 10 queries/minute
— tight, but it is the only free tool in this document that reads source across all of GitHub.

**Caveat, and it is not small:** in a remote session, `get_file_contents` is scoped to
`ssamba1/untell` only. Search works across all of GitHub; *reading* another repo's files does not,
without `add_repo` or `WebFetch`. A harvester that pulls READMEs at scale is a local-checkout job.

---

## 2. Closing the "GitHub only" coverage limit

The census states plainly that GitLab, Codeberg, SourceForge and Gitea are uncovered because their
explore pages are JS-rendered.

**[ecosyste.ms](https://github.com/ecosyste-ms/repos)** is the direct answer. It is an open API
service providing unified repository metadata across GitHub, GitLab, Gitea and Forgejo — ~14.8M
repositories — at 5,000 requests/hour by IP with no key, plus **bulk compressed S3 exports**
intended for exactly this kind of academic sweep. The bulk export path also sidesteps the rate-limit
problem entirely: download once, query locally, no spend.

It is 403 from this session (see §0), so this is a local-run recommendation until the allowlist
changes.

Also considered: **[SEART GHS](https://seart-ghs.si.usi.ch/)** (735,669 repos, 25 mined
characteristics, built for MSR sampling, [MSR 2021 paper](https://arxiv.org/pdf/2103.04682)). Good
tool, wrong shape for us — it indexes 10 mainstream languages by repo *characteristics*, and this
field's long tail is small Markdown-only repos in Spanish, Portuguese and Korean that GHS's language
filter will not carry. Worth knowing about; not the fix here.

---

## 3. Web search, for the parts that are not GitHub

untell's research needs web search for three things the census cannot supply: commercial detector
behaviour, vendor claims, and literature currency.

| repo | ★ | what it is | fit |
|---|---|---|---|
| [`ihor-sokoliuk/mcp-searxng`](https://github.com/ihor-sokoliuk/mcp-searxng) | 1,183 | MCP server over a self-hosted [SearXNG](https://github.com/searxng/searxng) (36,348★) metasearch instance | **Best fit.** Free forever, no key, self-hosted, no vendor in the loop. Matches this repo's zero-dependency / $0 posture, and a self-hosted instance has no spend limit to die on. |
| [`exa-labs/exa-mcp-server`](https://github.com/exa-labs/exa-mcp-server) | 4,949 | neural/semantic search | Best of the hosted options for "find repos and papers *similar to this one*" — the query shape the census's keyword angles could not express. Metered past a free tier. |
| [`firecrawl/firecrawl-mcp-server`](https://github.com/firecrawl/firecrawl-mcp-server) | 7,358 (engine: 174,924) | scrape / crawl / map / extract | For enumerating a vendor's docs or a JS-rendered explore page. Strongest crawler; overkill for search alone. |
| [`tavily-ai/tavily-mcp`](https://github.com/tavily-ai/tavily-mcp) | 2,364 | RAG-shaped search | Fast, LLM-formatted results. Metered. |
| [`spences10/mcp-omnisearch`](https://github.com/spences10/mcp-omnisearch) | 347 | one MCP over Tavily + Brave + Kagi + Exa + Firecrawl + GitHub | Useful if you want to A/B providers behind one interface rather than commit. |

Recommendation: **SearXNG + `mcp-searxng`, with Exa as the paid escape hatch** for semantic queries.
The free/self-hosted default is not a compromise here — it is the option whose failure mode isn't a
spend limit, which is the failure mode this project has actually hit.

---

## 4. Literature currency

The README's strongest external claim — that iterative detector-feedback is the best training-free
technique in the literature — rests on [arXiv 2506.07001](https://arxiv.org/abs/2506.07001). A claim
of the form "nobody published better" decays silently, and nothing in the repo re-checks it.

| repo | ★ | sources |
|---|---|---|
| [`openags/paper-search-mcp`](https://github.com/openags/paper-search-mcp) | 2,542 | arXiv, PubMed, bioRxiv, medRxiv, Semantic Scholar, Crossref, OpenAlex, CORE, dblp, Zenodo, Unpaywall (~20) |
| [`benedict2310/Scientific-Papers-MCP`](https://github.com/benedict2310/Scientific-Papers-MCP) | — | arXiv + OpenAlex, with citation analysis and rate limiting |
| [`rpaszekdev/openalex-mcp`](https://github.com/rpaszekdev/openalex-mcp) | — | OpenAlex only; fetches full text of open-access papers |
| [`xingyulu23/Academix`](https://github.com/xingyulu23/Academix) | 9 | OpenAlex + DBLP + Semantic Scholar + arXiv + CrossRef |

`paper-search-mcp` is the obvious pick on coverage and maintenance. The narrow, honest version of
this: a monthly query for papers citing 2506.07001 or matching `detector-guided decoding` /
`adversarial paraphrasing`, appended to a ledger the same way `.claude/measurements.jsonl` records
measurements. All of these APIs are 403 from a remote session (§0).

---

## 5. The bot-gate on `browser_check.py`

`untell/browser_check.py` documents the problem exactly: probed 2026-06, QuillBot is behind
reCAPTCHA, GPTZero web redirects to a login app, Scribbr/Brandwell are iframe widgets, Writer
removed its tool, Sapling rate-limits. **ZeroGPT is the only clean one**, and the README's live
demo consequently rests on a single checker.

That is a stealth problem, and stealth has moved since the 2026-06 probe. Plain
`playwright-stealth` is deprecated and current Cloudflare checks detect it; the working tools patch
the browser binary, not the JS layer:

| repo | ★ | approach |
|---|---|---|
| [`daijro/camoufox`](https://github.com/daijro/camoufox) | 11,583 | Firefox fork, stealth patched at the C++ level — canvas, WebGL, AudioContext, font metrics, network timing. Reported 0% headless detection on standard bot tests. Playwright-compatible. |
| [`Kaliiiiiiiiii-Vinyzu/patchright`](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) | 4,241 | Playwright fork patched at the CDP layer; the maintained successor to `playwright-stealth`. **Closest to a drop-in** for the existing `[browser]` extra. |
| [`Johell1NS/browser-search`](https://github.com/Johell1NS/browser-search) | 510 | a Claude Code *skill* wiring SearXNG + Camoufox together, self-hosted and key-free |

`SiteConfig` is already config-driven, so the change is a driver swap, not a rewrite: `patchright`
first because it is API-compatible, `camoufox` if Cloudflare still wins.

**Two caveats, both load-bearing.** `browser_check.py`'s own warning stands — automating a free web
UI may violate that site's terms, and adding stealth makes that a deliberate act rather than an
incidental one, so it is the maintainer's call and not a default. And a second automatable checker
does not make the demo a *rate*; two paragraphs against two checkers is still a demonstration.

---

## 6. What is already covered — do not re-adopt

Checked against the repo so the recommendations above stay honest:

- **RAID** — `eval/datasets.py` already streams `liamdugan/raid` (and `yaful/MAGE`), and the README
  already points at the RAID leaderboard alongside IMGTB. What is *not* used is
  [`raid-bench`](https://github.com/liamdugan/raid) the **package** (`pip install raid-bench`, MIT):
  a detector-evaluation harness, 11 built-in adversarial attacks — homoglyph, zero-width space,
  whitespace addition, number swap, synonym swap, paraphrase — and a public leaderboard at
  raid-bench.xyz with a submission path. Three of those attacks are what `untell/attacks/` and the
  unicode scrubber already implement, which makes it an external cross-check on work already done,
  and the leaderboard is a route to numbers at a scale that answers the roadmap's own "n = 40 is not
  n = 15,310" complaint. That is the highest-value item in this document.
- **HumanizerBench** — already in `humanizer-census.json`, correctly categorised (`other`, no
  detector-in-loop). Worth revisiting as a *data source* rather than a competitor: it publishes
  monthly GPTZero / Originality.ai / Copyleaks / Winston / ZeroGPT verdicts with inputs, outputs and
  scoring code, across a dozen paid humanizer products. Those are exactly the commercial-detector
  numbers this project cannot buy and currently has to cite second-hand.
- **Deep-research agents** — `gpt-researcher` (29,228★), `Alibaba-NLP/DeepResearch` (19,898★),
  `dzhng/deep-research` (19,620★), `LearningCircuit/local-deep-research` (9,014★). Genuinely capable,
  and the wrong tool: an agent that synthesises prose is what produced a census whose numbers had to
  be hand-checked against raw profiles. What this project needs is a *deterministic harvester with an
  LLM tail*, per §1 — reproducibility is the thing it sells.

---

## 7. What shipped, and what is left

**Shipped: `.claude/census.py`** — the refresher from §1, built and measured rather than proposed.

```bash
python .claude/census.py plan                      # 12 angles, 43 queries, ~2 min of search budget
python .claude/census.py harvest --out out/x.json  # local checkout + PAT; refuses cleanly elsewhere
python .claude/census.py ingest a.json --out x.json  # remote session: fold in MCP-captured results
python .claude/census.py classify x.json           # structural triage, no LLM, no network
python .claude/census.py inspect x.json --only-unsure  # shallow-clone and read the file tree
python .claude/census.py verify x.json             # score either classifier against the census
python .claude/census.py delta x.json              # what the census would say differently today
```

`verify` is the part that matters: the census hand-read 435 repos, so any overlap is free ground
truth, and both classifiers are scored against it rather than trusted. It is what caught the tree
reader being confidently wrong about twelve repos while it looked, on the set it was built
against, like it had solved the problem. It reports the two buckets
separately because they promise different things — a wrong *confident* row is a defect (it dropped
a repo from the read queue on a bad rule), a wrong *unsure* row is the system working.

**The eleven-angle run is done.** 111 distinct repos captured across the plan's angles, folded
in with `ingest`, and diffed against the census. Raw harvest committed at
`.claude/probes/census-2026-09-01-multiangle.json`.

| | |
|---|---|
| repos seen | 131 |
| already in the census | 34 |
| **new** | **97** (19 of them at ≥100 stars) |
| moved by ≥50 stars | 7 |

Reproduce it: `python .claude/census.py delta .claude/probes/census-2026-09-01-multiangle.json`

The largest newcomers: `Nanako0129/sepia` (1,269★, **created 2026-08-28** — three weeks after the
sweep), `LearnPrompt/humanize-ppt` (916★), `fromleda/text-humanizer` (734★, created 2026-08-10),
`scanaislop/aislop` (589★), `LifelongLazyLearner/qu-ai-wei` (510★),
`berelevant-ai/slopless` (323★). Among the movers, `epoko77-ai/im-not-ai` went
**4,182 → 5,143** and `speak-human-tw` 752 → 919.

### Four findings that bear on this repo's own claims

1. **`Vladimir-Human/humanizer-ru`** (120★) is the closest thing to untell's thesis found so far:
   58 patterns, 40 regex markers with an evidence registry, a **"detectability delta before/after"
   axis with false-positive control**, C2PA/EXIF/XMP mark removal, a PyPI package, 193 tests. In
   Russian. The "measured, honest, tested" position is less empty than the census implied.
2. **`kinit-sk/mAO`** — "Benchmark of authorship obfuscation methods in multilingual
   machine-generated text detection". This is a published benchmark for exactly what the rewriting
   loop does, from the group behind IMGTB, and the README does not cite it.
3. **`suraj-ranganath/StealthRL`** — the actual repo behind the StealthRL numbers `ROADMAP.md`
   quotes as the thing untell cannot beat. It was cited from the paper, never located. **Now
   located and read**: 138 product files, 38k lines, LoRA/PEFT/TRL training against ten named
   detectors. Two claims in this repository turned on what is inside it, and reading it settled
   both. It ships `rewards/fairness_reward.py`, computing the ESL-versus-native false-positive
   gap as a live reward term — which **falsified** the strategy doc's "zero repos compute this
   statistic" and forced that claim to be narrowed to the one that survives (a reward term is not
   an instrument). And its semantic term is a *soft* one: `_normalize_semantics` clamps the
   similarity bonus to zero below a floor while the evasion term keeps paying, so destroying
   meaning is unrewarded rather than punished — which **confirms** `absolute-ceiling-buildplan.md`,
   whose hard `−1.0` return is a different mechanism and is now verified against source rather
   than inferred from the paper.
4. **`aloth/provenance-linkage`** and **`wolfvswhale.github.io`** — two 2026-08 projects on how
   AI-text-detection benchmarks get *evaluated* and where the evaluation goes wrong. That is
   untell's own honesty thesis, being worked on elsewhere.

### Confident rows, verified against source

The accuracy claim above used to be a two-row spot check, because reading the other rows looked
like it needed the budget the whole exercise exists to avoid. It does not — see the git-proxy note
in §0. **All sixteen confident rows of the 131-repo harvest were shallow-cloned and read on
2026-09-01.** Fifteen were right.

| row | category | verdict |
|---|---|---|
| `bushrabeg/turkce-humanizer` | prompt-guide | ✅ markdown only, `SKILL.md` + docs + examples |
| `asavvin-pixel/unslop` | prompt-guide | ✅ markdown only |
| `gabelul/slopbuster` | prompt-guide | ✅ 26 `.md`, no source |
| `profdorly/humanizador` | prompt-guide | ✅ four files, all prose |
| `Hakku/finnish-humanizer` | prompt-guide | ✅ the 748 lines of Python are `build.py` and its test; the product is the generated instruction files in `dist/` |
| `LifelongLazyLearner/qu-ai-wei` | prompt-guide | ✅ all four code files are under `tests/` |
| `AndreAlmeidaDC/humanizador` | prompt-guide | ✅ the one Python file is `scripts/validate_skill.py` |
| `DaleSeo/korean-skills` | prompt-guide | ✅ on category; it is a *collection* of three Korean agent skills, so whether it belongs in a humanizer census is a harvest question, not a classifier one |
| `Xircth/thesis-workflow-skill` | prompt-guide | ✅ boundary case — 1,150 lines of C#, but it is a DOCX sub-skill; the AIGC-lowering is `skills/thesis-optimizer`, which is prose |
| `msannikov03/undetectable-mcp` | api-wrapper | ✅ an MCP server over the Undetectable.ai API |
| `lorossi/zero-width-steganography` | unicode-trickery | ✅ |
| `darkshadow2bd/Project-Invisible` | unicode-trickery | ✅ |
| `chinmay29hub/stegmoji` | unicode-trickery | ✅ |
| `v1sc0/zwcs` | unicode-trickery | ✅ |
| `dapperfu/whitespace-stego` | unicode-trickery | ✅ |
| `xuange520/unmark` | unicode-trickery | ❌ **wrong** |

**The one miss is the informative one.** `unmark` describes itself as "Dual-Layer LLM text
watermark removal and AI generation verifier"; `zero-width` appears nowhere in that prose and
reached the classifier as one self-assigned topic in eight. The source is `core/sanitizer.py`
(strip invisible characters — the facet the topic named), `core/scrubber.py` (an open-weights LLM
resampling text to break SynthID's n-gram hash chains — the actual product), and
`audit/verifier.py`, a detector running SynthID z-scores, **perplexity and burstiness**, TTR and
entropy. So the classifier confidently filed a model-based scrubber-with-a-detector-in-the-loop —
precisely the class §1 says is worth paying to read — as character trickery, and a confident
verdict is what drops a row out of the read queue.

Two things follow. First, `unmark` *removes* hidden characters; the rule fired on a sanitiser
using the word its carriers use. A carrier puts characters in and a sanitiser takes them out, they
share the whole vocabulary, and only the verb separates them. The rule now requires the mechanism
in the repo's own prose rather than in a topic label — the same narrowing the vendor rule already
needed — and requires a carrier verb with no removal verb. Detection alone does not disqualify: a
stego toolkit ships a detector for its own format.

The measured trade: **coverage 12.2% → 10.7%, confident-row accuracy 15/16 → 14/14.** It costs one
true positive, `dapperfu/whitespace-stego`, whose description says "invisible Unicode whitespace
characters" and so names no phrase the rule matches. Adding that phrase would recover it and would
be fitting the rule to the sixteen rows used to measure it, so the cost is pinned by a test
instead.

Second, and worth more than the fix: **five of the six `unicode-trickery` rows are not humanizers
at all.** `stegmoji`, `whitespace-stego`, `zwcs`, `zero-width-steganography` and
`Project-Invisible` are general covert-communication tools that predate the AI-detector question
and have nothing to do with it. The classifier is most confident exactly where the harvest was
least precise — an off-topic repo is easy to categorise because its purpose is unambiguous. Of the
sixteen rows the classifier was surest about, ten are on-topic. That is a search-query problem,
not a triage one, and it means the confident bucket's *value* is lower than its accuracy.

### Reading the source, and what it cost to find out that mostly does not work

§1 argues the census overspent by paying an agent to read 435 READMEs, and that a script could
triage most of them. The metadata classifier gets a tenth. The git-proxy finding in §0 says the
rest of the gap is not a reading problem either — the file tree is free — so `census.py inspect`
shallow-clones each repo, reads its tree, and re-decides:

```bash
python .claude/census.py inspect harvest.json --only-unsure
```

**Scored against ground truth nobody fitted it to** — the 34 rows where this harvest overlaps
repos the census hand-read from source, years before this tool existed:

| | rows decided | confident rows right |
|---|---|---|
| `classify` (metadata) | 2 / 34 — **6%** | 2 / 2 |
| `inspect` (file tree) | 11 / 34 — **32%** | 10 / 11 — **91%** |

(`classify` decides 10.7% of the *full* 131-repo sweep and only 6% here, because the overlap is
the harder half by construction: these are the repos the census thought worth reading.)

Five times the reach at comparable precision, and the read queue it hands over is briefed rather
than blind: each unsure row now carries its product file count, its own line count net of bundled
sub-skills, and which detector and meaning-check names appear in its source.

**The first version scored 13/25.** It is worth saying what that means: it was confidently wrong
about *twelve* repos, which is worse than the metadata rule it was built to replace, because a
confident row is one that leaves the read queue. Nine of the twelve came from one branch, and the
branch looked like the best idea in the file — grep the source for `gptzero`, `binoculars`,
`fast-detectgpt`, and you have found the `detector_in_loop` class §1 says is worth paying to read.

It has not. **A humanizer prompt guide lists the detectors it aims to beat.** `gptzero` and
`binoculars` appear in the source of guides and of pipelines alike; `lakshitha-dev/ai-humanizer-skill`
names five and is a prompt guide. Narrowing the word list does not help, because the failure is
the evidence class and not its membership: a mention is not a call, and no list of names
separates the two. The branch is gone. Detector names now reach the reader as a briefing note,
which is what they were always worth.

Two smaller versions of the same error went with it. `trainer(` fired on a benchmark repository
that trains detectors in order to compare them — research, benchmark and product repositories all
contain training code — so `fine-tuned-model` is now confident only on weights, which are a file
rather than a word. And `trl`, a token from that same list, matched inside `strlen` and
confidently called a C and Rust steganography toolkit a fine-tuned model; signal words are
matched at word boundaries now.

What survives is an asymmetry worth stating on its own, because it is the rule the whole step
turns on: **a mention cannot make a verdict, but it can unmake one.** The unicode branch claims
exclusivity — that hiding characters is the entire product — so any other mechanism named in the
source contradicts it whatever that mention turns out to mean. That separates the six unicode
rows by presence rather than by any threshold: all five verified carriers name no detector and no
trainer anywhere in their source, and `xuange520/unmark`, whose sanitiser enumerates eight code
points beside a scrubber and a detector, names five.

**The remaining confident miss is a real limit, not a defect.** `diaiq/claude-skill-humanizer` is
two Markdown files and no code; the census calls it an api-wrapper because its README says
"Powered by DiaIQ". A vendor relationship stated in prose is invisible to a file tree, exactly as
it is invisible to search metadata — §1 already named this repo as the case neither can check.

Three honesty notes on the numbers above. The tree reader also scores 14/14 confident at 88%
coverage on the sixteen repos of the *previous* section — ignore that number. Those sixteen are
what the bugs were found on, and it was 15/15 at 94% before the census overlap showed the
detector branch was wrong about nine repos it had no opinion on. It is what fitting to a
measurement set looks like from the inside, which is why the table above uses the other set.
Second, the 34-row score is itself no longer strictly held out: the diagnosis came from it. The
corrections were deletions of whole evidence classes rather than tuned thresholds — the one fitted
constant that crept in, a Markdown-file count sitting between the two repos it was measured on,
was removed in favour of the packaging fact it was standing in for — but the number should be read
as an upper bound, and re-scored against a fresh overlap when one exists. Third, `inspect` is
*not* cheaper than `classify`: it is a clone and a full-tree read per repo, roughly 1 MB and a
second each. It is cheaper than a reader, which is the comparison that matters.

### The full sweep, and the claim it falsified

All 131 harvested repos were cloned and read on 2026-09-01
(`.claude/probes/census-2026-09-01-multiangle.inspected.json`, ~11 minutes, none unreachable).
The tree decided **38 of 131 — 29%**, against the metadata classifier's 14, and revised 55
categories.

The sweep also carries a `subgroup_fairness` probe. It decides nothing — a test fails if any
branch starts ruling on it — and it exists to check the claim `ROADMAP.md` and
`strategy-the-audit-position.md` both rest on: that no repo in the census or the re-run measures
a detector's false-positive rate by writer subgroup. That claim had only ever been checked
against READMEs, which is the weakest possible evidence for a negative.

**It is false, and it is false about repos inside this very sweep.**

- **`satyamshivam13/AI_Text_Detector`** ships `scripts/fpr_by_population.py`, dated **July
  2026**. Human-only corpus so every flag is a false positive by construction; per-population
  rates with **Wilson 95% intervals**; the corpus built from **Liang et al. (2023)** directly —
  the same TOEFL non-native, US 8th-grade, college-admission and CS224N essays this field's
  bias literature is founded on, plus five HC3 domains; GPT-4-polished TOEFL essays held out as
  machine-edited rather than counted as plain false positives; an **n ≥ 30 floor**; worst-served
  and best-served population and a disparity ratio. It is this repository's instrument, designed
  independently and first, and in one respect better — it uses Liang's canonical corpus, which
  untell does not.
- **`suraj-ranganath/StealthRL`** computes the ESL-versus-native false-positive gap as a live
  training reward (`−w₄·F′`, `fairness_weight: 0.2`, "Minimize ESL bias"). Not an instrument, but
  it computes the number.

Both corrections are written into `ROADMAP.md` and the strategy doc, along with the part that
does survive and the part that turned out not to differentiate anything at all.

**Why a 435-repo census and a 131-repo re-run both missed it, twice over.** Neither repo says any
of this in its README, so a survey that reads READMEs cannot see it. But the sharper reason is
visible in the probe's own results: of 131 repos read at source, the number using *any*
algorithmic-fairness vocabulary is **zero**.

| term | repos |
|---|---|
| `subgroup`, `demographic parity`, `equalised/equalized odds` | 0 |
| `disparate impact`, `protected attribute`, `bias audit` | 0 |
| Aequitas, AIF360, Fairlearn | 0 |
| `fpr` / `false positive rate` / `wilson` | 20 |

The two repositories doing subgroup fairness work call their groups **populations** and **ESL
versus native**. They are not in conversation with the fairness literature and do not use its
words, which is why a vocabulary probe built from that literature nearly missed them too — what
actually found them was `wilson` and `fpr`. The field and the fairness field share no vocabulary,
and a survey searching either one's terms will keep concluding the other does not exist.

The other 18 hits are ordinary ROC bookkeeping — `fpr`/`tpr` in a benchmark loop, aggregate and
ungrouped. This paragraph first said `stef41/lmscan` and `Jroo1053/MGTMark` were "worth a
reader"; both were then read, and neither is. `lmscan` computes `fp / total_neg` in its
evaluation module, `MGTMark` the same per run-config. No subgroups in either.

### A third defect, found by walking into it

With 131 repos read at source, the obvious next question is what the sweep says the field is made
of — `ROADMAP.md` opens on exactly that table, and its headline is that **60% of the field either
instructs a humanizer or resells one**. Tallying the sweep's categories gives **32%**, a 27-point
gap that would be a significant finding about where the field is moving.

It is not a finding. It is an artifact of how the tally was printed. Of the sweep's 131 rows, 66
are `rule-based-rewriter` and **every one of them is `unsure`** — that category is the classifier's
fallback, the bucket for "has source; detector-in-loop and meaning verification need reading". An
unsure row keeps a category on purpose, as a prior for whoever reads it: dropping the category was
measured to take unsure-row agreement from 11/24 down to 4/24, because a reader starting from a
wrong prior still starts from a prior. But that means half the sweep sat in a bucket wearing a
category name, and a merged tally counted it as though it were a verdict.

`classify` and `inspect` now print two lists that cannot be added together — DECIDED, and a READ
QUEUE labelled as priors rather than findings. The defect is the same one this repository already
fixed twice in the audit: an empty axis heading that reads as "no disparity here", and a report
with no pooled error rates that let a 100% false-negative rate pass unremarked. **A placeholder
that reads as a finding is the recurring bug in this codebase**, and the only reliable guard is
never to render the two side by side.

Worth stating plainly: nothing above tells you the field's composition has or has not changed. The
census ran 624 queries and read source by hand; this sweep ran 11 angles and reads file trees.
They are not comparable samples measured the same way, and the honest answer to "what is the field
made of in September" is that this sweep does not establish it.

### Two defects the run exposed in the tooling

Both are fixed and pinned by tests, and both were only visible because the run was big enough.

- **Confident rows broke at scale.** 3/3 on 23 repos became 6/9 on 111. `Undetectable-AI` matched
  the vendor rule on *its own name*; two agent-skill repos were confidently called prompt guides.
  The vendor rule now reads the description only, and skills that advertise machinery or claim to
  beat named detectors go to a reader. Coverage fell to the honest tenth, and the accuracy claim
  went from a two-row spot check to the sixteen-row source audit below.
- **The delta was inflating itself.** 73 of the census's 435 names are not a bare `owner/repo` —
  annotations, missing owners, owner/repo inside parentheses. Exact matching reported
  `epoko77-ai/im-not-ai` as a *new* 5,143-star repo while the census's own star table lists it at
  4,182. The headline was 85 new; corrected, it is 78.

**Left, in order:**

1. **Read the 83-row queue** and fold the result into `docs/humanizer-census.json`. The harvest is
   done; reading is the only part that needs an LLM, and it is now a bounded list rather than 435.
2. **`raid-bench` as an external check** (§6) — MIT, pip-installable, aimed at a benchmark this repo
   already streams data from, and it attacks the weakest published claim (sample size) with somebody
   else's leaderboard rather than our own harness.
3. **Decide the egress question** (§0). Everything in §2–§5 is blocked from a remote session. Until
   the allowlist widens, they are local-checkout tools and the census refresh is a two-step
   (MCP capture → `ingest`) rather than one command.
