"""Verify the claim: every distinct first-word in _SYN values gets a correct a/an from agree_article.
An article that flips wrongly (a university -> an university) is a defect in the closed vocabulary."""
import json
from untell.attacks.word_importance import _SYN, agree_article

first_words = set()
for key, repls in _SYN.items():
    for r in repls:
        first_words.add(r.split()[0].lower() if r.split() else r.lower())
# For each first word, decide the CORRECT article by vowel sound heuristics
VOWELS = set("aeiou")
silent_h = {"hour", "hourly", "honest", "honestly", "honor", "honour", "honorary", "honoured", "heir", "heiress"}
y_onset = {"one", "once", "use", "used", "useful", "user", "using", "usable", "usage", "usual", "usually", "unique", "unit", "united", "universal", "university", "uniform", "union", "unified", "utility", "utilize", "utilizing", "utilization", "euro", "european", "eulogy", "ubiquitous"}

wrong = []
for w in sorted(first_words):
    got = agree_article("a", w)
    if w[0] in VOWELS or w in silent_h:
        expect = "an"
    else:
        expect = "a"
    # y_onset words start with 'u'/'e' but sound consonant
    if w in y_onset:
        expect = "a"
    if got != expect:
        wrong.append((w, expect, got))
print("distinct first words:", len(first_words))
print("wrong articles:", len(wrong))
for w, e, g in wrong[:25]:
    print(f"  {w!r}: expected {e!r}, got {g!r}")
