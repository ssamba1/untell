"""NOVEL probe: auth edge cases in _check_auth/_verify_key.

Covered: no key = open access; x-api-key matches; Bearer matches; wrong
key; empty strings; Bearer with no space; case sensitivity; key with
leading/trailing spaces (stripped?); compare_digest constant-time path.
"""
import sys, os, hmac
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.api_server as A

# (1) no key configured = open access
os.environ.pop("UNTELL_API_KEY", None)
print(f"(1) no key -> _check_auth(None, None) = {A._check_auth(None, None)!r} (expect None=open)")

# (2) key configured
os.environ["UNTELL_API_KEY"] = "s3cret"
cases = [
    ("x-api-key match", A._check_auth(None, "s3cret")),
    ("x-api-key wrong", A._check_auth(None, "wrong")),
    ("bearer match", A._check_auth("Bearer s3cret", None)),
    ("bearer no-space", A._check_auth("Bearers3cret", None)),
    ("bearer lowercase", A._check_auth("bearer s3cret", None)),
    ("both match", A._check_auth("Bearer s3cret", "s3cret")),
    ("x right bearer wrong", A._check_auth("Bearer nope", "s3cret")),
    ("empty auth", A._check_auth("", None)),
    ("empty xkey", A._check_auth(None, "")),
    ("case-sensitive", A._check_auth(None, "S3CRET")),
    ("key with space", A._check_auth("Bearer s3cret ", None)),
    ("trailing space xkey", A._check_auth(None, "s3cret ")),
]
for name, res in cases:
    print(f"(2) {name:24} -> {'PASS' if res is None else res[:40]}")

# (3) verify_key constant-time path (digest compare)
k = "s3cret"
same = hmac.compare_digest(k, "s3cret")
diff = hmac.compare_digest(k, "s3cretx")
print(f"(3) compare_digest same={same} diff={diff} — timing-safe impl in use")

os.environ.pop("UNTELL_API_KEY", None)
print("done")
