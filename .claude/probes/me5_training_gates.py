"""L4 probe: training reward gate + distill SFT filter share the loop's NLI meaning gate.

PROBE 1 (training/reward.py humanness_reward):
  - reward uses meaning_preserved (the loop's gate: NLI conjunction), not raw cosine
  - faithful paraphrase > off-topic (off-topic hard-gated to _GATE_REWARD)
  - identical text > faithful paraphrase > off-topic

PROBE 2 (training/distill.py filter):
  - distill filter = meaning_preserved(src, final, sim, sim_bar) — same gate
  - NLI-entailed faithful rewrite admitted to SFT set
  - contradictory rewrite excluded from SFT set
"""

import os

os.environ["UNTELL_LITE_NO_TORCH"] = "1"

from untell.scripts.entailment import available, meaning_preserved
from untell.scripts.quality import recommended_bar, similarity
import training.reward as r

ORIG = "The cat sat on the mat in the warm afternoon sun, perfectly content."
FAITHFUL = "The feline rested upon the rug during the sunny afternoon, quite satisfied."
OFF_TOPIC = "Quarterly revenue exceeded analyst expectations on strong enterprise demand."
CONTRADICTORY = "The cat refused to sit on the mat, shivering miserably in the cold dark rain."

print("NLI available:", available())
print("recommended_bar:", recommended_bar())
print("similarity(orig, faithful):", round(similarity(ORIG, FAITHFUL), 4))
print("similarity(orig, off_topic):", round(similarity(ORIG, OFF_TOPIC), 4))
print("similarity(orig, contradictory):", round(similarity(ORIG, CONTRADICTORY), 4))

# --- PROBE 1: reward ordering ---
# Pin the detector signal so the comparison isolates the gates (same trick as the
# regression tests): target_ai_score returns a constant for every candidate.
orig_ai = r.target_ai_score  # keep the real one for the live probe below

import untell.scripts.quality as q

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
print("identical > faithful:", rw_identical > rw_faithful)
print("faithful > off_topic:", rw_faithful > rw_offtopic)
print("off_topic == gate:", rw_offtopic == r._GATE_REWARD)

# same gate as the loop? compare meaning_preserved verdict on the same pairs
print("\n[PROBE 1b: reward gate == meaning_preserved (loop gate)]")
print("meaning_preserved(orig, faithful):", meaning_preserved(ORIG, FAITHFUL, similarity(ORIG, FAITHFUL), recommended_bar()))
print("meaning_preserved(orig, off_topic):", meaning_preserved(ORIG, OFF_TOPIC, similarity(ORIG, OFF_TOPIC), recommended_bar()))

# --- PROBE 2: distill filter ---
# replicate the exact filter expression from training/distill.py line 82:
#   if not result.get("flagged") and meaning_preserved(src, result["final"], sim, sim_bar)
sim_bar = recommended_bar()
sim_f = similarity(ORIG, FAITHFUL)
sim_c = similarity(ORIG, CONTRADICTORY)
admit_faithful = (not False) and meaning_preserved(ORIG, FAITHFUL, sim_f, sim_bar)
admit_contradictory = (not False) and meaning_preserved(ORIG, CONTRADICTORY, sim_c, sim_bar)
print("\n[PROBE 2: distill SFT filter]")
print("filter admits NLI-entailed faithful rewrite:", admit_faithful)
print("filter excludes contradictory rewrite:", not admit_contradictory)
print("meaning_preserved(orig, contradictory):", meaning_preserved(ORIG, CONTRADICTORY, sim_c, sim_bar))

# live detector signal probe (no pin): identical vs faithful vs off-topic on the real lite stack
r.target_ai_score = orig_ai
rw_live_identical = r.humanness_reward(ORIG, ORIG, tier="lite")
rw_live_faithful = r.humanness_reward(ORIG, FAITHFUL, tier="lite")
rw_live_offtopic = r.humanness_reward(ORIG, OFF_TOPIC, tier="lite")
print("\n[PROBE 1-live: real lite detector signal]")
print("reward(identical):", rw_live_identical)
print("reward(faithful):", rw_live_faithful)
print("reward(off_topic):", rw_live_offtopic)
print("faithful > off_topic:", rw_live_faithful > rw_live_offtopic)
