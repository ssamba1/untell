"""Pass 714 probe: io_utils write side + config module (untell)."""
import io
import logging
import os
import sys
import tempfile
import traceback

print(f"python: {sys.executable}")
print(f"PYTHONPATH={os.environ.get('PYTHONPATH')!r}")

sys.path.insert(0, os.getcwd())
from untell.scripts.io_utils import read_file, read_file_or_exit, read_stdin_or_none, configure_utf8_io
from untell import config

print("=" * 60)
print("PROBE 1: io_utils write side")
print("=" * 60)

# 1a. Write functions inventory
import inspect
import untell.scripts.io_utils as iu
writes = [n for n in dir(iu) if not n.startswith("__")]
print(f"io_utils public/private names: {writes}")
print(f"write-related names: {[n for n in writes if 'write' in n.lower()] or 'NONE - module is read-only'}")

# 1b. Round-trip: stdlib write -> read_file
tmpdir = tempfile.mkdtemp(prefix="io_wr_", dir=tempfile.gettempdir())
path = os.path.join(tmpdir, "roundtrip.txt")
content = "The quick brown fox jumps over the lazy dog.\nLine two with numbers 12345.\n"
with open(path, "w", encoding="utf-8") as fh:
    fh.write(content)
back = read_file(path)
print(f"roundtrip identical: {back == content}")
assert back == content, "roundtrip mismatch"

# 1c. UTF-8 with emoji survives
emoji_path = os.path.join(tmpdir, "emoji.txt")
emoji_content = "Hello 世界 🌍🎉 — smart 'quotes' and em-dash.\n第二行 with accented café naïve.\n"
with open(emoji_path, "w", encoding="utf-8") as fh:
    fh.write(emoji_content)
emoji_back = read_file(emoji_path)
print(f"emoji roundtrip identical: {emoji_back == emoji_content}")
print(f"emoji back repr: {emoji_back!r}")
assert emoji_back == emoji_content, "emoji mismatch"

# 1d. Append works
app_path = os.path.join(tmpdir, "append.txt")
with open(app_path, "w", encoding="utf-8") as fh:
    fh.write("first line\n")
with open(app_path, "a", encoding="utf-8") as fh:
    fh.write("second line appended\n")
app_back = read_file(app_path)
print(f"append readback: {app_back!r}")
assert app_back == "first line\nsecond line appended\n", "append mismatch"

# 1e. Bad path: clean error, not a traceback through the caller
print("-" * 40)
print("bad path via read_file (ValueError expected):")
try:
    read_file(os.path.join(tmpdir, "no_such_file.txt"))
    print("ERROR: no exception raised")
except ValueError as exc:
    print(f"clean ValueError: {exc}")
except Exception as exc:
    print(f"UNEXPECTED {type(exc).__name__}: {exc}")

print("bad path via read_file_or_exit (SystemExit 2 expected):")
try:
    read_file_or_exit(os.path.join(tmpdir, "no_such_file.txt"))
    print("ERROR: no exception raised")
except SystemExit as exc:
    print(f"clean SystemExit({exc.code})")

print("write to bad path (stdlib open, FileNotFoundError expected):")
try:
    with open(os.path.join(tmpdir, "no_such_dir", "x.txt"), "w") as fh:
        fh.write("x")
    print("ERROR: no exception raised")
except FileNotFoundError as exc:
    print(f"clean FileNotFoundError: {exc}")

# 1f. empty file roundtrip + read_stdin_or_none guard sanity
empty_path = os.path.join(tmpdir, "empty.txt")
open(empty_path, "w").close()
print(f"empty file read: {read_file(empty_path)!r}")

print("=" * 60)
print("PROBE 2: config module")
print("=" * 60)

# 2a. Config keys: defaults live in run.py _CLI_DEFAULTS
from untell.scripts.run import _CLI_DEFAULTS
print(f"_CLI_DEFAULTS: {_CLI_DEFAULTS}")

# 2b. Unknown key -> default
print(f"get('no_such_key', 'fallback') = {config.get('no_such_key', 'fallback')!r}")
print(f"get('no_such_key') (no default) = {config.get('no_such_key')!r}")

# 2c. Coercion: env string -> type of default
os.environ["UNTELL_MAX_ITERS"] = "7"
os.environ["UNTELL_THRESHOLD"] = "0.45"
os.environ["UNTELL_BEST_OF"] = "12"
v_int = config.get("max_iters", 5)
v_float = config.get("threshold", 0.30)
v_best = config.get("best_of", 3)
print(f"UNTELL_MAX_ITERS=7 -> get('max_iters',5) = {v_int!r} ({type(v_int).__name__})")
print(f"UNTELL_THRESHOLD=0.45 -> get('threshold',0.30) = {v_float!r} ({type(v_float).__name__})")
print(f"UNTELL_BEST_OF=12 -> get('best_of',3) = {v_best!r} ({type(v_best).__name__})")
assert v_int == 7 and isinstance(v_int, int)
assert v_float == 0.45 and isinstance(v_float, float)
assert v_best == 12 and isinstance(v_best, int)

# 2d. Bad env value -> default + warning on stderr
os.environ["UNTELL_MAX_ITERS"] = "abc"
stderr_buf = io.StringIO()
handler = logging.StreamHandler(stderr_buf)
logger = logging.getLogger("untell.config")
logger.setLevel(logging.WARNING)
logger.addHandler(handler)
v_bad = config.get("max_iters", 5)
print(f"UNTELL_MAX_ITERS=abc -> get('max_iters',5) = {v_bad!r} ({type(v_bad).__name__})")
print(f"warning captured: {stderr_buf.getvalue().strip()!r}")
assert v_bad == 5
assert "ignoring UNTELL_MAX_ITERS" in stderr_buf.getvalue()
logger.removeHandler(handler)

# 2e. Bad float env too
os.environ["UNTELL_THRESHOLD"] = "not-a-number"
stderr_buf2 = io.StringIO()
h2 = logging.StreamHandler(stderr_buf2)
logger.addHandler(h2)
v_badf = config.get("threshold", 0.30)
print(f"UNTELL_THRESHOLD=not-a-number -> get('threshold',0.30) = {v_badf!r}")
print(f"warning2 captured: {stderr_buf2.getvalue().strip()!r}")
assert v_badf == 0.30
assert "ignoring UNTELL_THRESHOLD" in stderr_buf2.getvalue()
logger.removeHandler(h2)
del os.environ["UNTELL_MAX_ITERS"]
del os.environ["UNTELL_THRESHOLD"]
del os.environ["UNTELL_BEST_OF"]

# 2f. At least 3 real keys resolve from defaults (no env, no config files in CWD)
#     CWD has pyproject.toml but NO [tool.untell], and no untell.yaml -> load() == {}
tier = config.get("tier", "full")
threshold = config.get("threshold", 0.30)
max_iters = config.get("max_iters", 5)
best_of = config.get("best_of", 3)
print(f"defaults: tier={tier!r} threshold={threshold!r} max_iters={max_iters!r} best_of={best_of!r}")
assert tier == "full" and threshold == 0.30 and max_iters == 5 and best_of == 3
print(f"load() in CWD = {config.load()!r}")

print("ALL ASSERTIONS PASSED")
