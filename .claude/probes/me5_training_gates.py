"""L4 probe: training reward gate + distill SFT filter share the loop's NLI meaning gate.

PROBE 1 (training/reward.py humanness_reward):
  - reward uses meaning_preserved (the loop's gate: NLI conjunction), not raw cosine
  - faithful paraphrase > off-topic (off-topic hard-gated to _GATE_REWARD)
  - identical text > off-topic, never gated

PROBE 2 (training/distill.py filter):
  - distill filter = meaning_preserved(src, final, sim, sim_bar) — same gate
  - NLI-entailed faithful rewrite admitted to SFT set
  - contradictory rewrite excluded from SFT set (even when its raw sim is HIGHER)
"""

import os

os.environ["UNTELL_LITE_NO_TORCH"] = "1"

from untell.scripts.entailment import (
    available,
    contradiction_score,
    entailment_score,
    meaning_preserved,
)
from untell.scripts.quality import method, recommended_bar, similarity
import training.reward as r

ORIG = "The cat sat on the mat in the warm afternoon sun, perfectly content."
FAITHFUL = "The feline rested upon the rug during the sunny afternoon, quite satisfied."
OFF_TOPIC = "Quarterly revenue exceeded analyst expectations on strong enterprise demand."
CONTRADICTORY = "The cat refused to sit on the mat, shivering miserably in the cold dark rain."

print("NLI available:", available())
print("similarity backend:", method())
print("recommended_bar:", recommended_bar())
sim_f = similarity(ORIG, FAITHFUL)
sim_o = similarity(ORIG, OFF_TOPIC)
sim_c = similarity(ORIG, CONTRADICTORY)
print("similarity(orig, faithful):", round(sim_f, 4))
print("similarity(orig, off_topic):", round(sim_o, 4))
print("similarity(orig, contradictory):", round(sim_c, 4))

# --- PROBE 1: reward ordering (detector pinned, isolating the gates) ---
def _pinned(text, tier="full"):
    return 0.5

r.target_ai_score = _pinned
rw_identical = r.humanness_reward(ORIG, ORIG, tier="lite")
rw_faithful = r.humanness_reward(ORIG, FAITHFUL, tier="lite")
rw_offtopic = r.humanness_reward(ORIG, OFF_TOPIC, tier="lite")
print("\n[PROBE 1, detector pinned to 0.5]")
print("reward(identical):", rw_identical)
print("reward(faithful):", rw_faithful)
print("reward(off_topic):", rw_offtopic)
print("gate reward:", r._GATE_REWARD, "floor:", r._MIN_SCORED_REWARD)
print("identical >= faithful:", rw_identical >= rw_faithful)
print("faithful > off_topic:", rw_faithful > rw_offtopic)
print("off_topic == gate:", rw_offtopic == r._GATE_REWARD)

# live detector signal (real lite stack)
r.target_ai_score = r.__dict__["target_ai_score"]  # restore? no - keep pinned for ordering;
# instead import the real one fresh
import importlib

importlib.reload(r)
rw_live_identical = r.humanness_reward(ORIG, ORIG, tier="lite")
rw_live_faithful = r.humanness_reward(ORIG, FAITHFUL, tier="lite")
rw_live_offtopic = r.humanness_reward(ORIG, OFF_TOPIC, tier="lite")
print("\n[PROBE 1-live: real lite detector signal]")
print("reward(identical):", rw_live_identical)
print("reward(faithful):", rw_live_faithful)
print("reward(off_topic):", rw_live_offtopic)
print("identical > off_topic:", rw_live_identical > rw_live_offtopic)
print("faithful > off_topic:", rw_live_faithful > rw_live_offtopic)

# --- PROBE 2: distill filter (exact expression from training/distill.py line 82) ---
sim_bar = recommended_bar()
admit_faithful = (not False) and meaning_preserved(ORIG, FAITHFUL, sim_f, sim_bar)
admit_contradictory = (not False) and meaning_preserved(ORIG, CONTRADICTORY, sim_c, sim_bar)
print("\n[PROBE 2: distill SFT filter]")
print("filter admits NLI-entailed faithful rewrite:", admit_faithful)
print("filter excludes contradictory rewrite:", not admit_contradictory)
print("contradiction_score(orig, contradictory):", round(contradiction_score(ORIG, CONTRADICTORY) or 0.0, 4))
print("entailment_score(orig, contradictory):", round(entailment_score(ORIG, CONTRADICTORY) or 0.0, 4))
print("contradiction_score(orig, faithful):", round(contradiction_score(ORIG, FAITHFUL) or 0.0, 4))
print("entailment_score(orig, faithful):", round(entailment_score(ORIG, FAITHFUL) or 0.0, 4))
