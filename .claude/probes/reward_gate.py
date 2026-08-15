import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from training.reward import humanness_reward, _GATE_REWARD

out = {}
a = "The system reads the incoming file and processes every record in order."
# identical -> highest reward (no gate trip)
r_ident = humanness_reward(a, a, tier="lite")
out["identical_not_gated"] = r_ident != _GATE_REWARD
out["identical_reward"] = round(r_ident, 4)
# faithful paraphrase -> NOT gated (NLI admits it even below cosine bar)
paraphrase = "After opening the file, the system handles each record in sequence."
r_para = humanness_reward(a, paraphrase, tier="lite")
out["paraphrase_not_gated"] = r_para != _GATE_REWARD
out["paraphrase_reward"] = round(r_para, 4)
# off-topic -> gated to -1.0
offtopic = "The weather in Paris is lovely this time of year and the cafes are full."
r_off = humanness_reward(a, offtopic, tier="lite")
out["offtopic_gated"] = r_off == _GATE_REWARD
out["offtopic_reward"] = r_off
# empty candidate -> gated
out["empty_gated"] = humanness_reward(a, "", tier="lite") == _GATE_REWARD
out["none_gated"] = humanness_reward(a, None, tier="lite") == _GATE_REWARD
print(json.dumps(out, indent=1))
