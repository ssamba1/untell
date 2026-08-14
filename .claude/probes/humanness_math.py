"""humanness: weights sum to 1, extreme inputs map to sensible bands."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.humanness import _W_TELLS, _W_DETECTOR, _W_BURSTY, humanness

out = {}
out["weights_sum"] = round(_W_TELLS + _W_DETECTOR + _W_BURSTY, 6) == 1.0
# clean varied human prose -> high
h = humanness("We tried a few approaches and the last one finally worked. The numbers came out better than we hoped, though the first batch was a mess. Our intern fixed the parser and everything started passing again. It took most of the week but we got there in the end.", tier="lite")
out["human_score"] = h
out["human_in_range"] = 0 <= h <= 100
# AI-flavored -> lower
a = humanness("Moreover, the framework leverages robust solutions to deliver outcomes at scale. It is important to note that the results demonstrate significant improvement in every domain. Additionally, the team utilized comprehensive methodologies to facilitate seamless integration. The findings underscore pivotal paradigms that reshape the landscape of modern practice.", tier="lite")
out["ai_score"] = a
out["orders"] = h > a
print(json.dumps(out, indent=1))
