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
| `api.github.com` **repo-scoped** | **200** — `repos/{owner}/{repo}/...` only |
| `api.github.com/search/*`, `/graphql` | **403** — "sessions are bound to their configured repositories" |
| `export.arxiv.org` | 403 at CONNECT |
| `api.openalex.org` | 403 |
| `api.semanticscholar.org` | 403 |
| `api.crossref.org` | 403 |
| `huggingface.co` | 403 |
| `repos.ecosyste.ms` | 403 |
| `grep.app` | 403 |
| `api.tavily.com`, `api.exa.ai` | 403 |

**Almost nothing here is scriptable from a remote session.** Two separate limits stack. The
egress proxy 403s every non-GitHub host above. And GitHub itself is *repo-scoped*: `curl` to
`api.github.com` serves `repos/ssamba1/untell/...` and refuses `/search/*` and `/graphql`
outright, so a script cannot run a global repo search from here at all. `/rate_limit` still
reports a healthy 15,000/hr core and 10,000/hr GraphQL budget — those numbers are real and they
describe a scope that cannot answer a census query, which is exactly the trap.

What *does* work in a remote session: the **MCP GitHub tools** (`search_repositories`,
`search_code`) reach all of GitHub, and `WebSearch`/`WebFetch` do not go through the egress proxy.
So discovery is available interactively; automation is not. `.claude/census.py` is built around
that split — it `harvest`s on a local checkout with a PAT, and `ingest`s MCP-captured results
everywhere else. Widening the environment's allowlist is what would collapse the two paths into
one, and that decision comes before any scheduled refresh.

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
   categories are 60% of the census (259 of 435), which is the *ceiling* on this idea, not the
   yield. **Measured**, on a 23-repo `topic:ai-humanizer` harvest: `.claude/census.py classify`
   decides **35%** without a reader, and on the 11 of those the census had already read by hand
   its confident rows agree **3 of 3**. A third of the budget, not two thirds — and the honest
   number is the one worth planning against.
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

## 7. What shipped, and what is left

**Shipped: `.claude/census.py`** — the refresher from §1, built and measured rather than proposed.

```bash
python .claude/census.py plan                      # 12 angles, 43 queries, ~2 min of search budget
python .claude/census.py harvest --out out/x.json  # local checkout + PAT; refuses cleanly elsewhere
python .claude/census.py ingest a.json --out x.json  # remote session: fold in MCP-captured results
python .claude/census.py classify x.json           # structural triage, no LLM, no network
python .claude/census.py verify x.json             # score the classifier against the census
python .claude/census.py delta x.json              # what the census would say differently today
```

`verify` is the part that matters: the census hand-read 435 repos, so any overlap is free ground
truth, and the classifier is scored against it rather than trusted. It reports the two buckets
separately because they promise different things — a wrong *confident* row is a defect (it dropped
a repo from the read queue on a bad rule), a wrong *unsure* row is the system working.

Its first real run says the census has decayed further than §1 showed. One angle
(`topic:ai-humanizer`, 23 repos) turns up **12 not in the census, 5 of them at ≥100 stars** —
including `seyedehsanhadi/sloptrim` (205★, created 2026-08-13), a zero-dependency stdlib-only prose
detector that is unusually close to this repo's own lite tier. Two known repos also moved by more
than 50 stars. That is one angle of twelve.

**Left, in order:**

1. **Run the other eleven angles** and fold the result into `docs/humanizer-census.json`. The tool
   is built; the read queue it produces is the only part that needs an LLM.
2. **`raid-bench` as an external check** (§6) — MIT, pip-installable, aimed at a benchmark this repo
   already streams data from, and it attacks the weakest published claim (sample size) with somebody
   else's leaderboard rather than our own harness.
3. **Decide the egress question** (§0). Everything in §2–§5 is blocked from a remote session. Until
   the allowlist widens, they are local-checkout tools and the census refresh is a two-step
   (MCP capture → `ingest`) rather than one command.
