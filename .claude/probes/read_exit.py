"""read_file_or_exit: every failure -> clean message + exit, never a raw traceback."""
import json, subprocess, sys, os, tempfile

env = dict(os.environ); env["PYTHONPATH"] = ""
script = (
    "import sys\n"
    "from untell.scripts.io_utils import read_file_or_exit\n"
    "try:\n"
    "    read_file_or_exit(sys.argv[1])\n"
    "    print('OK')\n"
    "except SystemExit as e:\n"
    "    print(f'EXIT:{e.code}')\n"
)
with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
    f.write(script)
    runner = f.name

cases = {
    "missing": "/nonexistent/nope.txt",
    "binary": None,
}
# binary file
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as bf:
    bf.write(b"\x00\x01\x02 binary content")
    cases["binary"] = bf.name

out = {}
for name, path in cases.items():
    r = subprocess.run([sys.executable, runner, path], capture_output=True, text=True, env=env, timeout=60)
    out[name] = {"exit": r.stdout.strip(), "stderr_tb": "Traceback" in r.stderr, "stderr_len": len(r.stderr)}
os.unlink(runner)
if cases.get("binary"): os.unlink(cases["binary"])
print(json.dumps(out, indent=1))
