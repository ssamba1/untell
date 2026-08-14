"""fuzz_corpus.py — input generators for the untell fuzz probe.

Shared by fuzz_worker.py (chunk executor) and fuzz_driver.py (orchestrator).
Every generator is seeded from a fixed master seed so chunk runs are
deterministic and binary-search for hangs reproduces the same cases.

Design notes (why these buckets):
  - Lone surrogates (U+D800..DFFF) are NOT valid UTF-8 but ARE legal Python
    str; they are the classic crash trigger for code that encodes text
    (spacy, hashlib, json with ensure_ascii=False, stdout). Real text can
    never contain them, but the engine should fail cleanly, not traceback.
  - Zero-width / bidi / combining chars are the watermark-evasion corpus the
    tool itself defends against; they exercise scrub/lock/tells paths.
  - Control chars and NUL stress tokenisers and regex engines.
  - Long runs (50k+) stress truncation and catastrophic-backtracking paths.
  - Bytes inputs are type-malformed (signature says str) — we classify
    whether the resulting error is clean (TypeError) or a raw internal crash.
"""
from __future__ import annotations

import base64
import json
import os
import random
import string

MASTER_SEED = 0x5EEDF00D

# Curated codepoint buckets (kept small so corpus files stay tiny; each case
# samples a *mix* of buckets).
_ASCII_PRINT = list(range(0x20, 0x7F))
_ASCII_CTRL = [0x00, 0x01, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1B, 0x1F]
_LATIN1 = list(range(0xA0, 0x100))
_LATIN_EXT = list(range(0x100, 0x180))
_GREEK_CYRILLIC = list(range(0x370, 0x400)) + list(range(0x400, 0x500))
_HEBREW_ARABIC = list(range(0x590, 0x5F0)) + list(range(0x600, 0x700))
_COMBINING = list(range(0x300, 0x370))
_ZERO_WIDTH = [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C,
               0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0x00AD]
_BIDI = [0x05D0, 0x05D1, 0x0627, 0x0644, 0x0639, 0x202E]
_CJK = list(range(0x4E00, 0x4E80)) + list(range(0x3000, 0x3040))
_HANGUL = list(range(0xAC00, 0xAC80))
_EMOJI = list(range(0x1F300, 0x1F350)) + [0x1F600, 0x1F680, 0x1F92F]
_SURROGATES = list(range(0xD800, 0xE000))
_PRIVATE = list(range(0xE000, 0xE100))
_MATH = list(range(0x2200, 0x2250))
_FULLWIDTH = list(range(0xFF01, 0xFF60))
_BOX = list(range(0x2500, 0x2580))

_BUCKETS = [
    _ASCII_PRINT, _ASCII_CTRL, _LATIN1, _LATIN_EXT, _GREEK_CYRILLIC,
    _HEBREW_ARABIC, _COMBINING, _ZERO_WIDTH, _BIDI, _CJK, _HANGUL, _EMOJI,
    _SURROGATES, _PRIVATE, _MATH, _FULLWIDTH, _BOX,
]

_WORDS = ("the quick brown fox jumps over lazy dog committee proposal "
          "unanimously approved surprising development following report "
          "analysis system implementation framework platform leveraging "
          "showcasing boasts underscores ensuring moreover furthermore").split()


def rand_str(rng: random.Random, max_len: int = 2000) -> str:
    """Random unicode string mixing buckets; length 0..max_len."""
    n = rng.randint(0, max_len)
    if n == 0:
        return ""
    parts: list[str] = []
    while len(parts) < n:
        r = rng.random()
        if r < 0.55:
            parts.append(chr(rng.choice(_ASCII_PRINT)))
        elif r < 0.70:
            parts.append(chr(rng.choice(rng.choice(_BUCKETS))))
        elif r < 0.85:
            parts.append(rng.choice(" \t\n\r"))
        elif r < 0.95:
            parts.append(rng.choice(_WORDS))
        else:
            parts.append("".join(chr(rng.choice(_COMBINING))
                                 for _ in range(rng.randint(1, 4))))
    return "".join(parts[:n])


def rand_bytes(rng: random.Random, max_len: int = 2000) -> bytes:
    n = rng.randint(0, max_len)
    r = rng.random()
    if r < 0.4:
        # purely random bytes (almost always invalid UTF-8)
        return bytes(rng.randrange(256) for _ in range(n))
    if r < 0.7:
        # valid UTF-8 fragments plus injected garbage
        s = rand_str(rng, n // 2).encode("utf-8", errors="ignore")
        junk = bytes(rng.randrange(256) for _ in range(rng.randint(0, 8)))
        return s + junk
    if r < 0.9:
        # utf-16-ish / BOM-heavy
        return b"\xff\xfe" + bytes(rng.randrange(256) for _ in range(max(0, n - 2)))
    # NUL-heavy / control-heavy
    return bytes(rng.choice([0, 0, 0, 0, 1, 9, 10, 13, 26, 127, 255, 0x80])
                 for _ in range(n))


def weird_types(rng: random.Random) -> object:
    pool = [None, True, False, 0, 1, -1, 3.14, float("nan"), float("inf"),
            float("-inf"), [], {}, set(), (), b"", bytearray(b"x"), 1 + 2j,
            object(), Ellipsis, NotImplemented]
    return rng.choice(pool)


def sentinel_collision_text(rng: random.Random) -> str:
    """Text containing literal HZ sentinels the lock machinery may collide with."""
    parts = []
    for _ in range(rng.randint(1, 6)):
        idx = rng.randint(0, 99999)
        parts.append(f"⟦HZ{idx:04d}⟧")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Case set builders. Each returns list[dict] of JSON-safe case specs.
# "value" for str is a plain string (json escapes lone surrogates with
# ensure_ascii=True); for bytes it is {"b64": ...}; for other types it is a
# {"type": name} marker the worker re-materialises.
# ---------------------------------------------------------------------------

def case_str(value: str) -> dict:
    return {"v": value}


def case_bytes(value: bytes) -> dict:
    return {"b": base64.b64encode(value).decode("ascii")}


def case_type(name: str) -> dict:
    return {"t": name}


def build_score_cases(n_str: int = 300, n_bytes: int = 300, n_type: int = 100) -> list[dict]:
    rng = random.Random(MASTER_SEED)
    cases: list[dict] = []
    for i in range(n_str):
        r = rng.random()
        if r < 0.75:
            text = rand_str(rng)
        elif r < 0.85:
            text = sentinel_collision_text(rng)
        elif r < 0.92:
            text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(0, 200)))
        elif r < 0.97:
            text = "".join(rng.choice(".,!?;:()[]{}#*_~`'\"-+=/\\|<>@$%^&")
                           for _ in range(rng.randint(0, 300)))
        else:
            text = rand_str(rng, 50000)  # long-run truncation path
        cases.append({"surface": "score", "kind": "str", "text": case_str(text),
                      "tier": "lite"})
    for i in range(n_bytes):
        cases.append({"surface": "score", "kind": "bytes", "text": case_bytes(rand_bytes(rng))})
    type_pool = ["none", "int", "float", "nan", "inf", "list", "dict", "set",
                 "tuple", "bytes_empty", "bytearray", "complex", "object", "bool"]
    for i in range(n_type):
        cases.append({"surface": "score", "kind": "type",
                      "text": case_type(rng.choice(type_pool))})
    # tier / threshold variants (valid-ish structured probes)
    for i in range(30):
        tier = rng.choice(["lite", "full", "heavy", "commercial", "bogus", "",
                           "LITE", None, 3, ["lite"], "lite\x00"])
        thr = rng.choice([0.3, 0.0, 1.0, -0.5, 2.0, float("nan"), float("inf"),
                          "0.5", None, True])
        cases.append({"surface": "score", "kind": "param",
                      "text": case_str(rand_str(rng, 500)), "tier": tier,
                      "threshold": thr})
    return cases


def build_loop_cases(n: int = 300) -> list[dict]:
    rng = random.Random(MASTER_SEED + 1)
    cases: list[dict] = []
    for i in range(n):
        r = rng.random()
        if r < 0.5:
            text = rand_str(rng, 1200)
        elif r < 0.7:
            text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(0, 120)))
        elif r < 0.85:
            text = sentinel_collision_text(rng) + " " + rand_str(rng, 200)
        elif r < 0.95:
            text = rand_str(rng, 50)
        else:
            text = "".join(rng.choice(" \t\n\r") for _ in range(rng.randint(0, 100)))
        case: dict = {"surface": "loop", "text": case_str(text)}
        if rng.random() < 0.3:
            case["max_iters"] = rng.choice([0, 1, 2, 3, 10])
        if rng.random() < 0.2:
            case["threshold"] = rng.choice([0.3, 0.0, 1.0, -1.0, 2.0, float("nan")])
        if rng.random() < 0.15:
            case["scrub"] = rng.choice([True, False])
        if rng.random() < 0.1:
            case["tier"] = rng.choice(["lite", "", "bogus", None, 5])
        if rng.random() < 0.1:
            case["best_of"] = rng.choice([0, 1, 3, -2, 50])
        if rng.random() < 0.05:
            case["confirm"] = rng.choice([-1, 1, 5])
        cases.append(case)
    return cases


def build_preserve_cases(n: int = 300) -> list[dict]:
    rng = random.Random(MASTER_SEED + 2)
    cases: list[dict] = []
    for i in range(n):
        r = rng.random()
        if r < 0.6:
            text = rand_str(rng, 1500)
        elif r < 0.75:
            text = sentinel_collision_text(rng)
        elif r < 0.85:
            text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(0, 80)))
        elif r < 0.95:
            text = rand_str(rng, 20)
        else:
            text = rand_str(rng, 30000)
        cases.append({"surface": "preserve", "kind": "roundtrip",
                      "text": case_str(text)})
    # adversarial restore: mapping with fake sentinels / wrong values
    for i in range(60):
        fake_map = {}
        for _ in range(rng.randint(1, 8)):
            key = f"⟦HZ{rng.randint(0, 99999):04d}⟧"
            val = rng.choice([rand_str(rng, 50), 42, None, b"x",
                              ["a"], {"k": 1}])
            fake_map[key] = val
        cases.append({"surface": "preserve", "kind": "adversarial",
                      "text": case_str(rand_str(rng, 400)),
                      "mapping": fake_map})
    # type-malformed lock/restore
    for i in range(40):
        kinds = [("lock", "none"), ("lock", "bytes"), ("restore", "none"),
                 ("restore", "bytes"), ("restore", "int")]
        fn, t = kinds[i % len(kinds)]
        cases.append({"surface": "preserve", "kind": "type",
                      "fn": fn, "arg": case_type(t)})
    return cases


def build_tells_cases(n: int = 300) -> list[dict]:
    rng = random.Random(MASTER_SEED + 3)
    cases: list[dict] = []
    for i in range(n):
        r = rng.random()
        if r < 0.6:
            text = rand_str(rng, 3000)
        elif r < 0.8:
            text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(0, 150)))
        elif r < 0.9:
            text = sentinel_collision_text(rng)
        else:
            text = rand_str(rng, 60000)
        cases.append({"surface": "tells", "kind": "str",
                      "text": case_str(text),
                      "include_matches": rng.random() < 0.4})
    for i in range(60):
        cases.append({"surface": "tells", "kind": "bytes",
                      "text": case_bytes(rand_bytes(rng, 2000))})
    for i in range(40):
        cases.append({"surface": "tells", "kind": "type",
                      "text": case_type(["none", "int", "list", "dict"][i % 4])})
    return cases


def build_cli_cases(n: int = 300, seed: int = 100) -> list[dict]:
    """Random argv lists for the three CLIs (run in-process inside a worker)."""
    rng = random.Random(seed)
    cases: list[dict] = []
    for i in range(n):
        r = rng.random()
        argv: list[str] = []
        if r < 0.08:
            pass  # empty argv: `untell` -> demo; score/loop -> no input
        elif r < 0.20:
            argv = [rng.choice(["--help", "-h", "--bogus", "-x", "--version",
                                "--check", "--demo", "-d", "help"])]
        elif r < 0.35:
            argv = [rand_str(rng, 40)]  # bare text (humanize shortcut for `untell`)
        elif r < 0.55:
            argv = ["--tier", rng.choice(["lite", "full", "bogus", "", "LITE",
                                          "lite\x00"])]
            argv += [rand_str(rng, 60)]
        elif r < 0.65:
            argv = ["--threshold", rng.choice(["0.5", "abc", "-1", "2", "nan",
                                               "0.5.5", "\ud800", "1e309"])]
            argv += [rand_str(rng, 40)]
        elif r < 0.75:
            argv = ["--file", rng.choice(["nope.txt", "C:\\nope.docx", ".",
                                          "untell/scripts/score.py",
                                          "C:\\Windows\\system32", "\ud800x"])]
        elif r < 0.85:
            argv = ["--json", "--quiet", rand_str(rng, 80)]
        elif r < 0.92:
            argv = ["--seed", rng.choice(["0", "-1", "abc", "99999999999999999999",
                                          "1.5", "\ud800"])]
            argv += [rand_str(rng, 60)]
        else:
            argv = [rng.choice(["--max-iters", "--max-rounds", "--best-of",
                                "--margin", "--confirm", "--polish",
                                "--no-scrub", "--style"]),
                    rng.choice(["0", "1", "-3", "abc", "999"])]
            argv += [rand_str(rng, 40)]
        cases.append({"surface": "cli", "argv": argv})
    return cases


def materialise(case: dict) -> tuple:
    """Return the Python value for a case's 'text'/'arg' payload."""
    spec = case.get("text", case.get("arg"))
    if isinstance(spec, dict):
        if "b" in spec:
            return base64.b64decode(spec["b"])
        if "t" in spec:
            return {"none": None, "int": 7, "float": 1.5, "nan": float("nan"),
                    "inf": float("inf"), "list": [1, "x"], "dict": {"k": "v"},
                    "set": {1, 2}, "tuple": (1, 2), "bytes_empty": b"",
                    "bytearray": bytearray(b"x"), "complex": 1 + 2j,
                    "object": object(), "bool": True,
                    "bytes": b"\xff\x00"}[spec["t"]]
        if "v" in spec:
            return spec["v"]
    return spec


def dump_cases(path: str, cases: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=True) + "\n")


def load_cases(path: str) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
