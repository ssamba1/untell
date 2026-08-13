"""Does markdown scaffolding change the score? Three hypotheses, all wrong, and one thing that holds.

People paste READMEs, reports and docs. The detector scores the whole string, so headings, tables
and code fences are non-prose characters averaged in with the prose — an obvious mechanism for a
structured document to be scored as more human than its writing deserves.

**Hypothesis 1: markdown lowers the score.** MEASURED on the same 20 HC3 machine halves wrapped in
progressively more markdown, lite tier:

    plain prose             0.5632   min 0.3667   20 of 20 over the 0.30 threshold
    + headings              0.5608   min 0.3603   20 of 20
    + bullet list           0.5632   min 0.3667   20 of 20
    + table and code fence  0.4416   min 0.3001   20 of 20

Headings 0.002, lists 0.000, table and fence 0.122. Real but small, and it changes no verdict.

**Hypothesis 2: headings are nearly free.** Written into this file as an assertion and it failed
immediately — on a single 70-word paragraph, headings cost **0.256**, not 0.002. The corpus figure
was measured on long documents and says nothing about short ones.

**Hypothesis 3: the drop scales with the scaffolding's share of the document.** The obvious repair,
and also wrong. Fixed 30-word scaffold, prose truncated to a target length, 25 machine halves:

    prose 40 words (43% scaffold)   drop  +0.115
    prose 80 words (27% scaffold)   drop  -0.043     <- the scaffolding RAISED the score
    prose 150 words (17% scaffold)  drop  +0.031

Non-monotone, and it changes sign. There is no dilution law here to pin.

What survives all three: **no markdown form changed a single verdict.** 20 of 20 machine documents
stayed above the loop threshold in every form, and the weakest landed on 0.3001 — a hair above,
which is the one number in this file worth watching. That is what is asserted below. The per-element
figures are recorded as history, not as a contract, because two attempts to turn them into one
failed.

Written after a probe reported perfect structural fidelity on a markdown document — headings,
bullets, numbered list, blockquote, table, code fence, blank lines, all identical in and out — while
the rewriter had done nothing at all, the document having scored 0.144 against a 0.30 threshold.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import score_text

PROSE = (
    "The service runs behind a load balancer, and the health check must respond within two seconds "
    "or the node is removed from the pool. A slow readiness probe compounds during a rollout, "
    "because the balancer keeps sending traffic to a node that cannot answer it yet. The team "
    "settled on two seconds after watching three incidents that all began the same way."
)
HEADINGS = "# Overview\n\n" + PROSE + "\n\n## Detail\n\nThe rest follows from that decision.\n"
LIST = PROSE + "\n\n- A provisioned database\n- Credentials in the secret store\n- A DNS record\n"
EVERYTHING = (
    HEADINGS
    + "\n- A provisioned database\n- Credentials in the secret store\n- A DNS record\n"
    + "\n| Stage | Timeout |\n|-------|---------|\n| build | 10m     |\n"
    + "\n```bash\nkubectl apply -f manifest.yaml\n```\n"
)
FORMS = {"headings": HEADINGS, "list": LIST, "everything": EVERYTHING}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("name", sorted(FORMS))
def test_the_score_stays_in_range(name: str) -> None:
    """The weak claim that all three measurements support: scaffolding moves the score, in both
    directions, and never off the scale. Nothing stronger survived contact with a second corpus."""
    score = score_text(FORMS[name], tier="lite")["max"]
    assert 0.0 < score < 1.0, (name, score)


@pytest.mark.parametrize("name", sorted(FORMS))
def test_a_structured_document_still_gets_a_caveat(name: str) -> None:
    """What the user actually receives. No caveat says the score is diluted — correctly, since there
    is no consistent dilution to describe — but a structured document does get the layout note,
    which says the rewriter reached less of the text than it would have on the same words in
    ordinary prose. The reader is not handed a comfortable nothing."""
    warning = score_text(FORMS[name], tier="lite", threshold=0.3).get("warning") or ""
    assert warning.strip(), name


@pytest.mark.slow
def test_no_markdown_form_changes_a_verdict() -> None:
    """The claim that held across every attempt to break it, on the corpus that produced it. 20 of
    20 machine documents stay above the loop threshold in all four forms; the closest is 0.3001.

    This is the assertion worth having. If scaffolding ever starts pushing genuine AI text under the
    threshold, the tool silently stops offering to help exactly the documents people paste most."""
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    try:
        pairs = load_pairs("hc3", n=40, min_words=60)
    except Exception as exc:  # noqa: BLE001 - corpus availability is environmental
        pytest.skip(f"hc3 unavailable: {exc}")
    machine = [m for _, m in pairs][:10]
    scaffold_head, scaffold_tail = "# Overview\n\n", (
        "\n\n## Detail\n\n- One\n- Two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```bash\nrun --now\n```\n"
    )
    dropped = []
    for text in machine:
        plain = score_text(text, tier="lite")["max"]
        wrapped = score_text(scaffold_head + text + scaffold_tail, tier="lite")["max"]
        if plain >= 0.30 > wrapped:
            dropped.append((round(plain, 4), round(wrapped, 4)))
    assert not dropped, f"{len(dropped)} of {len(machine)} crossed below the threshold: {dropped[:3]}"
