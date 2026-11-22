"""Corpora for auditing: your own files, and a git time capsule of pre-LLM human writing.

A false-positive audit is only as good as the claim that its "human" texts are human. For text
collected today that claim is getting hard to make. One source where it is still easy is version
control: prose committed to a repository before ChatGPT's public release (2022-11-30) was written
before the tools that could have written it existed. :func:`git_time_capsule` reads a repository
AS IT WAS at a cut-off date and returns its prose files with their provenance (commit, date), so
the "human" label rests on a timestamp rather than on trust.

Commit dates can be forged by whoever controls a repository, so use repositories whose history
you have reason to trust (well-known projects, mirrors you did not create). The provenance is
recorded on every document so a reader can check it.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import re
import subprocess
from pathlib import Path

__all__ = ["Doc", "load_corpus", "git_time_capsule", "corpus_fingerprint", "CHATGPT_RELEASE"]

CHATGPT_RELEASE = "2022-11-30"

Doc = dict  # {"id", "text", "label": "human"|"ai", "group", "author"?, "provenance"?}

_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def _wc(t: str) -> int:
    return len(_WORD.findall(t))


def _norm(doc: dict, i: int, default_label: str, default_group: str) -> Doc | None:
    text = doc.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    label = str(doc.get("label") or default_label).strip().lower()
    if label in ("0", "human", "h", "real"):
        label = "human"
    elif label in ("1", "ai", "machine", "generated", "llm"):
        label = "ai"
    out = {"id": str(doc.get("id") or f"doc{i:05d}"), "text": text, "label": label,
           "group": str(doc.get("group") or default_group)}
    for k in ("author", "provenance", "source"):
        if doc.get(k) is not None:
            out[k] = doc[k]
    # Writer metadata (grade, English-learner status, ...) for slicing a report card. Only flat
    # string values are kept, so a record cannot smuggle structure into the rows a card stores.
    meta = doc.get("meta")
    if isinstance(meta, dict):
        flat = {str(k): str(v) for k, v in meta.items() if isinstance(v, (str, int, float)) and str(v)}
        if flat:
            out["meta"] = flat
    return out


def load_corpus(path: str | Path, label: str = "human", group: str | None = None) -> list[Doc]:
    """Load a corpus from a ``.jsonl`` / ``.json`` / ``.csv`` file or a directory of text files.

    Records may carry ``text`` (required), ``label`` (``human``/``ai``; defaults to ``label``),
    ``group`` (a slice name such as ``non-native`` or ``grade-9``), ``author`` (for per-person
    rollups) and ``id``. In a directory, each ``.txt``/``.md`` file is one document and its
    parent sub-directory name is its group.
    """
    p = Path(path)
    docs: list[Doc] = []
    if p.is_dir():
        for i, f in enumerate(sorted(x for x in p.rglob("*") if x.suffix.lower() in (".txt", ".md"))):
            rel = f.relative_to(p)
            g = group or (rel.parts[0] if len(rel.parts) > 1 else p.name)
            d = _norm({"id": str(rel), "text": f.read_text(encoding="utf-8", errors="replace")},
                      i, label, g)
            if d:
                docs.append(d)
        return docs
    raw = p.read_text(encoding="utf-8")
    g = group or p.stem
    if p.suffix.lower() == ".jsonl":
        recs = [json.loads(line) for line in raw.splitlines() if line.strip()]
    elif p.suffix.lower() == ".json":
        data = json.loads(raw)
        recs = data if isinstance(data, list) else data.get("documents", [])
    elif p.suffix.lower() == ".csv":
        recs = list(csv.DictReader(raw.splitlines()))
    else:
        recs = [{"id": p.name, "text": raw}]
    for i, r in enumerate(recs):
        d = _norm(r if isinstance(r, dict) else {"text": r}, i, label, g)
        if d:
            docs.append(d)
    return docs


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


_FENCE = re.compile(r"^(```|~~~).*?^\1\s*$", re.M | re.S)
_MD_NOISE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|\||<|!\[|\[!\[)", re.M)


def prose_of(text: str) -> str:
    """Paragraphs of running prose from a Markdown/RST/plain file (code, tables, lists dropped)."""
    text = _FENCE.sub("", text)
    keep = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln for ln in para.splitlines() if ln.strip()]
        if not lines or any(_MD_NOISE.match(ln) for ln in lines):
            continue
        if any(ln.startswith(("    ", "\t", "..", "==", "--")) for ln in lines):
            continue
        p = " ".join(ln.strip() for ln in lines)
        if _wc(p) >= 25 and p.count("`") < 6:
            keep.append(p)
    return "\n\n".join(keep)


def git_time_capsule(
    repo: str | Path,
    before: str = CHATGPT_RELEASE,
    patterns: tuple[str, ...] = ("*.md", "*.rst", "*.txt"),
    min_words: int = 150,
    max_words: int = 800,
    limit: int | None = None,
    group: str | None = None,
) -> list[Doc]:
    """Prose from ``repo`` exactly as it stood at its last commit before ``before`` (YYYY-MM-DD).

    Each file yields at most one document of ``min_words``..``max_words`` words (longer files are
    cut at a paragraph boundary). Every document records the commit and its date.
    """
    r = Path(repo)
    commit = _git(r, "rev-list", "-1", f"--before={before}T00:00:00", "HEAD").strip()
    if not commit:
        raise ValueError(f"{repo} has no commit before {before}")
    cdate = _git(r, "show", "-s", "--format=%cI", commit).strip()
    files = [f for f in _git(r, "ls-tree", "-r", "--name-only", commit).splitlines()
             if any(fnmatch.fnmatch(Path(f).name.lower(), pat) for pat in patterns)]
    name = group or r.resolve().name
    docs: list[Doc] = []
    for f in sorted(files):
        try:
            raw = _git(r, "show", f"{commit}:{f}")
        except subprocess.CalledProcessError:
            continue
        paras = prose_of(raw).split("\n\n")
        chunk, words = [], 0
        for para in paras:
            w = _wc(para)
            if words and words + w > max_words:
                break
            chunk.append(para)
            words += w
        if words < min_words:
            continue
        docs.append({"id": f"{name}:{f}", "text": "\n\n".join(chunk), "label": "human",
                     "group": name,
                     "provenance": {"repo": name, "commit": commit, "commit_date": cdate,
                                    "path": f, "before": before}})
        if limit and len(docs) >= limit:
            break
    return docs


def corpus_fingerprint(docs: list[Doc]) -> str:
    """Order-independent SHA-256 over every document's label and text."""
    h = hashlib.sha256()
    for d in sorted(hashlib.sha256((d["label"] + "\0" + d["text"]).encode("utf-8")).hexdigest()
                    for d in docs):
        h.update(d.encode("ascii"))
    return h.hexdigest()
