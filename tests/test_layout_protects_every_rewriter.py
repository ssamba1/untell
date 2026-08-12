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
    # The prose in this case and the link-reference one below used to be a single short sentence.
    # It survived every rewriter, which reads as protection but was three of the four rewriters
    # declining to touch the document at all — a vacuous pass, found by giving every construct the
    # guard that only the indented-code case had. Lengthened until each has purchase.
    ("html block",
     'Moreover, the framework leverages robust methodologies to deliver outcomes, as shown below.\n\n'
     '<div class="note">\n  Additionally, note this.\n</div>\n\n'
     'In conclusion, it underscores the pivotal integration for every stakeholder involved.',
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
     "Moreover, the framework leverages robust methodologies to deliver outcomes; see [here][1]. "
     "In conclusion, it underscores the pivotal integration for every stakeholder involved.\n\n"
     "[1]: https://example.com/utilize-robust-methodologies",
     "https://example.com/utilize-robust-methodologies"),
    ("table",
     "Moreover, the framework leverages robust methods.\n\n| Method | Score |\n|---|---|\n"
     "| Ours | 0.91 |\n\nIn conclusion, done.",
     "| Method | Score |"),
    # Five constructs this list did not have. The gap worth naming is the first: the fenced block
    # is how code appears in almost every README, and the bug this file exists for was a rewriter
    # renaming an identifier inside INDENTED code. Same damage, commoner syntax, untested.
    ("fenced code",
     "Moreover, install it robustly:\n\n```bash\npip install untell --upgrade\n"
     "export UNTELL_LITE_NO_TORCH=1\n```\n\nIn conclusion, the framework leverages scale.",
     "```bash\npip install untell --upgrade\nexport UNTELL_LITE_NO_TORCH=1\n```"),
    ("atx heading",
     "# Deployment guide\n\nMoreover, the framework leverages robust methodologies at scale.",
     "# Deployment guide"),
    # A bare URL is a single token with meaning in every character; the link-reference case above
    # covers one inside a definition, not one sitting in a sentence the rewriter is working on.
    ("bare url in prose",
     "Moreover, read the notes at https://example.com/docs/getting-started?ref=guide robustly. "
     "In conclusion, the framework leverages robust methodologies at scale.",
     "https://example.com/docs/getting-started?ref=guide"),
    ("inline code span",
     "Moreover, set `verdict_threshold` to 0.45 robustly. In conclusion, the framework "
     "leverages robust methodologies to deliver outcomes at considerable scale.",
     "`verdict_threshold`"),
]

# List markers do not belong in the table above, and finding out why is worth recording. Written as
# a substring case with the needle "\n- Additionally," it failed on three of the four rewriters —
# because they had stripped the formulaic opener from the list item, which is precisely their job.
# The construct to protect is the MARKER, exactly as the footnote case above says of its own, and a
# substring needle cannot express "both markers are still there". So it gets a counting test.
LIST_DOC = (
    "Moreover, the framework leverages robust methods.\n\n- Additionally, run the first step\n"
    "- Furthermore, check the second step\n\nIn conclusion, done."
)

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
def test_every_list_marker_survives(rewriter: str) -> None:
    """Count, not substring: losing one bullet of two leaves every substring intact."""
    rw = get_rewriter(rewriter)
    scored = score_text(LIST_DOC, tier="lite")
    before = sum(1 for line in LIST_DOC.splitlines() if line.startswith("- "))
    assert before == 2, "fixture no longer has the two bullets this counts"
    for seed in range(4):
        random.seed(seed)
        out = rw.rewrite(LIST_DOC, scored, 0.3)
        after = sum(1 for line in out.splitlines() if line.startswith("- "))
        assert after == before, f"{rewriter} seed {seed}: {before} bullets -> {after}:\n{out}"


@pytest.mark.parametrize("rewriter", CPU_REWRITERS)
def test_the_list_item_text_is_still_rewritten(rewriter: str) -> None:
    """Guards the guard. Protecting the marker must not freeze the line it marks — the formulaic
    openers inside these items are exactly what the catalogue exists to remove, and three of the
    four rewriters do remove them."""
    rw = get_rewriter(rewriter)
    scored = score_text(LIST_DOC, tier="lite")
    outs = []
    for seed in range(4):
        random.seed(seed)
        outs.append(rw.rewrite(LIST_DOC, scored, 0.3))
    if rewriter == "surgical":
        pytest.skip("surgical substitutes vocabulary, not sentence openers; it leaves these intact")
    assert any(o != LIST_DOC for o in outs), f"{rewriter} left the document untouched at every seed"


@pytest.mark.parametrize(("name", "doc", "must_survive"), CONSTRUCTS, ids=lambda x: str(x)[:22])
def test_every_construct_document_has_rewritable_prose(
    name: str, doc: str, must_survive: str
) -> None:
    """Guards the guard, for EVERY construct rather than one.

    A survival test passes trivially when the rewriter does nothing, so each case above needs a
    partner showing the same document does change. This existed only for `CONSTRUCTS[2]`, which
    meant the four constructs added later could have been vacuous with nothing to say so.

    It asserts across the rewriters rather than per pair, because a rewriter DECLINING is
    legitimate: `surgical` only substitutes vocabulary, and `composite` returns its input whenever
    no draw scores better than leaving the text alone. Changes out of 8 seeds, per pair, measured:

                                  structural  surgical  composite  targeted
        html block                    8/8        0/8       0/8        8/8
        link reference definition     8/8        0/8       8/8        8/8
        everything else               8/8        8/8       8/8        8/8

    Those zeros are path-dependent, which is the part worth keeping. On the pure-stdlib lite path
    the same three pairs are 8/8, 8/8 and 6/8, and `inline code span` / surgical inverts to 0/8.
    The mechanism is `surgical_substitute(prefer_tells=True)`: it accepts a swap that removes a
    catalogued tell provided the score stays inside the loop's 0.02 noise band. The stdlib
    heuristic is insensitive to synonym substitution — its own docstring records swaps leaving the
    score bit-identical — so tell-removing swaps sit inside the band and are taken. GPT-2
    perplexity is sensitive, so the same swap can move the score past 0.02 and be refused. The
    weaker detector admits more rewriting, not less.
    """
    scored = score_text(doc, tier="lite")
    movers = []
    for rewriter in CPU_REWRITERS:
        rw = get_rewriter(rewriter)
        for seed in range(8):
            random.seed(seed)
            if rw.rewrite(doc, scored, 0.3) != doc:
                movers.append(rewriter)
                break
    assert movers, (
        f"no CPU rewriter ever changes the {name} document, so its survival test asserts only that "
        f"nothing happened"
    )


@pytest.mark.parametrize("rewriter", CPU_REWRITERS)
def test_the_prose_beside_it_is_still_rewritten(rewriter: str) -> None:
    """The original single-construct form, kept because the indented-code case is the one the bug
    was found on."""
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
