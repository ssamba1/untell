# Research tooling survey — what would make untell's research faster and wider

**Surveyed 2026-09-01.** A survey of repos and services that could improve *how this project does
research*, not what it ships. Every candidate below is matched to a limit this repository has
already written down about itself — mostly in
[`humanizer-census.md` § Coverage limits](humanizer-census.md#coverage-limits--what-this-census-still-cannot-claim)
and [`ROADMAP.md`](../ROADMAP.md).

Star counts are from the GitHub API on the survey date and drift daily. Nothing here was
benchmarked; this is a survey of *options*, and it says so.

---

## 0. The measured constraint nobody wrote down

Before recommending anything, this is what a Claude Code **web/remote** session can actually reach.
Probed 2026-09-01 with `curl` through the session's egress proxy:

| endpoint | result |
|---|---|
| `api.github.com` | **200** — core 15,000/hr, GraphQL 10,000/hr, search 30/min, code search 10/min |
| `export.arxiv.org` | 403 at CONNECT |
| `api.openalex.org` | 403 |
| `api.semanticscholar.org` | 403 |
| `api.crossref.org` | 403 |
| `huggingface.co` | 403 |
| `repos.ecosyste.ms` | 403 |
| `grep.app` | 403 |
| `api.tavily.com`, `api.exa.ai` | 403 |

**Everything below except GitHub is blocked by the environment's network policy in a remote
session.** The built-in `WebSearch`/`WebFetch` tools still work — they do not go through that
proxy — so *reading* the web is available; *scripted* access to any of these APIs is not. Any
harvester built on the non-GitHub services in this document must run on a local checkout, or the
environment's allowlist must be widened. That is a real constraint on the "run the census on a
schedule" idea and it is the first thing to settle.

---

## 1. The census is already stale, and re-running it the old way is the wrong fix

The 2026-08-05 census read 435 of 1287 repos. Two things about it:

**It has decayed.** A single GitHub repo-search filtered to `pushed:>2026-06-01` surfaced
[`fromleda/text-humanizer`](https://github.com/fromleda/text-humanizer) — **733 stars, created
2026-08-10**, five days *after* the sweep. A repo that size in this field is not a rounding error;
it would place in the census's own star table. There will be others.

**Its stated failure mode was LLM spend, not GitHub.** The census records that the completeness
critics and 49 non-English reads "died on an API spend limit". The GitHub side was never the
bottleneck — the numbers above show 15,000 REST and 10,000 GraphQL calls per hour available with no
key of ours and no spend at all. The 624 queries that produced 1287 candidates cost roughly 21
minutes of the 30/min search budget.

So the fix is not a bigger sweep budget. It is to **stop paying an LLM to read READMEs that a script
can triage**:

1. **Harvest deterministically.** GraphQL `search(type: REPOSITORY)` returns name, stars, topics,
   pushed date, primary language, license and the README blob in one query per page. 1287 repos is
   a few dozen calls, not 1287 agent turns.
2. **Classify cheaply first.** The census's own categories (`prompt-guide`, `api-wrapper`,
   `rule-based-rewriter`, …) are mostly decidable from file structure: a repo with no `.py`/`.ts`
   source and one Markdown file is a prompt guide; a repo whose only network call is to a vendor
   endpoint is an API wrapper. That is 60% of the field — 259 of 435 — resolved without a token.
3. **Spend the LLM on the tail.** The interesting classes (`detector_in_loop`,
   `meaning_verification`) are the ones that need reading. That is where the budget should have gone
   the first time.
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

## 7. If only two things get done

1. **A deterministic census refresher** (§1). GraphQL harvest → structural classification →
   LLM on the ambiguous tail → diff against `humanizer-census.json`. It costs no API spend against
   the limit that actually killed the last sweep, and it retires the "as of 2026-08-05" caveat that
   currently sits on the field's headline numbers. `text-humanizer` at 733 stars is the evidence
   that it is already needed.
2. **`raid-bench` as an external check** (§6). It is MIT, pip-installable, aimed at a benchmark this
   repo already streams data from, and it attacks the weakest published claim — sample size — with
   somebody else's leaderboard rather than our own harness.

Both are local-checkout work. Neither needs a key. Everything else in this document is blocked from
a remote session until the environment's egress allowlist is widened (§0), and that decision comes
first.
