import json
from untell._env import _parse_value

cases = {
    "plain": ("abc123", "abc123"),
    "inline_comment": ("abc123 # the prod key", "abc123"),
    "quoted": ('"abc123"', "abc123"),
    "quoted_with_comment": ('"abc" # note', "abc"),
    "quoted_keep_hash": ('"a#b"', "a#b"),
    "single_quoted": ("'xyz'", "xyz"),
    "unclosed_quote": ('"sk-broken', None),
    "empty": ("", ""),
    "spaces": ("  abc  ", "abc"),
    "hash_only": ("# just a comment", ""),
}
out = {}
for name, (raw, expected) in cases.items():
    got = _parse_value(raw)
    out[name] = {"got": got, "match": got == expected}
print(json.dumps(out, indent=1))
