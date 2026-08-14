"""io_utils: read/write round-trips, encoding detection, missing files, non-text bytes."""
import json, os, tempfile
from untell.scripts.io_utils import read_file, read_stdin_or_none

out = {}
# 1. UTF-8 read round-trip
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("café naïve — “quoted” \u2014 done\n")
    p = f.name
out["utf8_roundtrip"] = read_file(p) == "café naïve — “quoted” \u2014 done\n"
# 2. BOM
with open(p, "wb") as f:
    f.write(b"\xef\xbb\xbfBOM text here\n")
out["bom_stripped"] = read_file(p) == "BOM text here\n"
# 3. Missing file
try:
    read_file("/nonexistent/nope.txt")
    out["missing_raises"] = False
except Exception:
    out["missing_raises"] = True
# 4. Binary
with open(p, "wb") as f:
    f.write(b"\x00\x01\x02\xff binary")
try:
    r = read_file(p)
    out["binary_handled"] = True
    out["binary_ok"] = isinstance(r, str)
except Exception as e:
    out["binary_handled"] = False
    out["binary_error"] = f"{type(e).__name__}"
os.unlink(p)
print(json.dumps(out, indent=1))
