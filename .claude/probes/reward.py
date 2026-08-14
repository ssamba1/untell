"""humanness_reward: hard gates return -1, faithful candidates get real rewards."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from training.reward import humanness_reward, _GATE_REWARD

out = {}
# 1. None candidate -> gate
out["none_gate"] = humanness_reward("Some text here.", None) == _GATE_REWARD
# 2. Empty candidate -> gate
out["empty_gate"] = humanness_reward("Some text here.", "") == _GATE_REWARD
# 3. Meaning drift -> gate
out["drift_gate"] = humanness_reward("The intervention halved mortality in the trial group over six months.",
                                     "Cats are pleasant animals that enjoy sleeping in warm places.") == _GATE_REWARD
# 4. Truncation (half length) -> gate
out["truncate_gate"] = humanness_reward("The intervention halved mortality in the trial group over six months of follow-up.",
                                        "The intervention halved mortality.") == _GATE_REWARD
# 5. Faithful paraphrase -> real reward > gate
r = humanness_reward("The intervention halved mortality in the trial group over six months.",
                     "The treatment reduced deaths by half during the six-month study period.")
out["faithful_reward"] = round(r, 4)
out["faithful_gt_gate"] = r > _GATE_REWARD
print(json.dumps(out, indent=1))
