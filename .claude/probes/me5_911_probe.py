"""Pass 911 probe: MCP tool set + CLI tells flag (2nd re-audit).

PROBE 1 (MCP): registered tool list vs _TOOL_NAMES; per-tool docstring parameter
coverage; score tool with invalid threshold returns refusal dict, not a crash.
PROBE 2 (CLI): untell.scripts.tells with and without --matches.
"""
import inspect
import json
import subprocess
import sys

sys.path.insert(0, ".")
from untell import mcp_server  # noqa: E402

print("=== PROBE 1a: registered tool names ===")
srv = mcp_server._server()
tools = {t.name: t for t in srv._tool_manager.list_tools()}
print("REGISTERED:", ",".join(sorted(tools)))
print("CONST:", ",".join(mcp_server._TOOL_NAMES))
print("SETS_EQUAL:", set(tools) == set(mcp_server._TOOL_NAMES))

print("=== PROBE 1b: docstring parameter coverage per tool ===")
for name in sorted(tools):
    t = tools[name]
    params = list(inspect.signature(t.fn).parameters)
    doc = t.description or ""
    missing = [p for p in params if p not in doc]
    print(f"DOCCHECK {name}: params={params} missing={missing}")

print("=== PROBE 1c: invalid threshold -> refusal dict, not crash ===")
score = tools["score"].fn
for th in (2.0, "abc", 1.5):
    try:
        r = score("hello world this is a test sentence", tier="lite", threshold=th)
        print(f"THRESH {th!r} -> keys={sorted(r)} err={r.get('error')!r}")
    except Exception as e:  # noqa: BLE001
        print(f"THRESH {th!r} -> EXCEPTION {type(e).__name__}: {e}")

print("=== PROBE 1d: valid threshold passes through to engine ===")
try:
    r = score("hello world this is a test sentence", tier="lite", threshold=0.5)
    print("THRESH 0.5 -> keys:", sorted(r))
except Exception as e:  # noqa: BLE001
    print("THRESH 0.5 -> EXCEPTION", type(e).__name__, e)

print("=== PROBE 2: CLI tells flag ===")
TEXT = ("In conclusion, it is important to note that moreover the framework "
        "showcases a robust solution. Additionally, it boasts remarkable versatility.")
base = [sys.executable, "-m", "untell.scripts.tells"]
for extra in ([], ["--matches"]):
    cmd = base + extra + [TEXT]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = p.stdout.strip()
    print(f"CLI extra={extra} exit={p.returncode}")
    print("STDOUT:", out.replace("\n", " | ")[:500])
    print("HAS_MATCHES_KEY_IN_OUT:", "matches" in out)
    print("STDERR:", p.stderr.strip()[:200] if p.stderr.strip() else "(empty)")

p = subprocess.run(base + ["--json", "--matches", TEXT], capture_output=True, text=True, timeout=120)
print(f"CLI --json --matches exit={p.returncode}")
try:
    d = json.loads(p.stdout)
    print("JSON keys:", sorted(d))
    print("JSON matches:", json.dumps(d.get("matches"))[:300])
except Exception as e:  # noqa: BLE001
    print("JSON PARSE FAIL:", e, p.stdout[:300])
