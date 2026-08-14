import json, os, random
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
os.environ["UNTELL_SELECT"] = "dropout"
import untell.scripts.run as R

out = {}
score = {"detectors": {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5, "f": 0.6, "g": 0.7},
         "mean": 0.4, "max": 0.7}
for seed in range(5):
    rng = random.Random(seed)
    sub = R._selection_subset(score, rng)
    out[f"subset_s{seed}"] = {"size": len(sub), "names_ok": sub <= set(score["detectors"])}
rng = random.Random(1)
sub = R._selection_subset(score, rng)
obj = R._objective(score, sub)
out["objective_is_subset_max"] = (obj == max(score["detectors"][k] for k in sub))
out["subset"] = sorted(sub)
os.environ["UNTELL_SELECT"] = "mean"
out["mean_mode"] = R._objective({"detectors": {"a": 0.9}, "mean": 0.42, "max": 0.9}, None)
del os.environ["UNTELL_SELECT"]
small = {"detectors": {"a": 0.1, "b": 0.2}, "max": 0.2}
out["small_falls_back"] = R._selection_subset(small, random.Random(1)) is None
out["small_objective"] = R._objective(small, None)
out["bad_mode_falls_back"] = (os.environ.pop("UNTELL_SELECT", None) or "max")
os.environ["UNTELL_SELECT"] = "bogus"
out["bogus_mode"] = R._selection_mode()
del os.environ["UNTELL_SELECT"]
print(json.dumps(out, indent=1))
