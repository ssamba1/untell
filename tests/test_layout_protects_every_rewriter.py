"""Layout protection was a property of one rewriter, not of the pipeline.

`structural` and `mt_pivot` were the only backends calling `apply_per_block`, so the same document
survived `--rewriter structural` and was corrupted by the default `composite`, which reaches
`surgical`. MEASURED at every seed on a four-space indented code block:

        def f():                          def f():
            return utilize(x)      ->          return use(x)

Both halves are damage. The identifier was renamed, and the first line lost its indent, so what
remains does not render as code at all.

Two constructs also had no protection in `layout` itself, and both were rewritten at every seed:

    | Method | Score |              ->  | Way | Score |  /  | Technique | Score |
    title: Moreover the framework  ->  title: What is more the system

Five more unmarked constructs — setext headings, thematic breaks, HTML blocks, footnote definitions
and link reference definitions — reach the transform as prose and come back INTACT. They are pinned
here anyway: reaching the transform is exposure, and the only reason they are not damage today is
that no transform happens to touch them.
"""

from __future__ import annotations

import random

import pytest

from untell.rewriter import get_rewriter
from untell.scripts.score import score_text

# (name, document, the substring that must survive verbatim)
CONSTRUCTS = [
    ("setext heading",
     "Results\n=======\n\nMoreover, the framework leverages robust methodologies at scale.",
     "======="),
    ("thematic break",
     "Moreover, this holds robustly.\n\n---\n\nFurthermore, it leverages scale.",
     "\n---\n"),
    ("indented code",
     "Moreover, run this robustly:\n\n    def f():\n        return utilize(x)\n\nIn conclusion, done.",
     "    def f():\n        return utilize(x)"),
    ("html block",
     'Moreover, see below robustly.\n\n<div class="note">\n  Additionally, note this.\n</div>\n\nDone.',
     '<div class="note">'),
    ("yaml front matter",
     "---\ntitle: Moreover the framework\n---\n\nMoreover, the framework leverages robust methods.",
     "title: Moreover the framework"),
    # The MARKER, not the note text. A footnote's body is prose and rewriting it is the job; only
    # the `[^1]:` label has to survive, or the reference stops resolving. Asserting the whole line
    # was the first version of this and it failed on `composite` — correctly.
    ("footnote definition",
     "Moreover, see the note robustly.[^1]\n\n[^1]: Additionally, the authors leverage robust methods.",
     "[^1]:"),
    ("link reference definition",
     "Moreover, see [here][1] robustly.\n\n[1]: https://example.com/utilize-robust-methodologies",
     "https://example.com/utilize-robust-methodologies"),
    ("table",
     "Moreover, the framework leverages robust methods.\n\n| Method | Score |\n|---|---|\n"
     "| Ours | 0.91 |\n\nIn conclusion, done.",
     "| Method | Score |"),
]

# Every rewriter that runs without a key or a model download. The bug was that ONE of them had
# layout protection, so covering the registry is the point rather than covering `composite`.
CPU_REWRITERS = ["structural", "surgical", "composite", "targeted"]


@pytest.mark.parametrize(("name", "doc", "must_survive"), CONSTRUCTS, ids=lambda x: str(x)[:22])
@pytest.mark.parametrize("rewriter", CPU_REWRITERS)
def test_the_construct_survives_every_cpu_rewriter(
    rewriter: str, name: str, doc: str, must_survive: str
) -> None:
    rw = get_rewriter(rewriter)
    scored = score_text(doc, tier="lite")
    for seed in range(4):
        random.seed(seed)
        out = rw.rewrite(doc, scored, 0.3)
        assert must_survive in out, f"{rewriter} seed {seed} damaged {name}:\n{out}"


@pytest.mark.parametrize("rewriter", CPU_REWRITERS)
def test_the_prose_beside_it_is_still_rewritten(rewriter: str) -> None:
    """Guards the guard, per rewriter. Protecting the layout must not protect the document — a
    backend that stopped rewriting entirely would pass every test above."""
    doc = CONSTRUCTS[2][1]  # indented code, with prose either side
    rw = get_rewriter(rewriter)
    scored = score_text(doc, tier="lite")
    changed = False
    for seed in range(8):
        random.seed(seed)
        if rw.rewrite(doc, scored, 0.3) != doc:
            changed = True
            break
    assert changed, f"{rewriter} no longer changes a document containing a code block"


def test_surgical_still_substitutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """`surgical` now runs per block, so `max_subs` is per block rather than per document. That is
    the honest reading of the knob — it caps how much of any one passage is rewritten — but the
    substitution itself has to keep working.

    Pin the stdlib detector path. `tier="lite"` silently upgrades to GPT-2 perplexity whenever
    torch is importable, and the two disagree about this very text: stdlib scores it 0.6848
    (flagged at the 0.30 default, 2 substitutions) while the torch-backed path scores it 0.2824 —
    already passing, so `surgical_substitute` correctly declines to touch it and returns 0
    substitutions. The product behaviour is right on both paths; the test was reading an unpinned
    configuration and failed on any machine with torch installed. Same fix, and the same reason, as
    the two tests in tests/test_run.py that carry this note.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    text = (
        "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
        "It significantly improves overall efficiency and accuracy across the evaluated corpus."
    )
    scored = score_text(text, tier="lite")
    assert scored["max"] >= 0.3, (
        f"premise: this text must be flagged for a substitution to be requested (got {scored['max']})"
    )
    rw = get_rewriter("surgical")
    out = rw.rewrite(text, scored, 0.3)
    assert out != text
    assert "Moreover," not in out
