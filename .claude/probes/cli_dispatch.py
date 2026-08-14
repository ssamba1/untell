"""CLI dispatch: every registered command resolves to a callable, unknown refused."""
import json, os, importlib
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.cli import _COMMANDS, _STANDALONE_ONLY, main

out = {}
unresolved = []
for cmd, target in _COMMANDS.items():
    mod_name, _, attr = target.partition(":")
    try:
        mod = importlib.import_module(mod_name)
        if not callable(getattr(mod, attr)):
            unresolved.append(f"{cmd}: {attr} not callable")
    except Exception as e:
        unresolved.append(f"{cmd}: {type(e).__name__}")
out["all_commands_resolve"] = unresolved
overlap = _STANDALONE_ONLY.intersection(set(_COMMANDS))
out["standalone_overlap"] = sorted(overlap)
try:
    rc = main(["not-a-real-command", "some text"])
    out["unknown_rc"] = rc
except SystemExit as e:
    out["unknown_rc"] = e.code
print(json.dumps(out, indent=1))
