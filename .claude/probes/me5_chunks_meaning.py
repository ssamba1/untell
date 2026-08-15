"""me5 probe: aligned_chunks coverage/order + meaning_preserved relaxed bar (live NLI)."""
import os
import re
import sys
import time

os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
t0 = time.time()

from untell.text_split import aligned_chunks, CHUNK_WORDS
from untell.scripts.entailment import (
    meaning_preserved, available, contradiction_score, entailment_score,
    RELAXED_SIM_BAR, DEFAULT_CONTRADICTION_BAR, DEFAULT_ENTAILMENT_FLOOR,
)
from untell.scripts.quality import similarity

print(f"CHUNK_WORDS={CHUNK_WORDS} RELAXED_SIM_BAR={RELAXED_SIM_BAR} CON_BAR={DEFAULT_CONTRADICTION_BAR} ENT_FLOOR={DEFAULT_ENTAILMENT_FLOOR}")

# ---------------- PROBE 1: aligned_chunks ----------------
BASE = (
    "The committee approved the proposal following an extensive deliberation among its members, and the revised "
    "budget was forwarded to the finance office for a final review before the end of the fiscal quarter. Several "
    "departments raised concerns about the projected costs, but the majority agreed that the expected benefits "
    "outweighed the initial investment. The implementation plan calls for a gradual rollout across the entire "
    "organization, beginning with the pilot sites in the northern region. Staff training sessions are scheduled "
    "for the first two weeks of the new term, and supervisors have been asked to identify additional support "
    "materials for their teams. A monitoring committee will review the progress reports every month and report "
    "any deviations from the schedule to the executive board. The board expects the first measurable results "
    "within six months, after which the approach may be extended to the remaining offices. Historical data from "
    "similar programs suggests that early engagement is the strongest predictor of long term success, so the "
    "communication strategy was given as much attention as the technical work. Weekly newsletters will keep "
    "everyone informed about the milestones, and an internal portal has been set up for questions and feedback. "
    "Managers were reminded that the success of the initiative depends on their willingness to model the new "
    "practices in their own daily routines. The final decision on the rollout calendar rests with the board, "
    "which meets again at the end of the month to consider the latest projections and any remaining concerns "
    "from the departments. In the meantime, the project office will publish a detailed timeline and a set of "
    "frequently asked questions to address the most common worries raised during the consultation phase. "
    "Everyone involved understands that the changes will take time to produce visible results, and the "
    "leadership has promised to communicate openly about the obstacles as well as the achievements along the way."
)
words = BASE.split()
assert len(words) >= 300, f"base too short: {len(words)}"
src = " ".join(words[:300])

# rewrite: move sentence #3 to the end + swap one word in every 7th position (1:1 word count)
sents = re.split(r"(?<=[.!?])\s+", src)
moved = sents.pop(3)
sents.append(moved)
syn = {"meeting": "gathering", "important": "significant", "project": "initiative",
       "team": "group", "decided": "determined", "report": "summary", "increase": "rise",
       "problem": "issue", "begin": "start", "provide": "give", "large": "big",
       "company": "firm", "system": "framework", "change": "shift", "final": "last"}
rw_words = [syn.get(w.lower(), w) if i % 7 == 0 else w for i, w in enumerate(src.split())]
rw = " ".join(rw_words[:300])

print(f"\n[P1] src_words={len(src.split())} rw_words={len(rw.split())}")
k_expected = max(1, -(-max(len(src.split()), len(rw.split())) // CHUNK_WORDS))
chunks = aligned_chunks(src, rw)
ta = sum(len(a.split()) for a, _ in chunks)
tb = sum(len(b.split()) for _, b in chunks)
recon_a = " ".join(a for a, _ in chunks).split() == src.split()
recon_b = " ".join(b for _, b in chunks).split() == rw.split()
print(f"[P1] k_expected={k_expected} n_chunks={len(chunks)} total_a={ta} total_b={tb} "
      f"coverage_a={ta == len(src.split())} coverage_b={tb == len(rw.split())} "
      f"ordered_a={recon_a} ordered_b={recon_b}")
for i, (a, b) in enumerate(chunks):
    print(f"  chunk{i}: a={len(a.split())}w b={len(b.split())}w  a_head={a.split()[:4]} b_head={b.split()[:4]}")

# short pair -> 1 chunk
short = aligned_chunks("The cat sat on the mat.", "The feline sat on the mat.")
print(f"[P1] short_pair_chunks={len(short)}")

# ---------------- PROBE 2: meaning_preserved (live NLI) ----------------
STRICT = 0.76
print(f"\n[P2] available()={available()} (UNTELL_DISABLE_NLI={os.environ.get('UNTELL_DISABLE_NLI')})")

def show(tag, src_t, rw_t):
    sim = similarity(src_t, rw_t)
    con = contradiction_score(src_t, rw_t)
    ent = entailment_score(src_t, rw_t)
    verdict = meaning_preserved(src_t, rw_t, sim, STRICT)
    print(f"[P2] {tag}: sim={sim:.4f} con={con} ent={ent} -> meaning_preserved={verdict} "
          f"(relaxed_bar={RELAXED_SIM_BAR}, strict={STRICT})")
    return verdict

# A: faithful register-shift paraphrase (sim below strict bar, NLI-entailed)
src_a = "The committee approved the proposal following an extensive deliberation among its members."
rw_a = "After a long deliberation, the committee gave the proposal the go-ahead."
v_a = show("faithful_paraphrase", src_a, rw_a)

# B: role swap (sim high, contradiction)
src_b = "The company sued the regulator."
rw_b = "The regulator sued the company."
v_b = show("role_swap", src_b, rw_b)

# C: unrelated
src_c = "The committee approved the proposal following an extensive deliberation among its members."
rw_c = "Quantum entanglement is a physical phenomenon observed at microscopic scales."
v_c = show("unrelated", src_c, rw_c)

print(f"\nSUMMARY: faithful={v_a} role_swap={v_b} unrelated={v_c} elapsed={time.time()-t0:.1f}s")
