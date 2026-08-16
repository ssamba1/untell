"""Slice 4 probe — sentence/layout round 3 boundary classes."""
import sys

sys.path.insert(0, r"C:/Users/Admin/Humanize")

from untell.text_split import split_sentences, ends_with_abbreviation
from untell.layout import apply_per_block, blocks

ID = lambda s: s  # identity transform: layout must survive untouched


def show(label, text, n_expected=None):
    out = split_sentences(text)
    mark = ""
    if n_expected is not None:
        mark = "  <-- COUNT MISMATCH" if len(out) != n_expected else ""
    print(f"[{label}] n={len(out)} {mark}")
    for i, s in enumerate(out):
        print(f"    {i}: {s!r}")
    return out


print("=" * 70)
print("1. ORDINAL SUFFIXES at sentence end")
show("1st", "He finished 1st. Then he celebrated.", 2)
show("22nd", "She placed 22nd. The crowd cheered.", 2)
show("3rd", "It was the 3rd. The next was easier.", 2)
show("ordinal+closer", 'He came in 1st." Then he left.', 2)
show("ordinal mid", "The 1st place went to Ana. She won.", 2)
show("ordinal no space", "He ranked 1st.2nd.3rd. overall.", 4)

print("=" * 70)
print("2. LATIN ABBREVIATIONS (other-language)")
show("etc", "Apples, pears, etc. are fruits. Oranges too.", 2)
show("vs", "The study compared X vs. Y. Results differed.", 2)
show("cf", "See cf. the appendix. Details follow.", 2)
show("ca circa", "Founded ca. 1850. The city grew fast.", 2)
show("ca lower cont", "Founded ca. 1850 and still standing. Truly.", 2)
show("approx", "Weights approx. 3 kg. Errors were small.", 2)
show("viz", "Three items, viz. a, b, c. All were used.", 2)
show("nb", "NB. the result matters. Read on.", 2)
show("sic", 'The text reads "recieve" [sic]. Odd.', 2)
show("op cit", "See Smith, op. cit. p. 4. The claim holds.", 2)
print("  ends_with_abbreviation('ca.'):", ends_with_abbreviation("ca."))
print("  ends_with_abbreviation('viz.'):", ends_with_abbreviation("viz."))
print("  ends_with_abbreviation('nb.'):", ends_with_abbreviation("nb."))

print("=" * 70)
print("3. NESTED QUOTES")
show("single in double", 'He said "She told me \'no.\' Then she left."', 1)
show("single in double 2", 'He said "She told me \'no.\'" Then he left.', 2)
show("double in single", "She said 'He yelled \"Go!\" and ran.'", 1)
show("quote then lower", '"Stop." he said quietly. Then all was calm.', 2)

print("=" * 70)
print("4. FOOTNOTE/ENDNOTE MARKERS")
show("bracket after period", "The result was significant.[1] However, the effect vanished.", 2)
show("superscript after period", "The result was significant.\u00b9 However, the effect vanished.", 2)
show("dagger after period", "The result was significant.\u2020 However, the effect vanished.", 2)
show("bracket before period", "The result was significant[1]. However, the effect vanished.", 2)
show("two markers", "Both results were significant.[1][2] Yet the story differs.", 2)
show("marker then lower", "The result was significant.[1] but only marginally.", 2)
show("marker+closer", "The result was significant.[1]\" He smiled. Then left.", 2)

print("=" * 70)
print("5. TABLE CELL BOUNDARIES (layout)")
tbl = "| Method | Score |\n|--------|-------|\n| A | 0.9 |\n| B | 0.8 |"
print("plain table blocks:", blocks(tbl))
print("plain table transformed:", repr(apply_per_block(tbl, ID)))
qtbl = "> | Method | Score |\n> | A | 0.9 |"
print("blockquote table blocks:", blocks(qtbl))
print("blockquote table transformed:", repr(apply_per_block(qtbl, ID)))
itbl = "  | Method | Score |\n  | A | 0.9 |"
print("indented table transformed:", repr(apply_per_block(itbl, ID)))
tbltxt = "Results below.\n| Method | Score |\n| A | 0.9 |"
print("table after prose blocks:", blocks(tbltxt))
print("table after prose transformed:", repr(apply_per_block(tbltxt, ID)))

print("=" * 70)
print("6. HEADING/PROSE TRANSITIONS (layout)")
setext = "My Heading\n==========\nSome prose here. More prose."
print("setext blocks:", blocks(setext))
print("setext transformed:", repr(apply_per_block(setext, ID)))
setext2 = "My Heading\n----------\nSome prose here."
print("setext --- blocks:", blocks(setext2))
print("setext --- transformed:", repr(apply_per_block(setext2, ID)))
hr = "Para one.\n---\nPara two."
print("thematic break blocks:", blocks(hr))
print("thematic break transformed:", repr(apply_per_block(hr, ID)))
atx = "Some text.\n# Heading\nMore text."
print("atx-after-prose blocks:", blocks(atx))
print("atx-after-prose transformed:", repr(apply_per_block(atx, ID)))
headcol = "# Heading:\n- item a\n- item b"
print("heading-colon blocks:", blocks(headcol))
print("heading-colon transformed:", repr(apply_per_block(headcol, ID)))

print("=" * 70)
print("7. LIST ITEMS WITH TRAILING COLONS (layout)")
lst = "Ingredients:\n- flour\n- sugar"
print("colon-then-list blocks:", blocks(lst))
print("colon-then-list transformed:", repr(apply_per_block(lst, ID)))
lst2 = "- Note: this matters.\n- Also: that matters."
print("colon items blocks:", blocks(lst2))
print("colon items transformed:", repr(apply_per_block(lst2, ID)))
lst3 = "The results were as follows:\n  - First result\n  - Second result"
print("colon-then-indented-list blocks:", blocks(lst3))
print("colon-then-indented-list transformed:", repr(apply_per_block(lst3, ID)))
lst4 = "- First:\n- Second:\n- Third:"
print("trailing-colon items blocks:", blocks(lst4))
print("trailing-colon items transformed:", repr(apply_per_block(lst4, ID)))
