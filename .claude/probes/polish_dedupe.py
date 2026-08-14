"""Does _POLISH_FAILED warn for a SECOND, DIFFERENT exception type?"""
import json, os, logging
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.scripts.run as R

# Simulate the guard directly
R._POLISH_FAILED.clear()
log = []
class FakeLogger:
    def warning(self, msg, *a):
        log.append(msg % a)
orig = logging.getLogger
# The real code path uses logging.getLogger; monkeypatch the module's logger
import types
captured = []
class Capture:
    def warning(self, msg, *a, **k):
        captured.append(str(a[0]))
R.logging.getLogger = lambda name=None: Capture() if name == __name__ else orig(name)

# First failure: ValueError
exc1 = ValueError("transient")
if not R._POLISH_FAILED:
    R._POLISH_FAILED.add(type(exc1).__name__)
    captured.append(f"warned: {type(exc1).__name__}")
# Second failure: different type (KeyError) — should warn per the per-type claim
exc2 = KeyError("persistent broken model")
if not R._POLISH_FAILED:
    R._POLISH_FAILED.add(type(exc2).__name__)
    captured.append(f"warned: {type(exc2).__name__}")
else:
    captured.append(f"SUPPRESSED: {type(exc2).__name__} (set already non-empty)")

print(json.dumps({
    "events": captured,
    "set_after": sorted(R._POLISH_FAILED),
    "second_type_warned": "warned: KeyError" in captured,
}, indent=1))
R.logging.getLogger = orig
