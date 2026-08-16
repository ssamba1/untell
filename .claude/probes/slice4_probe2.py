"""Slice 4 probe 2 — real-damage demonstration for layout findings + deeper quote probes."""
import sys

sys.path.insert(0, r"C:/Users/Admin/Humanize")

from untell.layout import apply_per_block, blocks
from untell.text_split import split_sentences

# A merge transform: what sentence-merge rewriters do (" ".join(lines))
MERGE = lambda s: " ".join(x.strip() for x in s.split("\n") if x.strip())
# A substitution transform: what surgical/structural rewriters do
SUBS = lambda s: s.replace("Method", "Technique").replace("Results", "Findings")

print("--- F3a: setext heading (===) with merge transform")
src = "My Heading\n==========\nSome prose here. More prose."
print("blocks:", blocks(src))
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- F3b: setext heading (---) with merge transform")
src = "My Heading\n----------\nSome prose here."
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- F3c: thematic break between paragraphs, merge transform")
src = "Para one.\n---\nPara two."
print("blocks:", blocks(src))
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- F3d: starred HR with merge")
src = "Para one.\n* * *\nPara two."
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- F4: blockquote table with substitution transform")
src = "> | Method | Score |\n> |--------|-------|\n> | A | 0.9 |"
print("blocks:", blocks(src))
print("subbed:", repr(apply_per_block(src, SUBS)))

print("--- F4b: blockquote table with merge transform")
src = "> | Method | Score |\n> | A | 0.9 |"
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- control: plain table with merge transform (should stay intact)")
src = "| Method | Score |\n| A | 0.9 |"
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- nested quote, lowercase continuation inside outer quote")
out = split_sentences('He said "She told me \'no.\' and left."')
print("n=", len(out), out)

print("--- nested quote, two sentences inside outer quote")
out = split_sentences('He said "She told me \'no.\' Then she left."')
print("n=", len(out), out)

print("--- nested quote, period after inner closer + lowercase outside")
out = split_sentences("He said 'she whispered \"run.\" and froze.' Then all stopped.")
print("n=", len(out), out)

print("--- quote spanning paragraphs in layout (blank line inside quote)")
src = 'He said,\n"I\'m leaving.\n\nI can\'t stay here."'
print("blocks:", blocks(src))
print("identity:", repr(apply_per_block(src, lambda s: s)))
print("merged:", repr(apply_per_block(src, MERGE)))

print("--- quote opening in one paragraph, content next (no blank)")
src = 'He said,\n"I\'m leaving.\nI can\'t stay here."'
print("blocks:", blocks(src))
print("merged:", repr(apply_per_block(src, MERGE)))
