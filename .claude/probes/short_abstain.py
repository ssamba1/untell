"""score_text length floor + abstention semantics on the lite path."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text

probes = {
    "0_words": "",
    "1_word": "Hello",
    "2_words": "Hello world",
    "4_words": "The quick brown fox",
    "5_words": "The quick brown fox jumps",
    "39_words": " ".join(f"w{i}" for i in range(39)),
    "40_words": " ".join(f"w{i}" for i in range(40)),
    "punct_only": ";;; ;;; --- ...",
    "digits_only": "123 456 789 0123 4567 8901",
}
out = {}
for name, t in probes.items():
    s = score_text(t, tier="lite")
    out[name] = {"max": round(s.get("max", -1), 4), "flagged": s.get("flagged"),
                 "abstained": s.get("abstained", False),
                 "warning_present": bool(s.get("warning"))}
print(json.dumps(out, indent=1))
