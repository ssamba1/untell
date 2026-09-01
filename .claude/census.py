"""Keep the census alive, without paying an agent to read 435 READMEs.

The 2026-08-05 sweep read 435 of 1287 repos and recorded its own cause of death: the
completeness critics and 49 non-English reads "died on an API spend limit". That was LLM
spend. GitHub was never the bottleneck -- the search API serves 30 queries a minute, and the
624 queries that produced 1287 candidates fit inside half an hour of it.

So the fix is not a bigger budget. It is to stop spending tokens on the part of the field that
is decidable from metadata -- and to be honest about how small that part is.

MEASURED 2026-09-01, on a real eleven-angle harvest of 111 repos, 26 of which the census had
already read by hand:

    decided without a reader   9%   (35% on a single topic-filtered slice)
    confident rows correct     2/2
    unsure rows correct       11/24

The 60% the census's own category counts suggest -- 259 of 435 being prompt-guide or
api-wrapper -- is NOT reachable from metadata, and the gap is not a tuning problem. Those
categories were assigned by reading source. Metadata can see that a repo is packaged as an agent
skill or that its description names a vendor; it cannot see whether the Python file beside the
Markdown is the product. Nine percent of a sweep is what this saves. That is worth having and it
is not a revolution, and a version of this file that claimed otherwise would be the exact
failure the repo it lives in exists to measure.

What is left over -- detector_in_loop, meaning_verification -- is what actually needed reading,
and handing you exactly that list is this script's job.

    python .claude/census.py plan                     # the query plan, one line per angle
    python .claude/census.py harvest --out out/x.json # run the plan (needs a token; see below)
    python .claude/census.py ingest a.json b.json     # fold in results captured some other way
    python .claude/census.py classify out/x.json      # structural triage, no LLM, no network
    python .claude/census.py verify out/x.json        # score the classifier against the census
    python .claude/census.py delta out/x.json         # what changed vs docs/humanizer-census.json

**Read this before trusting `harvest`.** Global GitHub search needs a token with normal API
scope. A Claude Code *remote* session does not have one: its api.github.com is bound to the
session's own repositories, and `/search/*` and `/graphql` answer 403 with "sessions are bound
to their configured repositories". Measured 2026-09-01. In that environment `harvest` cannot
run at all and says so; use the MCP GitHub tools, write their JSON to a file, and `ingest` it.
On a local checkout with a PAT in GITHUB_TOKEN, `harvest` runs the whole plan unaided.

The classifier never invents a reading. Every row it is not sure about is marked `needs_read`,
and a row it IS sure about carries the rule that decided it, so a wrong call is traceable to a
rule rather than to a vibe. `category` here is deliberately the same vocabulary as
docs/humanizer-census.json, so a refresh diffs against the census instead of replacing it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENSUS = ROOT / "docs" / "humanizer-census.json"
API = "https://api.github.com"

# The 12 discovery angles the 2026-08-05 sweep used, written down as queries this time. The
# sweep's angles lived in a prompt and died with it, which is why "624 distinct queries" is a
# number nobody can reproduce. These are reproducible; that is the entire point of the file.
#
# `stars:>=0` is not redundant -- it forces the search index to rank by the sort argument
# rather than by relevance, which is what makes paging deterministic.
QUERY_PLAN: dict[str, tuple[str, ...]] = {
    "topics": (
        "topic:ai-humanizer", "topic:humanizer", "topic:bypass-ai-detection",
        "topic:ai-detection", "topic:ai-text-detection", "topic:anti-ai-detection",
    ),
    "keywords": (
        "humanize ai text", "humanizer ai detector", "bypass ai detector",
        "undetectable ai text", "ai text rewriter detector",
    ),
    "techniques": (
        "adversarial paraphrasing detector", "detector guided decoding",
        "paraphrase attack ai detection", "token substitution detector evasion",
    ),
    "research": (
        "machine generated text detection benchmark", "AI generated text detector evaluation",
        "watermark removal text llm",
    ),
    "detectors": (
        "gptzero detector", "ai content detector open source", "zerogpt", "originality ai detector",
    ),
    "unicode": (
        "zero width character text", "homoglyph text attack", "trojan source unicode",
    ),
    "prompts": (
        "humanize prompt chatgpt", "anti ai writing patterns prompt", "ai slop prompt guide",
    ),
    "awesome": (
        "awesome ai detection", "awesome humanizer",
    ),
    "wrappers": (
        "undetectable.ai api client", "stealthgpt api", "humanizer api wrapper",
    ),
    # 32% of the field is non-English and the census under-counted it, because 49 of those
    # reads are the ones that hit the spend limit. Metadata search does not care about that.
    "non_english": (
        "humanizador ia texto", "AI 检测 降重", "AI 문체 탐지", "гуманизатор текста нейросети",
        "humanizador de texto ia", "humaniseur de texte ia",
    ),
    "registries": (
        "humanizer pypi package", "ai detector npm package",
    ),
    "integrity": (
        "turnitin ai detection", "academic integrity ai writing detection",
    ),
}

# ---------------------------------------------------------------------------------------------
# Structural classification.
#
# Each rule is (category, confidence, why, predicate). First match wins, so order is meaning.
# "confident" rows are counted; "unsure" rows are handed to a reader. A rule that fires on
# everything would silently empty the read queue, so `classify` reports the split and
# `test_census_triage.py` pins that a real corpus lands in both buckets.
# ---------------------------------------------------------------------------------------------

# Vendors whose name in a description means the repo bills for, or wraps, somebody else's
# humanizer. Taken from the census's own api-wrapper segment.
_VENDORS = (
    "undetectable.ai", "stealthgpt", "humbot", "hix", "writehuman", "phrasly", "walterwrites",
    "quillbot", "bypassgpt", "smodin", "netus", "twixify", "surfer", "rephrasy", "aihumanize",
)
_PROMPT_WORDS = ("prompt", "guide", "rules", "instructions", "cheatsheet", "patterns", "skill")
# The field's shape changed after the census: the prompt guide grew a packaging format. An
# "agent skill" is usually a Markdown instruction file with a manifest, which is a prompt guide
# however many .py helpers sit beside it -- and those helpers are what made the language
# heuristic below call four of them rewriters.
#
# MEASURED on the 2026-09-01 topic:ai-humanizer sweep (23 repos, 11 of them already read by the
# census). Before this rule: 4/11 agreement, 22% decided without a reader, and the one confident
# row was right. After it and the machinery guard below: 6/11 agreement, 35% decided, and
# **3 of 3 confident rows right**. The middle number went 43% -> 35% when the guard landed, and
# that was the trade worth making -- see the guard's own note.
_SKILL_TOPICS = (
    "claude-skill", "claude-skills", "claude-code-skill", "claude-code-skills", "agent-skills",
    "codex-skill", "openclaw-skill", "claude-code-plugin", "agent-skill",
)
# ...but "packaged as a skill" is not "is only prose". marmbiz/humanizer-de ships 72 patterns
# behind deterministic linters and the census calls it a rule-based-rewriter; the skill rule
# called it a prompt-guide CONFIDENTLY, which is the one kind of miss that costs something -- it
# drops a repo from the read queue on a bad rule. A skill that advertises machinery goes to a
# reader instead of to a verdict.
_MACHINERY_WORDS = (
    "linter", "deterministic", "regex", "parser", "script", "algorithm", "pipeline",
    "classifier", "scorer", "engine",
    # Added after the 111-repo harvest: stephenlzc/humanize-mba-text-skill calls itself a
    # "detection and removal tool" and the census made it a rule-based-rewriter, but none of the
    # words above fired. Something that DETECTS is running machinery, whatever it is packaged as.
    "detection", "detector", "detects", "removal", "analyzer", "analyser",
)
# A skill that promises to beat NAMED detectors is making a product claim, and metadata cannot
# tell a prompt that claims it from a pipeline that does it. diaiq/claude-skill-humanizer reads
# exactly like a prompt guide and the census read it as an api-wrapper ("Powered by DiaIQ").
# Claims like this go to a reader rather than to a confident verdict.
_BYPASS_CLAIM = ("bypass", "undetectable", "pass ai detect", "beat ai detect", "100% human")
_WRAPPER_WORDS = ("api client", "api wrapper", "sdk for", "unofficial api", "reverse engineered")
_DETECTOR_WORDS = ("detector", "detection", "classifier", "identify ai", "ai checker")
_TRAIN_WORDS = ("fine-tune", "finetune", "lora", "dpo", "grpo", "sft", "rlhf", "trained on")
_UNICODE_WORDS = ("zero-width", "zero width", "homoglyph", "invisible character", "trojan source")
_DATASET_WORDS = ("dataset", "corpus", "benchmark")

# Markdown-only repos are the field's largest segment and the cheapest to identify: GitHub
# reports no primary language for a repo that contains no code it recognises.
_MARKDOWNISH = (None, "", "Markdown", "HTML", "TeX")


def _text(repo: dict) -> str:
    parts = [repo.get("name") or "", repo.get("full_name") or "", repo.get("description") or ""]
    parts.extend(repo.get("topics") or ())
    return " ".join(parts).lower()


def _described(repo: dict) -> str:
    """Description only.

    MEASURED 2026-09-01: the vendor rule read the repo's own name and topics too, so
    `samrand96/Undetectable-AI` -- topics `undetectable-ai`, `bypassgpt` -- was CONFIDENTLY called
    an api-wrapper. The census read it and called it detector-with-evasion. Naming yourself after
    the thing you replace is not the same as billing for it, and a topic is a self-label rather
    than a dependency. A vendor name only implies wrapping when it appears in the prose.
    """
    return (repo.get("description") or "").lower()


def classify(repo: dict) -> dict:
    """Assign a census category from metadata alone, or admit that it cannot."""
    t = _text(repo)
    lang = repo.get("language")
    has = lambda words: any(w in t for w in words)  # noqa: E731 - a predicate, not a function

    described = _described(repo)
    if any(v in described for v in _VENDORS) or any(w in described for w in _WRAPPER_WORDS):
        return _row(repo, "api-wrapper", "confident",
                    "its description names a commercial humanizer, or says it wraps one")

    topics = {str(t).lower() for t in (repo.get("topics") or ())}
    name = (repo.get("name") or "").lower()
    if topics & set(_SKILL_TOPICS) or name.endswith("-skill"):
        # Both guards below drop CONFIDENCE without abandoning the category. The packaging is
        # still the strongest signal metadata has; what the guard doubts is whether it is the
        # WHOLE story, not whether it is true. Flipping the category as well cost real accuracy:
        # on the 111-repo harvest the census calls ten of these prompt-guide and the guarded rows
        # were answering rule-based-rewriter, so the reader started from a worse prior than the
        # packaging alone would have given them. Unsure-row agreement 4/24 -> 11/24 on that change.
        if has(_MACHINERY_WORDS):
            return _row(repo, "prompt-guide", "unsure",
                        "an agent skill that also advertises machinery; whether the machinery or "
                        "the prose is the product needs reading")
        if any(c in described for c in _BYPASS_CLAIM):
            return _row(repo, "prompt-guide", "unsure",
                        "an agent skill claiming it beats named detectors; that is a product "
                        "claim metadata cannot check")
        return _row(repo, "prompt-guide", "confident",
                    "packaged as an agent skill: a Markdown instruction file plus a manifest")

    if lang in _MARKDOWNISH and has(_PROMPT_WORDS):
        return _row(repo, "prompt-guide", "confident",
                    "no source language GitHub recognises, and describes itself as a prompt/guide")

    if has(_UNICODE_WORDS):
        return _row(repo, "unicode-trickery", "confident", "names a hidden-character carrier")

    if has(_TRAIN_WORDS):
        return _row(repo, "fine-tuned-model", "unsure",
                    "names a training method; whether it SHIPS the model needs reading")

    if has(_DATASET_WORDS) and not has(("humanize", "rewrite", "bypass")):
        return _row(repo, "dataset", "unsure", "looks like data rather than a tool; needs reading")

    if has(_DETECTOR_WORDS) and not has(("humanize", "bypass", "evade")):
        return _row(repo, "detector-with-evasion", "unsure",
                    "a detector; whether it ships attack code needs reading")

    # Everything left is a rewriter of some kind, and the interesting question -- is a detector
    # inside the loop -- is exactly the one metadata cannot answer. This is the read queue.
    if lang in _MARKDOWNISH:
        return _row(repo, "prompt-guide", "unsure", "no recognised source language, but not self-described as a guide")
    return _row(repo, "rule-based-rewriter", "unsure",
                "has source; detector-in-loop and meaning verification need reading")


def _row(repo: dict, category: str, confidence: str, why: str) -> dict:
    return {
        "name": repo.get("full_name") or repo.get("name"),
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language"),
        "pushed_at": repo.get("pushed_at") or repo.get("updated_at"),
        "created_at": repo.get("created_at"),
        "category": category,
        "confidence": confidence,
        "rule": why,
        "needs_read": confidence != "confident",
    }


# ---------------------------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------------------------

class HarvestUnavailable(RuntimeError):
    """Global search is not reachable from here. The message says what to do instead."""


def _get(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "untell-census",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.loads(fh.read().decode("utf-8"))


def search(query: str, token: str | None, pages: int = 1, per_page: int = 100) -> list[dict]:
    out: list[dict] = []
    for page in range(1, pages + 1):
        qs = urllib.parse.urlencode({
            "q": query, "sort": "stars", "order": "desc", "per_page": per_page, "page": page,
        })
        try:
            data = _get(f"{API}/search/repositories?{qs}", token)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code == 403 and "bound to their configured repositories" in body:
                raise HarvestUnavailable(
                    "this session's api.github.com is bound to its own repositories, so global "
                    "search answers 403. Run this on a local checkout with a PAT in "
                    "GITHUB_TOKEN, or use the MCP GitHub tools and `ingest` their output."
                ) from exc
            if exc.code in (403, 429):  # secondary rate limit: back off once, then give up
                time.sleep(60)
                data = _get(f"{API}/search/repositories?{qs}", token)
            else:
                raise
        items = data.get("items", [])
        out.extend(items)
        if len(items) < per_page:
            break
        time.sleep(2.1)  # 30 searches/minute, with room for the retry above
    return out


def harvest(pages: int, angles: tuple[str, ...] | None) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    seen: dict[str, dict] = {}
    for angle, queries in QUERY_PLAN.items():
        if angles and angle not in angles:
            continue
        for q in queries:
            found = search(q, token, pages=pages)
            for repo in found:
                seen.setdefault(repo["full_name"], repo)
            print(f"  {angle:12} {q[:44]:44} +{len(found):3}  total {len(seen)}", file=sys.stderr)
    return list(seen.values())


def ingest(paths: list[Path]) -> list[dict]:
    """Fold in search results captured elsewhere -- e.g. by the MCP GitHub tools.

    Accepts either a bare list of repo objects or the `{"items": [...]}` the search API
    returns, so a result can be saved verbatim without reshaping it by hand.
    """
    seen: dict[str, dict] = {}
    for p in paths:
        blob = json.loads(p.read_text(encoding="utf-8"))
        items = blob.get("items", []) if isinstance(blob, dict) else blob
        for repo in items:
            key = repo.get("full_name") or repo.get("name")
            if key:
                seen.setdefault(key, repo)
    return list(seen.values())


# ---------------------------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------------------------

# 73 of the census's 435 `name` values are not a bare owner/repo. They carry annotations
# ("epoko77-ai/im-not-ai (Humanize KR)"), or give the owner/repo inside the parens
# ("BERT-Attack (LinyangLee/BERT-Attack)"), or are a bare repo with no owner at all
# ("speak-human-tw", "GPTZzzs"). Exact-string matching against that field silently reports
# known repos as new: it put epoko77-ai/im-not-ai -- which the census's own star table lists at
# 4,182 stars -- in the "new" column at 5,143. A delta that inflates itself is worse than none,
# so names are matched through these keys instead.
_OWNER_REPO = re.compile(r"[\w.-]+/[\w.-]+")


def _match_keys(name: str) -> tuple[set[str], set[str]]:
    """(owner/repo forms, bare repo names) for one census or harvest name."""
    low = name.strip().lower()
    full = set(_OWNER_REPO.findall(low))
    bare = {f.split("/")[-1] for f in full}
    if not full:  # a bare repo name, possibly with an annotation after it
        bare.add(low.split("(")[0].strip().split()[0] if low.split("(")[0].strip() else low)
    return full, bare


def load_census() -> dict[str, dict]:
    """Index the census by every name form a harvest might legitimately match.

    Bare-repo keys are only registered for census rows that give no owner at all, because two
    different owners really do ship a `humanizer-ru`, and matching those together would hide a
    new repo rather than merely miscount one.
    """
    if not CENSUS.exists():
        return {}
    index: dict[str, dict] = {}
    for row in json.loads(CENSUS.read_text(encoding="utf-8")):
        full, bare = _match_keys(row["name"])
        for key in full:
            index.setdefault(key, row)
        if not full:
            for key in bare:
                index.setdefault(key, row)
    return index


def _known(name: str, known: dict[str, dict]) -> dict | None:
    full, bare = _match_keys(name or "")
    for key in full or bare:
        if key in known:
            return known[key]
    for key in bare:
        if key in known:
            return known[key]
    return None


def delta(fresh: list[dict], known: dict[str, dict], star_floor: int = 50) -> dict:
    """What the census would say differently if it were re-read today."""
    rows = [r if "confidence" in r else classify(r) for r in fresh]
    new = [r for r in rows if _known(r["name"], known) is None]
    new.sort(key=lambda r: -r["stars"])
    moved = []
    for r in rows:
        old = _known(r["name"], known)
        if old and abs(r["stars"] - old.get("stars", 0)) >= star_floor:
            moved.append((r["name"], old.get("stars", 0), r["stars"]))
    moved.sort(key=lambda m: -(m[2] - m[1]))
    return {
        "seen": len(rows),
        "in_census": len(rows) - len(new),
        "new": new,
        "notable_new": [r for r in new if r["stars"] >= 100],
        "moved": moved,
        "needs_read": [r for r in new if r["needs_read"]],
    }


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

def _load(path: Path) -> list[dict]:
    blob = json.loads(path.read_text(encoding="utf-8"))
    return blob.get("items", []) if isinstance(blob, dict) else blob


def cmd_plan() -> int:
    total = sum(len(v) for v in QUERY_PLAN.values())
    print(f"{len(QUERY_PLAN)} angles, {total} queries "
          f"(~{total * 2.1 / 60:.0f} min at the search API's 30/min)\n")
    for angle, queries in QUERY_PLAN.items():
        print(f"{angle:12} {len(queries):2}  " + " | ".join(queries[:3])
              + (" | ..." if len(queries) > 3 else ""))
    return 0


def cmd_classify(path: Path) -> int:
    rows = [classify(r) for r in _load(path)]
    confident = [r for r in rows if not r["needs_read"]]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print(f"{len(rows)} repos: {len(confident)} classified from metadata, "
          f"{len(rows) - len(confident)} need a reader "
          f"({100 * len(confident) / max(len(rows), 1):.0f}% of the budget saved)\n")
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:24} {n:4}")
    out = path.with_suffix(".classified.json")
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


def verify(fresh: list[dict], known: dict[str, dict]) -> dict:
    """Score the classifier against the census's own hand-read verdicts.

    The census read those 435 repos properly, so where a harvest overlaps it we have ground
    truth for free. This is the only thing standing between "structural triage" and "guessing
    quickly": a classifier nobody scores is a classifier nobody should believe.

    Reported split by confidence, because the two buckets make different promises. A wrong
    `confident` row is a defect -- it removed a repo from the read queue on a bad rule. A wrong
    `unsure` row is the system working: it was already routed to a reader.
    """
    rows = [(row, _known(row["name"], known)) for row in (classify(r) for r in fresh)]
    scored = [(row, old) for row, old in rows if old]
    out = {"overlap": len(scored), "confident": [0, 0], "unsure": [0, 0], "wrong": []}
    for row, old in scored:
        bucket = "confident" if row["confidence"] == "confident" else "unsure"
        hit = old["category"] == row["category"]
        out[bucket][0 if hit else 1] += 1
        if not hit:
            out["wrong"].append((row["name"], old["category"], row["category"], row["confidence"]))
    return out


def cmd_verify(path: Path) -> int:
    v = verify(_load(path), load_census())
    if not v["overlap"]:
        print("no overlap with the census: nothing to score against.")
        return 1
    ch, cm = v["confident"]
    uh, um = v["unsure"]
    print(f"{v['overlap']} repos overlap the census's hand-read verdicts\n")
    print(f"  confident rows  {ch}/{ch + cm} agree" + ("  <-- a miss here is a defect" if cm else ""))
    print(f"  unsure rows     {uh}/{uh + um} agree      (these were routed to a reader anyway)")
    if v["wrong"]:
        print("\ndisagreements:")
        for name, was, mine, conf in v["wrong"]:
            print(f"  {name:38} census={was:22} mine={mine:22} ({conf})")
    return 0


def cmd_delta(path: Path, star_floor: int) -> int:
    d = delta(_load(path), load_census(), star_floor)
    print(f"{d['seen']} repos seen, {d['in_census']} already in the census, "
          f"{len(d['new'])} new\n")
    if d["notable_new"]:
        print("new at >=100 stars -- these change the field's shape:")
        for r in d["notable_new"]:
            print(f"  {r['stars']:6}  {r['name']:44} {r['category']:22} created {str(r['created_at'])[:10]}")
    if d["moved"]:
        print(f"\nmoved by >={star_floor} stars since the census:")
        for name, was, now in d["moved"][:20]:
            print(f"  {was:6} -> {now:6}  {name}")
    print(f"\n{len(d['needs_read'])} of the new rows need a reader. That is the LLM budget; "
          f"the rest is already decided.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    # `census.py classify x | head -3` closes stdout early, and the default SIGPIPE handling in
    # Python turns that into a BrokenPipeError traceback on a run that actually SUCCEEDED. A
    # reporting tool people will pipe into head/grep must not do that.
    try:
        from signal import SIG_DFL, SIGPIPE, signal

        signal(SIGPIPE, SIG_DFL)
    except ImportError:  # no SIGPIPE on Windows; nothing to restore
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("plan", help="print the query plan without running it")
    h = sub.add_parser("harvest", help="run the plan against the search API (needs a token)")
    h.add_argument("--out", type=Path, required=True)
    h.add_argument("--pages", type=int, default=1, help="pages of 100 per query")
    h.add_argument("--angles", default="", help="comma-separated subset of the plan")
    i = sub.add_parser("ingest", help="fold in results captured elsewhere (e.g. MCP tools)")
    i.add_argument("paths", type=Path, nargs="+")
    i.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("classify", help="structural triage: no LLM, no network")
    c.add_argument("path", type=Path)
    v = sub.add_parser("verify", help="score the classifier against the census's read verdicts")
    v.add_argument("path", type=Path)
    dd = sub.add_parser("delta", help="diff against docs/humanizer-census.json")
    dd.add_argument("path", type=Path)
    dd.add_argument("--star-floor", type=int, default=50)
    a = ap.parse_args()

    if a.cmd == "harvest":
        angles = tuple(x for x in a.angles.split(",") if x) or None
        try:
            repos = harvest(a.pages, angles)
        except HarvestUnavailable as exc:
            print(f"harvest unavailable: {exc}", file=sys.stderr)
            return 2
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(repos, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{len(repos)} distinct repos -> {a.out}")
        return 0
    if a.cmd == "ingest":
        repos = ingest(a.paths)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(repos, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{len(repos)} distinct repos -> {a.out}")
        return 0
    if a.cmd == "classify":
        return cmd_classify(a.path)
    if a.cmd == "verify":
        return cmd_verify(a.path)
    if a.cmd == "delta":
        return cmd_delta(a.path, a.star_floor)
    return cmd_plan()


if __name__ == "__main__":
    raise SystemExit(main())
