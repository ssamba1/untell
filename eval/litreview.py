"""Reproduce the systematic literature pass this repo's research documents rest on.

`docs/research-verification.md` reports a count over the primary literature: of the
machine-generated-text detection papers published in the ACL Anthology, roughly a third address
robustness and evasion while **under 2% address false positives or fairness**. That number is the
argument for this project's existence, so it must not be something a reader has to take on trust
from a document. This module re-derives it.

It downloads Anthology volume metadata (the Anthology's own XML, published in its GitHub
repository), extracts every abstract, selects the detection-related subset by keyword, and counts
how many address each topic. Run it and you get the table; change ``VOLUMES`` and you extend the
survey.

**Why this exists rather than a saved spreadsheet.** The compiling environment could not reach
arxiv.org, aclanthology.org or most publishers — an organization egress policy — so the published
survey covers the Anthology and PubMed and says so. Shipping the *method* means the next person to
run it, on a machine without those restrictions, extends the coverage instead of repeating the
work. A bounded survey that can be re-run and widened is worth more than an unbounded claim.

    python -m eval.litreview                    # counts, from cached XML if present
    python -m eval.litreview --download         # fetch the volumes first (~67 MB)
    python -m eval.litreview --topic fairness   # list the papers behind one row
    python -m eval.litreview --json             # machine-readable

Counts are reported with the corpus size beside them, because "6 papers" means nothing without
"out of 397 detection papers out of 28,120 abstracts".
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

ANTHOLOGY_XML = "https://raw.githubusercontent.com/acl-org/acl-anthology/master/data/xml"

# The volumes the published survey covers. Extend this list to widen the survey; a volume that does
# not exist yet is skipped with a warning rather than failing the run, because the Anthology
# publishes them as conferences complete.
VOLUMES: tuple[str, ...] = (
    "2023.acl", "2023.emnlp", "2023.findings", "2023.tacl", "2023.ijcnlp",
    "2024.acl", "2024.emnlp", "2024.findings", "2024.naacl", "2024.lrec", "2024.tacl", "2024.inlg",
    "2025.acl", "2025.emnlp", "2025.findings", "2025.naacl", "2025.coling", "2025.tacl", "2025.cl",
    "2025.aacl", "2025.inlg", "2025.wmt", "2025.naacl-srw",
    "2026.acl", "2026.findings", "2026.eacl", "2026.lrec", "2026.tacl", "2026.cl", "2026.aacl",
)

# A paper counts as detection-related if it talks about detecting generated text at all. Kept broad
# on purpose: the point of the exercise is the *ratio between topics inside* this set, and a narrow
# filter would let the selection do the arguing.
DETECTION = re.compile(
    r"machine[- ]generated text|AI-generated text|LLM-generated text|MGT detection"
    r"|AI text detect|detector",
    re.I,
)

TOPICS: dict[str, re.Pattern[str]] = {
    "robustness/paraphrase": re.compile(r"paraphras|adversarial|robustness|evad", re.I),
    "human-AI mixed/edited": re.compile(
        r"co-?written|human-edited|polish|hybrid|boundary|AI-assisted|mixed", re.I),
    "watermark": re.compile(r"watermark", re.I),
    "education/integrity": re.compile(r"academic integrity|student|classroom|education|essay", re.I),
    "calibration/thresholds": re.compile(r"calibrat|conformal|TPR@|operating point", re.I),
    "false positives/accusation": re.compile(
        r"false positive|false accusation|falsely (flag|accus)|FPR", re.I),
    "fairness/non-native bias": re.compile(
        r"non-native|second language|L2 writer|bias(ed)? against|fairness|demographic", re.I),
}


def _flatten(element: ET.Element | None) -> str:
    """All text under an element, whitespace-normalised.

    Anthology titles and abstracts carry inline markup (``<fixed-case>``, ``<i>``, TeX math), so
    ``element.text`` alone silently truncates at the first tag.
    """
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def download(cache: Path, volumes: tuple[str, ...] = VOLUMES) -> int:
    """Fetch volume XML into ``cache``. Returns how many are available locally afterwards."""
    cache.mkdir(parents=True, exist_ok=True)
    for name in volumes:
        target = cache / f"{name}.xml"
        if target.exists() and target.stat().st_size > 200:
            continue
        url = f"{ANTHOLOGY_XML}/{name}.xml"
        try:
            with urllib.request.urlopen(url, timeout=240) as response:  # noqa: S310
                body = response.read()
        except Exception as exc:  # noqa: BLE001 - a missing volume is normal, not an error
            logger.warning("skipping %s: %s: %s", name, type(exc).__name__, exc)
            continue
        if len(body) < 200:
            logger.warning("skipping %s: response too small to be a volume", name)
            continue
        target.write_bytes(body)
    return len(list(cache.glob("*.xml")))


def load_abstracts(cache: Path) -> list[dict[str, str]]:
    """Every paper in the cached volumes that has an abstract."""
    papers: list[dict[str, str]] = []
    for path in sorted(cache.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            logger.warning("could not parse %s: %s", path.name, exc)
            continue
        collection = root.get("id")
        for volume in root.findall("volume"):
            for paper in volume.findall("paper"):
                abstract = _flatten(paper.find("abstract"))
                if not abstract:
                    continue
                papers.append({
                    "id": f"{collection}-{volume.get('id')}.{paper.get('id')}",
                    "title": _flatten(paper.find("title")),
                    "abstract": abstract,
                })
    return papers


def survey(papers: list[dict[str, str]]) -> dict[str, object]:
    """Counts per topic over the detection subset, plus the corpus sizes that give them meaning."""
    detection = [p for p in papers if DETECTION.search(f"{p['title']} {p['abstract']}")]
    counts = {
        topic: sum(1 for p in detection if pattern.search(f"{p['title']} {p['abstract']}"))
        for topic, pattern in TOPICS.items()
    }
    return {"abstracts": len(papers), "detection_papers": len(detection), "topics": counts}


def papers_for_topic(papers: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
    """The detection papers behind one row, so a count can be audited rather than believed."""
    pattern = TOPICS[topic]
    return [
        p for p in papers
        if DETECTION.search(f"{p['title']} {p['abstract']}")
        and pattern.search(f"{p['title']} {p['abstract']}")
    ]


def _render(result: dict[str, object]) -> str:
    topics: dict[str, int] = result["topics"]  # type: ignore[assignment]
    total = result["detection_papers"]
    lines = [
        f"{result['abstracts']} abstracts indexed; {total} detection-related.",
        "",
        f"{'topic':<30} {'papers':>7}  {'share':>7}",
    ]
    for topic, count in sorted(topics.items(), key=lambda kv: -kv[1]):
        share = f"{100 * count / total:.1f}%" if total else "n/a"
        lines.append(f"{topic:<30} {count:>7}  {share:>7}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"),
                        help="where volume XML is stored (default: .anthology-cache)")
    parser.add_argument("--download", action="store_true", help="fetch missing volumes first")
    parser.add_argument("--topic", choices=sorted(TOPICS), help="list the papers behind one row")
    parser.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.download:
        available = download(args.cache)
        print(f"{available} volume(s) cached in {args.cache}", file=sys.stderr)

    if not args.cache.exists() or not any(args.cache.glob("*.xml")):
        print(f"no volume XML in {args.cache} — run with --download first "
              f"(~67 MB; needs access to raw.githubusercontent.com)", file=sys.stderr)
        return 1

    papers = load_abstracts(args.cache)

    if args.topic:
        hits = papers_for_topic(papers, args.topic)
        if args.as_json:
            print(json.dumps(hits, indent=2))
        else:
            print(f"{len(hits)} paper(s) under {args.topic!r}:")
            for paper in hits:
                print(f"  [{paper['id']}] {paper['title']}")
        return 0

    result = survey(papers)
    print(json.dumps(result, indent=2) if args.as_json else _render(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
