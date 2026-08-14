"""humanness vs score/tells: a more-human text scores higher humanness AND lower score/tells."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.humanness import humanness
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

ai = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
      "It is important to note that the results demonstrate significant improvement in every domain. "
      "Additionally, the team utilized comprehensive methodologies to facilitate seamless integration. "
      "The findings underscore pivotal paradigms that reshape the landscape of modern practice.")
human = ("We tried a few approaches and the last one finally worked. "
         "The numbers came out better than we hoped, though the first batch was a mess. "
         "Our intern fixed the parser and everything started passing again. "
         "It took most of the week but we got there in the end.")
out = {}
h_ai = humanness(ai, tier="lite")
h_h = humanness(human, tier="lite")
out["humanness_ai"], out["humanness_human"] = h_ai, h_h
out["humanness_orders"] = h_h > h_ai
s_ai = score_text(ai, tier="lite")
s_h = score_text(human, tier="lite")
out["score_ai"], out["score_human"] = s_ai["max"], s_h["max"]
out["score_orders"] = s_ai["max"] > s_h["max"]
t_ai = score_tells(ai)
t_h = score_tells(human)
out["tells_ai"], out["tells_human"] = t_ai["tells"], t_h["tells"]
out["tells_orders"] = t_ai["tells"] > t_h["tells"]
print(json.dumps(out, indent=1))
