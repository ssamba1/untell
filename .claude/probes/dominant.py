import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.humanness import _dominant_signal

out = {}
# uniform rhythm -> burstiness named
uniform = "The kettle boiled while I read the last few pages. Rain had started again and the window fogged at the corners. I put the book down and went to find a coat."
out["uniform_signal"] = _dominant_signal(uniform, "lite")
# AI-tells-heavy -> tells named
tellsy = "Moreover, the framework leverages robust solutions to deliver outcomes at scale. It is important to note that the results demonstrate significant improvement in every domain. Additionally, the team utilized comprehensive methodologies to facilitate seamless integration."
out["tells_signal"] = _dominant_signal(tellsy, "lite")
# clean varied prose -> None or something sensible
clean = "We tried a few approaches and the last one finally worked. The numbers came out better than we hoped, though the first batch was a mess. Our intern fixed the parser and everything started passing again."
out["clean_signal"] = _dominant_signal(clean, "lite")
print(json.dumps(out, indent=1))
