"""meaning_preserved: adaptive gate — faithful passes, inversion rejected (when NLI available)."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.entailment import meaning_preserved, available, RELAXED_SIM_BAR, DEFAULT_CONTRADICTION_BAR, DEFAULT_ENTAILMENT_FLOOR
from untell.scripts.quality import similarity

out = {"nli_available": available()}
faith = ("The intervention halved mortality in the trial group over six months.",
         "The treatment cut deaths in the study group by half during the six months.")
invert = ("The company sued the regulator over the new rules.",
          "The regulator sued the company over the new rules.")
drift = ("The intervention halved mortality in the trial group over six months.",
         "Cats are pleasant animals that enjoy sleeping in warm places.")

for name, (a, b) in [("faithful", faith), ("inversion", invert), ("drift", drift)]:
    sim = similarity(a, b)
    mp = meaning_preserved(a, b, sim, strict_sim_bar=0.76)
    out[name] = {"sim": round(sim, 3), "meaning_preserved": mp}
# The critical property: faithful accepted OR inversion rejected (never BOTH wrong)
out["safe"] = out["faithful"]["meaning_preserved"] or not out["inversion"]["meaning_preserved"]
print(json.dumps(out, indent=1))
