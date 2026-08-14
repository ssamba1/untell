"""Restore capitalisation: does a locked span moved to sentence start get capitalised correctly?
And does capitalising a span that begins with a lowercase non-plain word corrupt it?"""
import json
from untell.scripts.preserve import lock, restore

# Case A: span locked mid-sentence, rewriter moves it to sentence start (simulated by masking pattern)
t = "the New York Times published the report, and the New York Times is just one outlet."
m, mp = lock(t)
print("A locked:", m)
# simulate the loop splitting at the sentence boundary: second sentence starts with sentinel
restored = restore("the New York Times published the report, and ⟦HZ0000⟧ is just one outlet.".replace("⟦HZ0000⟧", [k for k in mp if mp[k]=="the New York Times"][0]), mp)
print("A restored:", restored)
print("A has 'the ⟦' or 'The ' artifact:", "the New York Times" in restored and "The New York Times" not in restored)
