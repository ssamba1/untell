"""`count_hidden` was quadratic, on the tool whose whole job is to scan a document.

It answered "how many characters would the scrubber remove or rewrite" by diffing the text against
its own scrubbed output with `difflib.SequenceMatcher(..., autojunk=False)`. `autojunk=False` is
required — the heuristic it disables discards exactly the frequent characters prose is made of —
and it is also the only thing keeping SequenceMatcher fast. MEASURED, one hidden character per 100:

    length    count_hidden    scrub_hidden      count_hidden (now)
       201        0.002s         0.0004s
     1,009        0.131s         0.0022s              0.0025s
     4,039        7.160s         0.0080s              0.0096s
     8,079       56.970s         0.0149s              0.0190s
    50,499        ~35 min        0.1100s              0.1170s

8x the length for 435x the time, while the scrub it is derived from stayed linear. The 50,000 row
is MAX_INPUT_CHARS, the cap `score` enforces — so a document at the documented limit, on the
`scrub` tool both the MCP and REST surfaces expose, and the scrubber itself cleans it in a tenth
of a second.

The replacement is a two-pointer walk with a bounded resynchronisation window, which is exact
because every pass in `scrub_hidden` maps one codepoint to zero or one codepoints.

IT IS ALSO MORE ACCURATE, which is not what a performance fix usually buys. Validated against
ground truth rather than against the implementation it replaces — 300 documents with exactly K
carriers injected at known positions, each removed or rewritten one-for-one, so the answer is K by
construction:

    this implementation      0 wrong of 300
    SequenceMatcher          8 wrong of 300

SequenceMatcher reports the alignment it finds and that alignment is not unique: rewriting U+00A0
to a space beside an existing space lets it match the run more than one way, and the opcode
arithmetic then charges for characters nothing touched. Checking the new code against the old would
have ratified those eight.

The first attempt at the two-pointer derailed and is why the window compares all three moves: with
a lone "do the tails line up?" test, a second edit inside the window makes a substitution look like
a deletion, the two strings stay one character out of step for the rest of the document, and the
count came back 58 where the answer was 4. 319 of 400 randomised inputs were wrong that way.
"""

from __future__ import annotations

import random
import time

import pytest

from untell.attacks import count_hidden, scrub_hidden

# One per carrier class the scrubber handles, each a single codepoint it removes or rewrites 1:1.
CARRIERS = [
    ("zero width space", chr(0x200B)),
    ("zero width non-joiner", chr(0x200C)),
    ("byte order mark", chr(0xFEFF)),
    ("soft hyphen", chr(0x00AD)),
    ("deprecated format", chr(0x206A)),
    ("arabic number sign", chr(0x0600)),
    ("word joiner", chr(0x2060)),
    ("non-breaking space", chr(0x00A0)),
]

WORDS = "the quick brown fox jumps over lazy dog and then some more".split()


@pytest.mark.parametrize("name,carrier", CARRIERS, ids=[c[0] for c in CARRIERS])
def test_one_carrier_counts_as_one(name: str, carrier: str) -> None:
    assert count_hidden(f"the quick{carrier} brown fox") == 1, name


def test_clean_text_counts_zero():
    assert count_hidden("Nothing hidden in this sentence at all.") == 0


def test_the_count_matches_the_number_of_carriers_injected():
    """Ground truth, not agreement with the previous implementation — that is what made the eight
    SequenceMatcher errors invisible."""
    rng = random.Random(7)
    wrong = []
    for _ in range(200):
        tokens = [rng.choice(WORDS) for _ in range(rng.randint(6, 40))]
        positions = rng.sample(range(len(tokens)), min(rng.randint(1, 12), len(tokens)))
        for p in positions:
            tokens[p] += rng.choice([c for _n, c in CARRIERS])
        text = " ".join(tokens)
        counted = count_hidden(text)
        if counted != len(positions):
            wrong.append((len(positions), counted, text[:60]))
    assert not wrong, f"{len(wrong)} of 200 documents miscounted, e.g. {wrong[:3]}"


def test_the_count_survives_carriers_next_to_what_they_become():
    """The shape that broke SequenceMatcher: U+00A0 rewrites to a space and there is already a space
    beside it, so more than one alignment explains the output."""
    assert count_hidden("dog  text") == 1
    assert count_hidden("dog  text  more") == 2


def test_a_document_at_the_input_cap_finishes_promptly():
    """The regression this exists for. A quadratic implementation needs tens of minutes here; the
    bound is loose enough that ordinary machine noise cannot trip it and tight enough that the old
    behaviour cannot pass — 8,079 characters alone took 57 seconds."""
    from untell.scripts.score import MAX_INPUT_CHARS

    base = "The quick brown fox jumps over the lazy dog. "
    text = (base * (MAX_INPUT_CHARS // len(base) + 1))[:MAX_INPUT_CHARS]
    dirty = chr(0x200B).join(text[i : i + 100] for i in range(0, len(text), 100))

    started = time.perf_counter()
    counted = count_hidden(dirty)
    elapsed = time.perf_counter() - started

    assert counted == len(dirty.split(chr(0x200B))) - 1
    assert elapsed < 10.0, f"{len(dirty)} characters took {elapsed:.1f}s"


def test_the_count_still_derives_from_the_scrubber():
    """The property six earlier versions lost: a class the scrubber handles must be counted without
    anyone remembering to add a counting term for it."""
    for _name, carrier in CARRIERS:
        text = f"the quick{carrier} brown fox"
        assert scrub_hidden(text) != text, f"{carrier!r} is not scrubbed; the fixture is stale"
        assert count_hidden(text) > 0
