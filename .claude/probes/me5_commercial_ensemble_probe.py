import os, sys, json, logging

sys.path.insert(0, r"C:\Users\Admin\Humanize")
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
logging.basicConfig(level=logging.WARNING, format="LOG %(name)s: %(message)s")

print("=== PROBE 1: commercial detector error handling ===")
from untell.detectors.commercial import commercial_detectors
dets = commercial_detectors()
p1_avail = {d.name: d.available() for d in dets}
p1_tiers = {d.name: d.tier for d in dets}
print("P1 avail (no keys):", json.dumps(p1_avail))
print("P1 tiers:", json.dumps(p1_tiers))

from untell.detectors.base import load_detectors, _TIER_RANK
print("P1 commercial in _TIER_RANK:", "commercial" in _TIER_RANK, "| rank:", _TIER_RANK.get("commercial"))

roster = load_detectors("commercial")
roster_names = [d.name for d in roster]
print("P1 roster@commercial:", roster_names)
print("P1 commercial names in roster:", [n for n in roster_names if n in p1_avail])

scores = {}
for d in dets:
    try:
        scores[d.name] = d.score("The quick brown fox jumps over the lazy dog. " * 5)
    except Exception as e:
        scores[d.name] = f"RAISED {type(e).__name__}: {e}"
print("P1 direct score() no-key:", json.dumps(scores))

from untell.scripts.score import score_text
res = score_text("The quick brown fox jumps over the lazy dog. " * 10, tier="commercial")
print("P1 result keys:", sorted(res.keys()))
print("P1 tier:", res.get("tier"), "| requested:", res.get("tier_requested"),
      "| scored:", res.get("scored"), "| max:", res.get("max"),
      "| mean:", res.get("mean"), "| flagged:", res.get("flagged"))
print("P1 warning:", repr((res.get("warning") or "")[:280]))
print("P1 detectors:", json.dumps(res.get("detectors", {})))

print()
print("=== PROBE 2: ensemble rewriter state ===")
from untell.rewriter.ensemble import EnsembleRewriter, _RANK_EPS, _MEMBER_FAILED
ens = EnsembleRewriter()
print("P2 members:", ens.member_names)
print("P2 available:", ens.available(), "| _RANK_EPS:", _RANK_EPS)

TEXT = "The committee reviewed the proposal and decided to postpone the decision until next quarter. " * 4

# 2a: all members raise -> input returned unchanged
class _Boom:
    name = "boom"
    def rewrite(self, text, score_result, threshold):
        raise RuntimeError("simulated member failure")

ens2 = EnsembleRewriter()
ens2._members = [("boom", _Boom())]
out2 = ens2.rewrite(TEXT, {"tier": "full"}, 0.30)
print("P2 all-members-fail -> unchanged:", out2 == TEXT, "| len out:", len(out2), "| len in:", len(TEXT))

# 2b: passing candidate preferred over band mean
# fake members returning crafted candidates; patch module-level score_text (imported at call time)
import untell.rewriter.ensemble as E
import untell.scripts.score as SS

class _Cand:
    def __init__(self, name, out):
        self.name = name
        self.out = out
    def rewrite(self, text, score_result, threshold):
        return self.out

FAILING = "FAILING_CANDIDATE max=0.310 mean=0.20"
PASSING = "PASSING_CANDIDATE max=0.295 mean=0.25"
calls = {}
def fake_score(text, tier="full", threshold=0.30):
    if text == PASSING:
        calls["passing"] = calls.get("passing", 0) + 1
        return {"tier": tier, "max": 0.295, "mean": 0.25, "threshold": threshold}
    if text == FAILING:
        calls["failing"] = calls.get("failing", 0) + 1
        return {"tier": tier, "max": 0.310, "mean": 0.20, "threshold": threshold}
    calls["base"] = calls.get("base", 0) + 1
    return {"tier": tier, "max": 0.400, "mean": 0.35, "threshold": threshold}

orig_ss_score = SS.score_text
SS.score_text = fake_score
try:
    ens3 = EnsembleRewriter()
    ens3._members = [("fail_cand", _Cand("fail_cand", FAILING)), ("pass_cand", _Cand("pass_cand", PASSING))]
    out3 = ens3.rewrite(TEXT, {"tier": "full"}, 0.30)
finally:
    SS.score_text = orig_ss_score
print("P2 selection chose passing candidate:", out3 == PASSING, "| got:", repr(out3[:40]))
print("P2 score_text calls:", json.dumps(calls))

# 2c: band math check — both candidates within eps of best_max
best_max = 0.295  # min max
in_band_failing = 0.310 <= best_max + _RANK_EPS
print("P2 failing cand in band:", in_band_failing, "| passing < threshold:", 0.295 < 0.30)
