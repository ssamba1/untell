import io, sys, json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rich_output import print_humanize_result

out = {}
# None max values (abstention path) must not crash
buf = io.StringIO()
old = sys.stdout
sys.stdout = buf
try:
    print_humanize_result(
        original="The system reads the file.",
        final="The system reads the file and processes it.",
        pre_score={"max": None, "tier": "lite"},
        post_score={"max": 0.42, "tier": "lite"},
        iterations=2, stopped="passed",
    )
    sys.stdout = old
    txt = buf.getvalue()
    out["no_crash"] = True
    out["prints_final"] = "processes it" in txt
    out["prints_delta"] = "0.42" in txt
except Exception as e:
    sys.stdout = old
    out["no_crash"] = False
    out["error"] = f"{type(e).__name__}: {str(e)[:60]}"
print(json.dumps(out, indent=1))
