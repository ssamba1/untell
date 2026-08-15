"""me5 pass probe: _duplicate_sentence_starts + NLI scores. Real functions, real numbers."""
import sys

import untell.scripts.tells as T
from untell.scripts.entailment import (
    available,
    contradiction_score,
    entailment_score,
)

print("NLI available:", available())

# ---- PROBE 1: _duplicate_sentence_starts ----
S_LONG = ("The committee reviewed the annual budget report and then approved the "
          "revised spending plan for the coming fiscal year without further discussion. ")
S_SHORT = "The plan was approved. "

cases = {
    # 4+ sentences all 'The', >= 60 words -> trigger expected, count = dupes (3)
    "all_the_4_long": (S_LONG * 4, 3),
    # 4 sentences all 'The' but < 60 words -> word guard returns 0
    "all_the_4_short": (S_SHORT * 4, 0),
    # exactly 2 sentences both 'The', >= 60 words -> too-few-openers guard returns 0
    "two_the_only": (S_LONG * 2, 0),
    # 6 sentences, 2 start 'The' -> dupes=1, share 16.7% < 40% -> 0
    "two_of_six_the": (
        S_LONG * 2
        + "This report covers the quarterly results and the outlook for the "
          "remaining months of the current calendar year. "
        + "These figures include revenue growth and operating margin data. "
        + "Our team prepared the analysis over several weeks. "
        + "Management reviewed every assumption carefully. ",
        0,
    ),
    # 5 sentences: The,The,This,This,This -> dupes=3, share 60% -> returns 3
    "mixed_count_check": (
        S_LONG + S_LONG
        + "This report covers the quarterly results and the outlook for the "
          "remaining months of the current calendar year. "
        + "These figures include revenue growth and operating margin data. "
        + "This analysis was prepared over several weeks. ",
        3,
    ),
}

for name, (text, expect_trigger) in cases.items():
    out = T._duplicate_sentence_starts(text)
    words = len(T._WORD.findall(text))
    print(f"dup_starts[{name}] words={words} -> {out} (expect {'>0' if expect_trigger else '0'})")

# ---- PROBE 2: NLI scores ----
IDENT = "The cat sat on the mat and watched the rain fall outside."
FAST = "The build runs significantly faster."
SLOW = "The build runs significantly slower."

c_ident = contradiction_score(IDENT, IDENT)
e_ident = entailment_score(IDENT, IDENT)
c_flip = contradiction_score(FAST, SLOW)
e_flip = entailment_score(FAST, SLOW)

print(f"contradiction_score(ident, ident) = {c_ident!r}")
print(f"entailment_score(ident, ident)    = {e_ident!r}")
print(f"contradiction_score(faster, slower) = {c_flip!r}")
print(f"entailment_score(faster, slower)    = {e_flip!r}")

# float-in-[0,1] checks on the model-backed pair
for label, v in [("contra_flip", c_flip), ("entail_flip", e_flip)]:
    print(f"type[{label}] = {type(v).__name__}, in[0,1] = {isinstance(v, float) and 0.0 <= v <= 1.0}")

print("DONE")
