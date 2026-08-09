# What would make this the top repo

Written 2026-08-09, from the 435-repo census in [`humanizer-census.json`](humanizer-census.json).
Every number here is re-derived from that file; the derivations are in
[Result 47](free-ceiling-measured.md).

The short version: **"top" by stars and "top" by quality are different games, and more engineering
only wins the second one.** That is not a reason to stop engineering — it is a reason to stop
expecting stars to follow from it, and to be deliberate about which prize is being chased.

## Stars do not measure what this repo is good at

Counted from the census JSON (Result 47):

| category | repos | median ★ | share of all stars | best |
|---|---|---|---|---|
| `prompt-guide` | 184 | 1 | **92%** | 298,793 |
| `adversarial-perturbation` | 39 | 13 | 2% | 8,720 |
| `api-wrapper` | 75 | 1 | <1% | 2,029 |
| `rule-based-rewriter` — *our category* | 38 | 2 | **0.3%** | **413** |
| `research-code` | 19 | 13 | 0.3% | 1,018 |

584,528 stars across 435 repos, and **the top 20 hold 98% of them**. Six of the eight largest
contain **no executable code at all** — two of them are a single `SKILL.md`.

Sorted by what a repo contains rather than what it is called:

| group | repos | median ★ | mean ★ | best |
|---|---|---|---|---|
| detector in the loop | 49 | 10 | 320 | 8,720 |
| automated meaning verification | 85 | 3 | 3,697 | 298,793 |
| **no mechanical verification of any kind** | 275 | 1 | 581 | 68,545 |

Engineering raises the **floor** — a detector loop is worth 10× the median of a repo with nothing
mechanical in it. It does nothing to the **ceiling**. The largest engineered project in the census
is `leondz/garak` at 8,720★, and garak is an LLM red-teaming scanner, not a humanizer. The largest
thing that is actually a rule-based rewriter, the category this repo sits in, has **413 stars**.

So the honest statement of position: we are near the top of a category worth 0.3% of the field's
attention, and the top of the field is held by two markdown files.

## Two prizes, two different levers

**If "top" means stars,** more gates will not do it. The measured levers, in the order the data
supports them:

1. **Language.** Roughly a third of the field targets a language other than English, and three of
   the eight largest repos are Chinese. Our catalogue, the voice matcher's constants and every
   measurement here are English-only. `untell/languages.py` already exists as the registry a second
   catalogue would plug into — the blocker is not architecture, it is that a tell catalogue must be
   written by someone who reads the language. **Not autonomous. Needs a native speaker.**
2. **Skill-first framing.** 154 census repos (35%) ship as a Claude Code skill and hold 73% of all
   stars — though their median is 1★, so this is a lottery with a very long tail, not a reliable
   return. We already ship a skill; what we do not do is lead with it. Low effort, unknown payoff,
   no correctness risk.
3. **Nothing else in the data moves stars.** Tests, gates, CI, negative results: no correlation
   worth acting on. 275 repos have no mechanical verification and one of them has 68,545 stars.

**If "top" means the repo a careful person should actually use,** the census already says we hold
that, and Result 46 re-verified it: of 435 repos, **zero** combine a mechanical meaning gate with
citation locking. The work that defends this position is the work already underway — every claim
machine-checked, every defect re-derived, every negative result published.

## The one technique nobody in 435 repos uses

Mining the 49 detector-in-loop repos for search strategy:

| technique | repos using it | best |
|---|---|---|
| iterate until it passes | 12 | 4,254★ |
| RL (GRPO/DPO/PPO) | 5 | 18★ |
| ensemble of detectors | 4 | 71★ |
| per-token coupling | 3 | 85★ |
| gradient / white-box | 3 | 85★ |
| **beam or tree search over candidates** | **0** | — |

Nobody searches. Every detector-coupled repo in the census, including this one, does greedy
iteration: generate candidates, keep the single best, iterate from it. `best_of=3` is three
independent draws collapsed to one survivor each round, which throws away every runner-up before it
has been extended.

A beam of width *k* keeps *k* partial rewrites across iterations instead of one. It needs no GPU
and no new dependency — it is more scoring calls against the same lite-tier scorer, and the cost is
linear in beam width. It is the only strategy on this list with a zero next to it, and it is
squarely autonomous.

Worth being clear about the risk before anyone builds it: scoring is already the bottleneck, a
prior measurement found ~46% of scoring is recomputation, and both attempted caches were measured
and reverted. A beam of width 4 is roughly 4× the scoring cost for an unknown gain. **The next step
is a measurement, not an implementation** — beam vs `best_of` at matched scoring budget, on both
corpora, at `--repeats 3` because the neural path is 4× as variable as the composite one.

## What not to do

- **Chase the star count with features.** The data says it does not work in this category.
- **Add a seventh meaning gate.** Result 46 says zero competitors have two. The marginal gate
  defends nothing.
- **Re-tune the lite threshold on pooled corpora.** Result 43: 30% on HC3, 10% on RAID. A pooled
  number describes neither.
- **Trust any of this without re-deriving it.** These numbers describe the census as it stood on
  2026-08-09, and a census is a snapshot of a field that moves.
