"""MCP tools: each returns a dict (not raises), bad args refused, compare works."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.mcp_server as M

# Get the FastMCP server and invoke tools via their raw functions
srv = M._server()
# Find tool callables
tool_fns = {}
for name in dir(srv):
    if name.startswith("_"):
        continue
    obj = getattr(srv, name)
    if callable(obj) and getattr(obj, "__name__", "") in ("score", "tells", "untell", "sentences", "verify_commercial", "compare"):
        tool_fns[obj.__name__] = obj

out = {}
# tells: normal
if "tells" in tool_fns:
    r = tool_fns["tells"]("Moreover, the framework leverages robust solutions.", include_matches=True)
    out["tells_ok"] = isinstance(r, dict) and r.get("tells") == 1
# score with bad tier -> refusal dict
if "score" in tool_fns:
    r = tool_fns["score"]("text", tier="bogus")
    out["bad_tier_refused"] = isinstance(r, dict) and "error" in str(r.get("error", "")).lower() or "tier" in json.dumps(r).lower()
# compare: works with sample corpus
if "compare" in tool_fns:
    r = tool_fns["compare"]()
    out["compare_ok"] = isinstance(r, dict) and "corpus" in r
    out["compare_corpus"] = r.get("corpus")
print(json.dumps(out, indent=1))
