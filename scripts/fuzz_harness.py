"""fuzz_harness.py — reusable deterministic robustness fuzz for the untell public API + CLI.

Ships in-repo as the standing fuzz surface (pattern extended from
.claude/probes/fuzz_driver.py — that probe is a one-shot audit artifact; this
harness is the maintained, reusable version). Every generator is seeded, every
case runs inside a timeout thread, and every CLI subprocess spawn sanitises
argv the way Windows CreateProcess requires.

Surfaces (run one with --surface, or all):
    split      untell.text_split   split_sentences / aligned_chunks / abbreviation guards
    layout     untell.layout       apply_per_block / blocks / restore_layout_lines
    detectors  untell.detectors.base  normalise_for_scoring / windowed_max / clamp01 + lite score()
    api        scripts.score/run/tells/sentences/humanness — hostile text + type-malformed args
    mcp        untell.mcp_server._bad_args — the arg guard every MCP tool funnels through
    rest       untell.api_server request models + live TestClient endpoints (raw bodies)
    cli        in-process main() argv fuzz + one-shot subprocess runs (NUL-sanitised argv)
    preserve   scripts.preserve lock/restore round trips + adversarial mappings + type guards
    rest_socket  transport-level malformed HTTP against a LIVE in-process uvicorn server
                (raw bytes via http.client — bad method, bad headers, chunked-encoding
                abuse, request smuggling shapes). Contract: 4xx, never 5xx, never a wedge.
    mcp_stdio    MCP server over stdio (subprocess): initialize handshake, then garbage
                JSON-RPC lines (binary, NUL, 5MB, deep nesting) and hostile tools/call
                frames. Contract: JSON-RPC error/result responses, no traceback, clean exit.
    soak        500 sequential + 50 parallel POST /score against the live server:
                no 5xx, median-latency drift < 2x, tracemalloc memory plateau.

Usage (from repo root, PYTHONPATH cleared — the Hermes desktop app shadows pydantic_core):

    PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe scripts/fuzz_harness.py
    PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe scripts/fuzz_harness.py --surface split --quick

Output: JSONL findings to --out (default .claude/probes/fuzz_harness_findings.jsonl)
plus a numbered human summary on stdout. Exit code 0 always (findings are data,
not failures — CI watches the findings file).

Classification:
    DEFECT  unhandled exception / hang on valid-ish input — must fix
    GAP     exception on type-malformed input that leaks an internal message —
            should be a clean TypeError naming the contract (repo convention)
    OK      clean refusal / documented behaviour
"""
from __future__ import annotations

import argparse
import base64
import http.client
import io
import json
import os
import random
import re  # used by run_mcp_stdio_surface; upstream fca0c0c dropped it pre-slice
import socket
import statistics
import subprocess
import sys
import threading
import time
import traceback
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
DEFAULT_OUT = os.path.join(REPO, ".claude", "probes", "fuzz_harness_findings.jsonl")

ENV = dict(os.environ)
ENV["PYTHONPATH"] = ""
ENV["UNTELL_LITE_NO_TORCH"] = "1"
ENV["PYTHONUTF8"] = "1"

MASTER_SEED = 0x5EEDF00D

# --- corpus generators (seeded; ported/trimmed from .claude/probes/fuzz_corpus.py) ---------------

_ASCII_PRINT = list(range(0x20, 0x7F))
_ASCII_CTRL = [0x00, 0x01, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1B, 0x1F]
_LATIN_EXT = list(range(0x100, 0x180))
_COMBINING = list(range(0x300, 0x370))
_ZERO_WIDTH = [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C,
               0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0x00AD]
_BIDI = [0x05D0, 0x05D1, 0x0627, 0x0644, 0x0639, 0x202E]
_CJK = list(range(0x4E00, 0x4E80)) + list(range(0x3000, 0x3040))
_EMOJI = list(range(0x1F300, 0x1F350)) + [0x1F600, 0x1F680, 0x1F92F]
_SURROGATES = list(range(0xD800, 0xE000))
_MATH = list(range(0x2200, 0x2250))
_BOX = list(range(0x2500, 0x2580))

_BUCKETS = [_ASCII_PRINT, _ASCII_CTRL, _LATIN_EXT, _COMBINING, _ZERO_WIDTH,
            _BIDI, _CJK, _EMOJI, _SURROGATES, _MATH, _BOX]

_WORDS = ("the quick brown fox jumps over lazy dog committee proposal "
          "unanimously approved surprising development following report "
          "analysis system implementation framework platform leveraging "
          "showcasing boasts underscores ensuring moreover furthermore").split()

_SENTENCEY = ("The committee approved the proposal yesterday. Moreover, the framework "
              "showcases remarkable results. Dr. Smith and Prof. Jones agreed on the "
              "analysis. The mean was 3.5. Variance was low. He said \"Done.\" Then he left. "
              "It works... mostly. p.m. meetings are common. e.g. hammers are tools.")


def rand_str(rng: random.Random, max_len: int = 2000) -> str:
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
        return bytes(rng.randrange(256) for _ in range(n))
    if r < 0.7:
        s = rand_str(rng, n // 2).encode("utf-8", errors="ignore")
        junk = bytes(rng.randrange(256) for _ in range(rng.randint(0, 8)))
        return s + junk
    if r < 0.9:
        return b"\xff\xfe" + bytes(rng.randrange(256) for _ in range(max(0, n - 2)))
    return bytes(rng.choice([0, 0, 0, 0, 1, 9, 10, 13, 26, 127, 255, 0x80])
                 for _ in range(n))


def rand_layout(rng: random.Random, max_lines: int = 40) -> str:
    """Markdown-ish text mixing prose, fences, tables, lists, math and blank lines."""
    lines = []
    for _ in range(rng.randint(1, max_lines)):
        r = rng.random()
        if r < 0.35:
            lines.append(rand_str(rng, 80))
        elif r < 0.45:
            lines.append(rng.choice(["", "   ", "\t"]))
        elif r < 0.55:
            lines.append(rng.choice(["```", "```python", "~~~", "````"]))
        elif r < 0.62:
            lines.append("| " + " | ".join(rng.choice(_WORDS) for _ in range(3)) + " |")
        elif r < 0.70:
            lines.append(rng.choice(["- ", "* ", "+ ", "> ", "1. ", "5) ", "# ", "## "]) + rand_str(rng, 40))
        elif r < 0.78:
            lines.append("$$")
        elif r < 0.85:
            lines.append("    " + rand_str(rng, 40))
        elif r < 0.92:
            lines.append(rand_str(rng, 40) + rng.choice(["  ", ".", "!", "?"]))
        else:
            lines.append(rng.choice(["---", "...", "|", "```", "$$", "**bold**"]))
    return "\n".join(lines)


def rand_argv(rng: random.Random) -> list[str]:
    """Random CLI argv mixing flags, values, NULs, surrogates and long tokens."""
    r = rng.random()
    if r < 0.10:
        return [rng.choice(["--help", "-h", "--bogus", "-x", "--version", "--check",
                            "--demo", "help", "--json", "--quiet"])]
    if r < 0.25:
        return [rand_str(rng, 60)]
    if r < 0.45:
        return ["--tier", rng.choice(["lite", "full", "bogus", "", "LITE", "lite\x00x"]),
                rand_str(rng, 60)]
    if r < 0.60:
        return ["--threshold", rng.choice(["0.5", "abc", "-1", "2", "nan", "0.5.5",
                                           "\ud800", "1e309", "inf"]), rand_str(rng, 40)]
    if r < 0.75:
        return ["--file", rng.choice(["nope.txt", "C:\\nope.docx", ".", "\ud800x",
                                      "untell/scripts/score.py"])]
    if r < 0.85:
        return ["--seed", rng.choice(["0", "-1", "abc", "99999999999999999999", "1.5"]),
                rand_str(rng, 60)]
    if r < 0.95:
        return [rng.choice(["--max-iters", "--best-of", "--margin", "--confirm",
                            "--style", "--top", "--max-rounds"]),
                rng.choice(["0", "1", "-3", "abc", "999", "1e309"]), rand_str(rng, 40)]
    return [rand_str(rng, 40) + "\x00" + rand_str(rng, 10)]


def sanitise_argv(argv: list[str]) -> list[str]:
    """Strip NUL bytes before a subprocess spawn.

    Windows CreateProcess rejects an embedded NUL in the command line with
    ValueError: embedded null character — not a bug in the CLI, a constraint of
    the OS process model. The CLI can never receive NUL via argv, so the
    harness must not try to send it that way; it strips the NULs and notes the
    sanitisation on the result line. NUL *inside text* (stdin / --file / API
    body) still reaches the engine and is fuzzed there.
    """
    return [a.replace("\x00", "") for a in argv]


# --- case runners --------------------------------------------------------------------------------

def _materialise(spec):
    if isinstance(spec, dict):
        if "b" in spec:
            return base64.b64decode(spec["b"])
        if "t" in spec:
            return {"none": None, "int": 7, "float": 1.5, "nan": float("nan"),
                    "inf": float("inf"), "list": [1, "x"], "dict": {"k": "v"},
                    "set": {1, 2}, "tuple": (1, 2), "bytes_empty": b"",
                    "bytearray": bytearray(b"x"), "complex": 1 + 2j,
                    "object": object(), "bool": True, "bytes": b"\xff\x00"}[spec["t"]]
        if "v" in spec:
            return spec["v"]
    return spec


def _run_split(case):
    from untell.text_split import aligned_chunks, ends_with_abbreviation, split_sentences
    text = case["text"]
    parts = split_sentences(text)
    # round-trip sanity: splitting must not DROP content. Exact substring and
    # word-list checks are both too strict — abbreviation merges re-join with a
    # single space ("Dr.\tSmith" -> "Dr. Smith"), and the splitter's `\s+` is
    # unicode-aware while str.split() is ASCII-only, so a token containing a
    # U+3000/U+00A0 splits where split() keeps it whole. The invariant that
    # holds regardless: the multiset of non-whitespace characters is unchanged.
    orig_chars = sorted(c for c in text if not c.isspace())
    part_chars = sorted(c for c in "".join(parts) if not c.isspace())
    assert orig_chars == part_chars, (
        f"split dropped content: {len(orig_chars)} vs {len(part_chars)} chars"
    )
    ends_with_abbreviation(text)
    aligned_chunks(text, text)
    return {"ok": True, "n_sentences": len(parts)}


def _run_layout(case):
    from untell.layout import apply_per_block, blocks, restore_layout_lines
    text = case["text"]
    b = blocks(text)
    r1 = apply_per_block(text, lambda s: s.upper())
    apply_per_block(text, lambda s: s.replace("the", "a"))
    restore_layout_lines(text, r1)
    restore_layout_lines(text, "x\ny\nz")
    # a block transform must never drop a non-prose line
    for line in text.split("\n"):
        if line.strip().startswith("```") or line.strip() == "$$":
            assert line in r1, f"layout line vanished: {line!r}"
    return {"ok": True, "n_blocks": len(b)}


def _run_detectors(case):
    from untell.detectors.base import clamp01, load_detectors, normalise_for_scoring, windowed_max
    text = case["text"]
    normalise_for_scoring(text)
    normalise_for_scoring("\ud800" + text)
    x = case["x"]
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        clamp01(x)  # typed float helper: fuzz only numeric values
    windowed_max(text, lambda t: 0.5, window_words=64)
    for d in load_detectors("lite"):
        d.score(text)
    return {"ok": True}


def _run_api(case):
    kind = case.get("kind", "score")
    value = _materialise(case["text"])
    if kind == "score":
        from untell.scripts.score import score_text
        score_text(value, tier=case.get("tier", "lite"),
                   threshold=case.get("threshold", 0.3))
    elif kind == "tells":
        from untell.scripts.tells import score_tells
        score_tells(value, include_matches=True)
    elif kind == "sentences":
        from untell.scripts.sentences import score_sentences
        score_sentences(value, tier=case.get("tier", "lite"))
    elif kind == "humanness":
        from untell.humanness import humanness
        humanness(value, tier="lite")
    else:  # loop
        from untell.scripts.run import untell_text
        untell_text(value, tier="lite", max_iters=1, best_of=1, seed=7,
                    rewriter="surgical", scrub=False)
    return {"ok": True}


def _run_mcp(case):
    from untell.mcp_server import _bad_args
    kind = case["kind"]
    value = _materialise(case["arg"])
    name = case.get("name", "threshold")
    out = _bad_args(**{name: (value, kind)})
    if out is None:
        return {"ok": True, "accepted": True}
    return {"ok": True, "refused": True}


_REST_MODELS = {}


def _rest_model(name: str):
    if not _REST_MODELS:
        from untell.api_server import (
            CeilingRequest,
            HumanizeRequest,
            ScoreRequest,
            SentencesRequest,
            TellsRequest,
            VerifyRequest,
        )
        _REST_MODELS.update({"ScoreRequest": ScoreRequest,
                             "HumanizeRequest": HumanizeRequest,
                             "SentencesRequest": SentencesRequest,
                             "TellsRequest": TellsRequest,
                             "VerifyRequest": VerifyRequest,
                             "CeilingRequest": CeilingRequest})
    return _REST_MODELS[name]


def _run_rest(case):
    """Pydantic request-model validation (the REST edge). Network-free."""
    from pydantic import ValidationError

    cls = _rest_model(case["model"])
    payload = case["payload"]
    try:
        cls.model_validate(payload)
    except ValidationError:
        # A refusal IS the contract at the REST edge: pydantic exists to reject
        # malformed bodies, and FastAPI maps it to 422. Not a finding.
        return {"ok": True, "refused": True}
    return {"ok": True}


def _run_preserve(case):
    from untell.scripts.preserve import lock, restore
    kind = case.get("kind", "roundtrip")
    if kind == "roundtrip":
        text = case["text"]
        masked, mapping = lock(text)
        back = restore(masked, mapping)
        # lock() sanitises lone surrogates by design (spaCy rejects them; run.py
        # does the same before locking), so the round-trip contract is: exact for
        # decodable text, and the sanitised text back for surrogate-bearing input.
        expected = text.encode("utf-8", errors="replace").decode("utf-8") \
            if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text) else text
        assert back == expected, f"lock/restore changed text: {text!r} -> {back!r}"
    elif kind == "adversarial":
        text = case["text"]
        masked, mapping = lock(text)
        merged = dict(mapping)
        merged.update(case.get("mapping", {}))
        restore(masked, merged)
    elif kind == "type":
        fn = case.get("fn", "lock")
        arg = _materialise(case["arg"])
        if fn == "lock":
            lock(arg)
        else:
            restore(arg, {"\u27e6HZ0000\u27e7": "x"})
    return {"ok": True}


def _run_cli(case):
    """Run one CLI main() in-process with hostile argv."""
    which = case.get("which", "score")
    argv = case.get("argv", [])
    if which == "untell":
        from untell.scripts.cli import main
        # In-process `untell` with a text arg runs the full humanize loop; force
        # the fast lite path the same way the subprocess one-shots do, so the
        # surface under test is ARG PARSING, not loop throughput (covered by the
        # `api` surface). A hostile --tier/--threshold/--seed value still reaches
        # argparse unchanged — the prefix only sets the loop's speed knobs.
        argv = ["--tier", "lite", "--max-iters", "1", "--best-of", "1"] + list(argv)
    elif which == "sentences":
        from untell.scripts.sentences import main
        argv = ["--tier", "lite"] + list(argv)
    elif which == "scrub":
        from untell.scripts.scrub import main
    elif which == "tells":
        from untell.scripts.tells import main
    elif which == "preserve":
        from untell.scripts.preserve import main
    else:
        from untell.scripts.score import main
        argv = ["--tier", "lite"] + list(argv)
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf, buf
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else -1
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    out = buf.getvalue()
    if "Traceback (most recent call last)" in out:
        raise RuntimeError(f"traceback printed by main({argv!r}): {out[-400:]}")
    return {"ok": True, "code": code}


# --- rest_socket / soak: one live in-process uvicorn server per harness process ----------
#
# Transport-level fuzz cannot run against TestClient (it drives the ASGI app in-process and
# never touches a socket). We boot a real uvicorn server on 127.0.0.1:0 in a daemon thread
# and talk to it with http.client over actual TCP.
#
# NOTE on the event loop: uvicorn 0.49's asyncio_loop_factory returns ProactorEventLoop on
# Windows by default (this is also what the shipped `untell-server` runs), so no policy is
# forced here — the fuzz runs on the SHIPPED loop configuration. The flaky "wedged server"
# observations during development were CPU starvation (16 cores at 100% from sibling
# slices), handled below by retried liveness probes and generous timeouts.
_REST_SERVER = {"port": None, "server": None, "thread": None}
_REST_LOCK = threading.Lock()


def _ensure_rest_server() -> int:
    """Start (once) the in-process uvicorn server; return its port."""
    with _REST_LOCK:
        if _REST_SERVER["port"] is not None:
            return _REST_SERVER["port"]
        import uvicorn

        from untell.api_server import app

        # The soak makes 550 calls in ~a minute; the shipped default limit is 60/min.
        # The documented disable knob (UNTELL_RATE_LIMIT env var set to 0) is used below —
        # rate limiting has its own tests; the soak measures latency/memory, not throttling.
        os.environ["UNTELL_RATE_LIMIT"] = "0"
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error",
                                lifespan="off")
        server = uvicorn.Server(config)
        th = threading.Thread(target=server.run, daemon=True)
        th.start()
        for _ in range(400):
            if server.started:
                break
            time.sleep(0.02)
        if not server.started:
            raise RuntimeError("in-process uvicorn server failed to start")
        port = server.servers[0].sockets[0].getsockname()[1]
        _REST_SERVER.update(port=port, server=server, thread=th)
        return port


def _stop_rest_server() -> None:
    with _REST_LOCK:
        server = _REST_SERVER["server"]
        if server is None:
            return
        server.should_exit = True
        _REST_SERVER["thread"].join(15)
        _REST_SERVER.update(port=None, server=None, thread=None)


def _rest_send(port: int, raw: bytes, timeout: float = 10.0) -> dict:
    """Send raw bytes on a fresh connection; parse the response with http.client."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        conn.connect()
        conn.sock.sendall(raw)
        conn.sock.settimeout(timeout)
        try:
            resp = http.client.HTTPResponse(conn.sock)
            resp.begin()
            resp.read()
            return {"status": "ok", "code": resp.status}
        except socket.timeout:
            # No response bytes at all: the parser is waiting for more request input
            # (incomplete request line / chunk body) or the server is wedged. The probe
            # decides which.
            return {"status": "no_response"}
        except http.client.HTTPException as exc:
            return {"status": f"bad_response:{type(exc).__name__}"}
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except (ConnectionResetError, BrokenPipeError):
        return {"status": "reset"}
    except Exception as exc:  # noqa: BLE001 — fuzz: classify every transport outcome
        return {"status": f"client_err:{type(exc).__name__}:{exc}"}


def _rest_probe(port: int, attempts: int = 3, timeout: float = 5.0) -> bool:
    """Liveness probe on a FRESH connection, retried (the box is often CPU-starved)."""
    for _ in range(attempts):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
            conn.request("GET", "/health")
            r = conn.getresponse()
            ok = r.status == 200
            conn.close()
            if ok:
                return True
        except Exception:  # noqa: BLE001 — probe: any failure means "not healthy now"
            pass
        time.sleep(0.5)
    return False


# Curated malformed-HTTP battery: bad method / bad headers / chunked-encoding abuse /
# request-smuggling shapes. Every case must draw a 4xx (or keep the server healthily
# waiting for more input); 5xx or a wedged server is a DEFECT.
_REST_RAW_CASES = [
    ('bad_method_unknown', b'BREW /score HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}'),
    ('bad_method_space_in_token', b'GE T /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('bad_method_nul', b'\x00GET /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('bad_method_crlf_inject', b'GET\r\n /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('bad_method_tab_sep', b'GET\t/score\tHTTP/1.1\r\nHost: x\r\n\r\n'),
    ('bad_method_lowercase', b'get /score HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}'),
    ('bad_method_connect', b'CONNECT /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('no_method', b' /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('bad_version', b'GET /score HTTP/9.9\r\nHost: x\r\n\r\n'),
    ('no_version', b'GET /score\r\nHost: x\r\n\r\n'),
    ('http09_style', b'GET /\r\n'),
    ('header_no_colon', b'GET /score HTTP/1.1\r\nHost x\r\n\r\n'),
    ('header_space_in_name', b'GET /score HTTP/1.1\r\nBad Header: x\r\n\r\n'),
    ('header_ctrl_in_value', b'GET /score HTTP/1.1\r\nX-Foo: \x01\x02\x7f\r\n\r\n'),
    ('header_nul', b'GET /score HTTP/1.1\r\nX-Foo: a\x00b\r\n\r\n'),
    ('header_crlf_inject', b'GET /score HTTP/1.1\r\nX-Foo: a\r\nInjected: b\r\n\r\n'),
    ('dup_content_length', b'POST /score HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\nContent-Length: 6\r\n\r\nhello!'),
    ('cl_and_te', b'POST /score HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n'),
    ('huge_header_name', b'GET /score HTTP/1.1\r\n' + b'A' * 90000 + b': x\r\n\r\n'),
    ('chunk_bad_size_hex', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\nzzz\r\nhello'),
    ('chunk_neg_size', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n-5\r\nhello'),
    ('chunk_huge_size', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\nFFFFFFFFFFFFFFFF\r\nhello'),
    ('chunk_plus_size', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n+5\r\nhello'),
    ('chunk_0x_size', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n0x5\r\nhello'),
    ('chunk_ext_weird', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n5;foo="bar"\r\nhello\r\n0\r\n\r\n'),
    ('chunk_no_final_zero', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n'),
    ('chunk_trailing_garbage', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\nGARBAGE'),
    ('chunk_size_with_space', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n5 \r\nhello\r\n0\r\n\r\n'),
    ('chunk_undersized_data', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n10\r\nhi\r\n0\r\n\r\n'),
    ('weird_leading_spaces', b'   GET /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('garbage_binary', b'\xff\xfe\x00\x01GARBAGE\r\n\r\n'),
    ('partial_request_line', b'GET /sco'),
    ('extra_crlf_before', b'\r\nGET /score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('asterisk_target', b'OPTIONS * HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('absolute_target', b'GET http://example.com/score HTTP/1.1\r\nHost: x\r\n\r\n'),
    ('http10_chunked', b'POST /score HTTP/1.0\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n'),
    ('get_with_cl', b'GET /score HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}'),
    ('smuggle_te_cl', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nContent-Length: 4\r\n\r\n0\r\n\r\n'),
    ('te_gzip_chunked', b'POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: gzip, chunked\r\n\r\n0\r\n\r\n'),
]

_RAW_METHODS = (b"GET", b"POST", b"BREW", b"\x00GET", b"GE T", b"get", b"CONNECT")


def _rand_raw(rng: random.Random) -> bytes:
    """Seeded random byte mutation for the transport surface."""
    r = rng.random()
    if r < 0.45:
        return bytes(rng.randrange(256) for _ in range(rng.randint(1, 150)))
    if r < 0.75:
        return (rng.choice(_RAW_METHODS) + b" " +
                bytes(rng.randrange(256) for _ in range(rng.randint(0, 50))) +
                rng.choice([b" HTTP/1.1", b" HTTP/9.9", b""]) + b"\r\n" +
                bytes(rng.randrange(256) for _ in range(rng.randint(0, 80))) + b"\r\n\r\n")
    base = rng.choice(_REST_RAW_CASES)[1]
    raw = bytearray(base)
    for _ in range(rng.randint(1, 4)):
        if raw:
            raw[rng.randrange(len(raw))] = rng.randrange(256)
    return bytes(raw)


def _run_rest_socket(case):
    """One malformed-HTTP frame against the live server. 5xx or a wedge is a DEFECT."""
    port = _ensure_rest_server()
    raw = case["raw"].encode("latin1")
    outcome = _rest_send(port, raw)
    if outcome["status"] == "ok":
        code = outcome["code"]
        if 500 <= code < 600:
            raise RuntimeError(f"server answered HTTP {code} to malformed input {raw[:80]!r}")
        return {"ok": True, "code": code}
    if outcome["status"] == "no_response":
        # No bytes back: either the parser is waiting for more input (incomplete request —
        # correct) or the server is wedged. The probe decides, with retries for the
        # CPU-starved box.
        if _rest_probe(port):
            return {"ok": True, "note": "incomplete request; server healthy and waiting"}
        raise RuntimeError(f"server unresponsive after malformed input {raw[:80]!r}")
    if outcome["status"].startswith("bad_response"):
        # The server wrote bytes http.client could not parse as an HTTP response — e.g. a
        # bare-body HTTP/0.9-style answer. Recorded, not a defect: the server answered.
        return {"ok": True, "note": outcome["status"]}
    raise RuntimeError(f"transport outcome {outcome['status']} on {raw[:80]!r}")


# --- soak: 500 sequential + 50 parallel REST calls ----------------------------------------
# Assertions (the shipped test mirrors these):
#   * every call answers 200 (no 5xx, and no unexpected 4xx on a well-formed request)
#   * median latency of the last 100 calls < 2x the first 100 (no drift)
#   * tracemalloc current/peak after the soak < first-checkpoint + 8MB (plateau, no leak)
# Rate limiting is disabled via the documented knob (UNTELL_RATE_LIMIT env var set to 0).
_SOAK_SEQ = 500
_SOAK_PAR = 50
_SOAK_PAR_WORKERS = 16
_SOAK_TEXT = ("The committee approved the proposal yesterday, and moreover the framework "
              "showcases remarkable results across several benchmarks. Dr. Smith and Prof. "
              "Jones agreed on the analysis, noting that the mean was 3.5 and variance low. "
              "It works... mostly. Meetings are common at 9:30 p.m. and the deadline is "
              "Friday, June 14th, 2026, at 5 p.m. precisely.") * 3
_SOAK_BODY = json.dumps({"text": _SOAK_TEXT, "tier": "lite"}).encode()
_SOAK_MEM_SLACK = 8 * 1024 * 1024


def _soak_call(port: int, timeout: float = 120.0) -> tuple[int, float]:
    t0 = time.time()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/score", body=_SOAK_BODY,
                 headers={"content-type": "application/json"})
    r = conn.getresponse()
    r.read()
    status = r.status
    conn.close()
    return status, time.time() - t0


def _run_soak(case):
    """The full soak. Any assertion failure raises (=> DEFECT finding)."""
    port = _ensure_rest_server()
    # Warm up: the first call in a fresh process costs ~27-38s (imports + detector
    # resolution on this box); it is not part of the measured window.
    st, _ = _soak_call(port)
    if st != 200:
        raise RuntimeError(f"warmup call answered {st}")
    st, _ = _soak_call(port)
    if st != 200:
        raise RuntimeError(f"second warmup call answered {st}")

    tracemalloc.start()
    latencies: list[float] = []
    checkpoints: list[tuple[int, int]] = []
    bad: list[tuple[str, int, int]] = []
    try:
        for batch in range(_SOAK_SEQ // 100):
            for i in range(100):
                st, dt = _soak_call(port)
                latencies.append(dt)
                if st != 200:
                    bad.append(("seq", batch * 100 + i, st))
            cur, peak = tracemalloc.get_traced_memory()
            checkpoints.append((cur, peak))
        with ThreadPoolExecutor(max_workers=_SOAK_PAR_WORKERS) as ex:
            results = list(ex.map(lambda _: _soak_call(port), range(_SOAK_PAR)))
        par_bad = [(i, st) for i, (st, _) in enumerate(results) if st != 200]
        cur, peak = tracemalloc.get_traced_memory()
        checkpoints.append((cur, peak))
    finally:
        tracemalloc.stop()

    if bad or par_bad:
        raise RuntimeError(f"non-200 during soak: seq={bad[:5]} par={par_bad[:5]}")
    first = statistics.median(latencies[:100])
    last = statistics.median(latencies[-100:])
    drift = last / first if first > 0 else float("inf")
    cur0 = checkpoints[0][0]
    peak0 = checkpoints[0][1]
    cur_growth = checkpoints[-1][0] - cur0
    peak_growth = checkpoints[-1][1] - peak0
    if drift >= 2.0:
        raise RuntimeError(f"latency drift {drift:.2f}x (first-100 median {first:.4f}s, "
                           f"last-100 {last:.4f}s)")
    if cur_growth > _SOAK_MEM_SLACK or peak_growth > _SOAK_MEM_SLACK:
        raise RuntimeError(f"memory growth {cur_growth / 1e6:.1f}MB current / "
                           f"{peak_growth / 1e6:.1f}MB peak over soak")
    return {"ok": True, "drift": round(drift, 3), "seq_median": round(first, 4),
            "last_median": round(last, 4), "cur_growth_mb": round(cur_growth / 1e6, 2),
            "peak_growth_mb": round(peak_growth / 1e6, 2),
            "seq_lat_max": round(max(latencies), 3),
            "par_median": round(statistics.median([dt for _, dt in results]), 3)}


# --- mcp_stdio: the MCP server over a real stdio pipe --------------------------------------
# The mcp SDK's stdio transport is NEWLINE-delimited JSON (mcp.server.stdio.stdin_reader:
# `async for line in stdin` -> JSONRPCMessage.model_validate_json). One server process runs
# the whole battery: initialize handshake, a warmup tool call (first-call cost ~38s), then
# every hostile frame, then EOF. stdin stays OPEN until all responses are in — closing it
# early makes the SDK's shutdown cancel in-flight responses (measured).
_MCP_HS_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "fuzz-harness", "version": "0"}}}

# MEASURED (slice 17): if a tool call triggers a heavy module import (spacy/thinc/
# numpy chain, or even plain numpy) WHILE RUNNING ON THE EVENT LOOP — the mcp SDK
# executes sync tools inline on the loop — the response is not delivered until stdin
# closes, and under CPU saturation the import alone can take minutes. Pre-importing
# the tool backends and doing one warm engine call at PROCESS BOOT (before anyio
# starts) keeps every tool call fast and responsive. This is a third-party SDK quirk,
# not an untell defect; the preamble is the harness-side workaround.
_MCP_PREAMBLE = (
    "from untell.scripts.score import score_text; "
    "score_text('warmup', tier='lite', threshold=0.3); "
    "from untell.scripts.tells import score_tells; score_tells('warmup', include_matches=True); "
    "from untell.scripts.sentences import score_sentences; "
    "score_sentences('warmup text here', tier='lite'); "
    "from untell.mcp_server import main; raise SystemExit(main())"
)


def _mcp_jline(msg: dict) -> bytes:
    return (json.dumps(msg, ensure_ascii=True).encode("utf-8", "replace") + b"\n")


def _mcp_tool_call(tid: int, name: str, args) -> bytes:
    return _mcp_jline({"jsonrpc": "2.0", "id": tid, "method": "tools/call",
                       "params": {"name": name, "arguments": args}})


def build_mcp_frames(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    frames = []
    hostile = [
        ("score_text_int", _mcp_tool_call(0, "score", {"text": 123, "tier": "lite"}), True),
        ("score_text_list", _mcp_tool_call(0, "score", {"text": ["a", "b"], "tier": "lite"}), True),
        # Lone-surrogate escapes are INVALID JSON to pydantic-core's jiter parser; the
        # server refuses with an error notification and no response (measured) — so this
        # is a garbage frame, not a tool call that must answer.
        ("score_text_surrogate", _mcp_tool_call(0, "score", {"text": "a \ud800 b", "tier": "lite"}), False),
        ("score_tier_bogus", _mcp_tool_call(0, "score", {"text": "hello", "tier": "bogus"}), True),
        ("score_threshold_1e309", _mcp_tool_call(0, "score", {"text": "hello", "threshold": 1e309,
                                                              "tier": "lite"}), True),
        ("score_threshold_inf", _mcp_tool_call(0, "score", {"text": "hello",
                                                            "threshold": float("inf"),
                                                            "tier": "lite"}), True),
        ("score_missing_text", _mcp_tool_call(0, "score", {"tier": "lite"}), True),
        ("score_no_args", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "tools/call",
                                      "params": {"name": "score", "arguments": None}}), True),
        ("score_args_as_string", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "tools/call",
                                             "params": {"name": "score", "arguments": "x"}}), True),
        ("unknown_tool", _mcp_tool_call(0, "nope", {}), True),
        ("huge_text_50k", _mcp_tool_call(0, "score", {"text": "x" * 50_000, "tier": "lite"}), True),
        ("sentences_top_huge", _mcp_tool_call(0, "sentences", {"text": "hello world",
                                                               "top": 10 ** 9}), True),
        ("verify_commercial_no_args", _mcp_tool_call(0, "verify_commercial", {}), True),
        ("compare_tier_bogus", _mcp_tool_call(0, "compare", {"tier": "bogus"}), True),
        ("ceiling_n_huge", _mcp_tool_call(0, "ceiling", {"n": 10 ** 6}), True),
        ("scrub_surrogate", _mcp_tool_call(0, "scrub", {"text": "\ud800\x00tail"}), True),
        ("binary_line", b"\x00\x01\xff\xfe\x80\n", False),
        ("nul_in_line", b'{"jsonrpc":"2.0","id":0,"method":"ping"}\x00\n', False),
        ("truncated_json", b'{"jsonrpc":"2.0","id":0,"method":"pi', False),
        ("garbage_line", b"GARBAGE\n", False),
        ("deep_nesting", b'{"a":' * 1000 + b"1" + b"}" * 1000 + b"\n", False),
        ("cl_framed_garbage", b'Content-Length: 12\r\n\r\n{"bogus"xxx\n', False),
        ("huge_line_5MB", b"x" * 5_000_000 + b"\n", False),
        ("re_init", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                           "clientInfo": {"name": "fuzz", "version": "0"}}}), True),
        ("init_garbage_params", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                            "params": "garbage"}), True),
        ("id_as_string", _mcp_jline({"jsonrpc": "2.0", "id": "s", "method": "tools/call",
                                     "params": {"name": "tells", "arguments": {"text": "x"}}}),
         True, "s"),
        ("no_params", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "tools/call"}), True),
        ("unimplemented_method", _mcp_jline({"jsonrpc": "2.0", "id": 0,
                                             "method": "resources/list"}), True),
        ("ping_with_params", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "ping",
                                         "params": {"x": 1}}), True),
        ("tools_list_with_params", _mcp_jline({"jsonrpc": "2.0", "id": 0, "method": "tools/list",
                                               "params": {"x": 1}}), True),
    ]

    for entry in hostile:
        name, payload, expect = entry[0], entry[1], entry[2]
        resp_id = entry[3] if len(entry) > 3 else None
        frames.append({"kind": "frame", "name": name, "expect_resp": expect,
                       "resp_id": resp_id,
                       "b64": base64.b64encode(payload).decode()})
    # seeded extra garbage frames
    for i in range(max(0, n - len(hostile))):
        r = rng.random()
        if r < 0.4:
            payload = bytes(rng.randrange(256) for _ in range(rng.randint(1, 80))) + b"\n"
            expect = False
        elif r < 0.7:
            payload = _mcp_tool_call(0, rng.choice(["score", "tells", "nope"]),
                                     {"text": rand_str(rng, 200), "tier": "lite"})
            expect = True
        else:
            payload = rand_str(rng, 300).encode("utf-8", "replace") + b"\n"
            expect = False
        frames.append({"kind": "frame", "name": f"rand_{i}", "expect_resp": expect,
                       "b64": base64.b64encode(payload).decode()})
    return frames


def run_mcp_stdio_surface(frames: list[dict], timeout: float, out_f) -> list[dict]:
    """One MCP server process; every frame must draw a response, never a traceback."""
    findings = []
    # Boot the server through a preamble that pre-imports the tool backends and warms
    # the engine once, before anyio starts (see _MCP_PREAMBLE above).
    cmd = [PY, "-c", _MCP_PREAMBLE]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=ENV, cwd=REPO)
    lines: list[str] = []

    def _reader():
        for line in proc.stdout:
            lines.append(line.decode("utf-8", "replace"))

    threading.Thread(target=_reader, daemon=True).start()

    def _wait_resp(tid: int, deadline: float) -> str | None:
        t_end = time.time() + deadline
        while time.time() < t_end:
            for line in lines:
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                if msg.get("id") == tid:
                    return line
            if proc.poll() is not None:
                return None
            time.sleep(0.2)
        return None

    def _send(payload: bytes) -> None:
        proc.stdin.write(payload)
        proc.stdin.flush()

    def _finding(sev: str, name: str, msg: str) -> dict:
        f = {"surface": "mcp_stdio", "severity": sev, "status": "exception",
             "exc": msg, "case": {"name": name}}
        findings.append(f)
        out_f.write(json.dumps(f, ensure_ascii=True, default=str) + "\n")
        out_f.flush()
        return f

    try:
        _send(_mcp_jline(_MCP_HS_INIT))
        if _wait_resp(1, 300) is None:
            _finding("DEFECT", "handshake",
                     "no initialize response" + (f"; process exited {proc.poll()}"
                                                 if proc.poll() is not None else ""))
            proc.kill()
            return findings
        _send(_mcp_jline({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        # Warmup uses `tells` (regex-only, no heavy imports): the score tool's FIRST
        # call imports the spacy->thinc->numpy chain, which under CPU saturation can
        # take minutes — measured repeatedly. `tells` proves the protocol and tool
        # machinery in well under a second.
        _send(_mcp_tool_call(3, "tells", {"text": "warmup"}))
        if _wait_resp(3, 30) is None:
            _finding("DEFECT", "warmup",
                     "warmup tells call drew no response"
                     + (f"; process exited {proc.poll()}" if proc.poll() is not None else ""))
            proc.kill()
            return findings
        for i, case in enumerate(frames):
            payload = base64.b64decode(case["b64"])
            # assign a fresh id so responses are attributable (unless the frame
            # deliberately uses a non-numeric id, which the SDK echoes back)
            if case.get("resp_id") is None:
                payload = re.sub(rb'"id"\s*:\s*0', b'"id": %d' % (1000 + i), payload, count=1)
            _send(payload)
            print(f"  [mcp_stdio] frame {i + 1}/{len(frames)} {case['name']}", flush=True)
            if not case.get("expect_resp", True):
                # A garbage/truncated frame cannot draw a response; the contract is that
                # the server survives it (no traceback, process alive).
                time.sleep(3)
                if proc.poll() is not None:
                    err = proc.stderr.read().decode("utf-8", "replace")
                    _finding("DEFECT", case["name"],
                             f"server died (exit {proc.poll()}) on garbage frame; "
                             f"stderr: {err[-400:]!r}")
                continue
            # Fixed generous budget: the first score-family call imports the
            # spacy->thinc->numpy chain, which under CPU saturation can take minutes.
            want_id = case["resp_id"] if case.get("resp_id") is not None else 1000 + i
            resp = _wait_resp(want_id, 300)
            if resp is None:
                if proc.poll() is not None:
                    err = proc.stderr.read().decode("utf-8", "replace")
                    _finding("DEFECT", case["name"],
                             f"server died (exit {proc.poll()}) waiting for response; "
                             f"stderr: {err[-200:]!r}")
                else:
                    _finding("GAP", case["name"],
                             "no response within deadline; server alive (first-call "
                             "spacy/numpy import under CPU saturation can exceed the "
                             "deadline — measured, not a crash)")
            elif "Traceback" in resp:
                _finding("DEFECT", case["name"],
                         f"traceback in server output: {resp[:200]!r}")
            # else: a response (result or error) arrived — the contract.
        _send(b"")
        proc.stdin.close()
        try:
            proc.wait(timeout=min(timeout, 60))
        except subprocess.TimeoutExpired:
            _finding("GAP", "eof", "server did not exit within 60s of stdin EOF")
            proc.kill()
        err = proc.stderr.read().decode("utf-8", "replace")
        if "Traceback" in err:
            _finding("DEFECT", "stderr", f"traceback on server stderr: {err[-300:]!r}")
        if proc.returncode not in (0, 1):
            _finding("GAP", "exit", f"server exited {proc.returncode}")
    except Exception as exc:  # noqa: BLE001 — harness plumbing failure
        extra = ""
        try:
            err = proc.stderr.read().decode("utf-8", "replace")
            if err:
                extra = f"; server stderr: {err[-400:]!r}"
        except Exception:
            pass
        _finding("DEFECT", "harness", f"{type(exc).__name__}: {exc}{extra}")
    return findings


_SURFACES = {
    "split": _run_split,
    "layout": _run_layout,
    "detectors": _run_detectors,
    "api": _run_api,
    "mcp": _run_mcp,
    "rest": _run_rest,
    "preserve": _run_preserve,
    "cli": _run_cli,
    "rest_socket": _run_rest_socket,
    "mcp_stdio": _run_mcp,  # handled by a dedicated runner in main(); placeholder kept
    "soak": _run_soak,
}

# Surfaces whose cases share one live in-process REST server (started before the
# case loop, stopped after).
_SURFACE_SERVER = frozenset({"rest_socket", "soak"})


def build_cases(surface: str, n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    if surface == "split":
        for _ in range(n):
            r = rng.random()
            if r < 0.5:
                text = rand_str(rng, 3000)
            elif r < 0.8:
                text = " ".join(_SENTENCEY.split()) + " " + rand_str(rng, 200)
            elif r < 0.95:
                text = rand_str(rng, 30)
            else:
                text = rand_str(rng, 60000)
            cases.append({"surface": surface, "text": text})
    elif surface == "layout":
        for _ in range(n):
            cases.append({"surface": surface, "text": rand_layout(rng)})
    elif surface == "detectors":
        for _ in range(n):
            cases.append({"surface": surface, "text": rand_str(rng, 1500),
                          "x": rng.choice([0.5, -1.0, 2.0, float("nan"), float("inf"),
                                           "0.5", None, True])})
    elif surface == "api":
        kinds = ["score", "tells", "sentences", "humanness", "loop"]
        for i in range(n):
            r = rng.random()
            if r < 0.6:
                spec = {"v": rand_str(rng, 1200)}
            elif r < 0.8:
                spec = {"b": base64.b64encode(rand_bytes(rng, 500)).decode("ascii")}
            elif r < 0.95:
                spec = {"t": rng.choice(["none", "int", "list", "dict", "bool"])}
            else:
                spec = {"v": rand_str(rng, 50000)}
            case = {"surface": surface, "kind": kinds[i % len(kinds)], "text": spec}
            # Robustness fuzz is about the TEXT and the type-malformed tier shapes,
            # not about which detector ensemble runs: force lite so no model loads
            # (each full-tier call costs ~10s of transformer warm-up). Type-malformed
            # tiers (list/int/NUL) still exercise the arg-validation path.
            if rng.random() < 0.3:
                case["tier"] = rng.choice(["lite", "bogus", "", "LITE", 5,
                                           ["lite"], "lite\x00"])
            if rng.random() < 0.2:
                case["threshold"] = rng.choice([0.3, 0.0, 1.0, -0.5, 2.0, float("nan"),
                                                float("inf"), "0.5", None])
            cases.append(case)
    elif surface == "mcp":
        kinds = [("threshold", "probability"), ("max_iters", "count"),
                 ("best_of", "count"), ("confirm", "count_or_zero"),
                 ("top", "top"), ("seed", "seed"), ("tier", "tier")]
        for _ in range(n):
            name, kind = kinds[rng.randrange(len(kinds))]
            r = rng.random()
            if r < 0.4:
                spec = {"v": rng.choice(["abc", "0.5", "2", "-1", "", "1e309", "inf",
                                         "nan", "0.5.5", "\ud800"])}
            elif r < 0.7:
                spec = {"t": rng.choice(["none", "int", "float", "nan", "inf",
                                         "bool", "list", "dict"])}
            else:
                spec = {"v": rng.choice([0.3, 50, -1, 0, 100, 2**64, 2**64 - 1, 1.5])}
            cases.append({"surface": surface, "kind": kind, "name": name, "arg": spec})
    elif surface == "rest":
        models = [("ScoreRequest", "ScoreRequest"), ("HumanizeRequest", "HumanizeRequest"),
                  ("SentencesRequest", "SentencesRequest"), ("TellsRequest", "TellsRequest"),
                  ("VerifyRequest", "VerifyRequest"), ("CeilingRequest", "CeilingRequest")]
        for _ in range(n):
            model_name, _ = models[rng.randrange(len(models))]
            payload = {"text": rand_str(rng, 500)}
            if model_name != "CeilingRequest":
                if rng.random() < 0.3:
                    payload["threshold"] = rng.choice([0.3, 50, -1, float("nan"),
                                                       float("inf"), "0.5"])
                if rng.random() < 0.2:
                    payload["tier"] = rng.choice(["lite", "bogus", "", 5, ["lite"]])
                if rng.random() < 0.2:
                    payload["nonsense_field"] = rand_str(rng, 20)
                if rng.random() < 0.1:
                    payload["text"] = rand_str(rng, 60000)
            else:
                payload = {"max_iters": rng.choice([5, 0, 10**6, float("inf"), "abc"]),
                           "n": rng.choice([3, 0, 10**7])}
            cases.append({"surface": surface, "model": model_name, "payload": payload})
    elif surface == "preserve":
        for _ in range(n):
            r = rng.random()
            if r < 0.6:
                cases.append({"surface": surface, "kind": "roundtrip",
                              "text": rand_str(rng, 1500)})
            elif r < 0.8:
                fake = {}
                for _ in range(rng.randint(1, 6)):
                    key = f"\u27e6HZ{rng.randint(0, 99999):04d}\u27e7"
                    fake[key] = rng.choice([rand_str(rng, 50), 42, None, b"x", ["a"], {"k": 1}])
                cases.append({"surface": surface, "kind": "adversarial",
                              "text": rand_str(rng, 400), "mapping": fake})
            else:
                cases.append({"surface": surface, "kind": "type",
                              "fn": rng.choice(["lock", "restore"]),
                              "arg": {"t": rng.choice(["none", "bytes", "int", "list"])}})
    elif surface == "cli":
        for _ in range(n):
            argv = rand_argv(rng)
            which = rng.choice(["untell", "score", "sentences", "scrub", "tells",
                                "preserve"])
            if which == "untell":
                # `untell` with bare text runs the full humanize loop (model loads,
                # tens of seconds). The loop itself is fuzzed on the `api` surface;
                # here the surface is ARG PARSING, so keep untell cases to flag/file
                # shapes that exit fast. `--demo`/bare-text are covered by the
                # subprocess one-shots with a long timeout.
                while argv and argv[0] not in ("--help", "-h", "--bogus", "-x",
                                               "--version", "--check", "--json",
                                               "--quiet", "--file", "--tier",
                                               "--threshold", "--seed"):
                    argv = rand_argv(rng)
            cases.append({"surface": surface, "argv": argv, "which": which})
    elif surface == "rest_socket":
        # Curated battery first, then seeded random byte mutations.
        for name, raw in _REST_RAW_CASES:
            cases.append({"surface": surface, "name": name, "raw": raw.decode("latin1")})
        for i in range(n):
            cases.append({"surface": surface, "name": f"mut_{i}",
                          "raw": _rand_raw(rng).decode("latin1")})
    elif surface == "mcp_stdio":
        # Frames are consumed by the dedicated runner (one MCP subprocess per battery).
        return build_mcp_frames(n, seed)
    elif surface == "soak":
        # The soak is a single case; 500 sequential + 50 parallel calls happen inside it.
        cases.append({"surface": surface})
    return cases


# --- execution -----------------------------------------------------------------------------------

def _capture_exc() -> tuple[str, str]:
    tb = traceback.format_exc()
    lines = tb.splitlines()
    head = lines[0] if lines else "?"
    site = [ln for ln in lines if "untell" in ln and "site-packages" not in ln]
    return head, "\n".join(site[:8])


def run_case(surface: str, case: dict, timeout: float) -> dict:
    result: dict = {"i": case.get("_i", 0), "status": "ok"}
    holder: dict = {}
    t0 = time.time()

    def _run():
        try:
            holder["r"] = _SURFACES[surface](case)
        except BaseException as exc:  # noqa: BLE001 — fuzz: capture everything
            head, site = _capture_exc()
            holder["r"] = {"exc": f"{type(exc).__name__}: {exc}",
                           "head": head, "site": site,
                           "exc_type": type(exc).__name__}

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout)
    elapsed = time.time() - t0
    if th.is_alive():
        result["status"] = "hang_thread"
        result["elapsed"] = round(elapsed, 2)
    else:
        result.update(holder.get("r") or {})
        result["elapsed"] = round(elapsed, 3)
        if result["status"] == "ok" and "exc" in result:
            result["status"] = "exception"
    for key, val in case.items():
        if key.startswith("_"):
            continue
        if key == "text" and isinstance(val, dict) and "v" in val:
            result["input_preview"] = val["v"][:120]
        elif key == "payload":
            result["payload_preview"] = json.dumps(val, ensure_ascii=True, default=str)[:120]
        else:
            result[key] = val
    return result


def classify(result: dict, surface: str) -> dict | None:
    status = result.get("status")
    exc = result.get("exc", "")
    if status == "exception":
        exc_type = result.get("exc_type", "?")
        # a clean TypeError naming the contract is the repo's documented fix shape
        if "TypeError" in exc_type and "must be str" in exc:
            return None
        sev = "DEFECT" if surface in ("split", "layout", "detectors", "preserve", "cli",
                                      "rest_socket", "soak") else "GAP"
        return {"severity": sev, "status": status, "exc": exc,
                "head": result.get("head"), "site": result.get("site"),
                "input_preview": result.get("input_preview") or result.get("payload_preview"),
                "case": {k: result[k] for k in ("text", "argv", "kind", "name", "arg",
                                                "tier", "threshold", "fn", "which",
                                                "model", "payload") if k in result}}
    if status == "hang_thread":
        return {"severity": "DEFECT", "status": status, "exc": "timeout",
                "elapsed": result.get("elapsed"),
                "input_preview": result.get("input_preview"),
                "case": {k: result[k] for k in ("text", "argv", "kind") if k in result}}
    return None


def write_finding(out_f, finding: dict, surface: str, case: dict) -> None:
    line = {"surface": surface, **finding,
            "case_spec": {k: v for k, v in case.items() if not k.startswith("_")}}
    out_f.write(json.dumps(line, ensure_ascii=True, default=str) + "\n")
    out_f.flush()


def run_surface(surface: str, n: int, timeout: float, out_f, quick: bool) -> list[dict]:
    seed = MASTER_SEED + hash(surface) % 1000
    cases = build_cases(surface, n, seed)
    findings = []
    if surface in _SURFACE_SERVER:
        _ensure_rest_server()
    try:
        for i, case in enumerate(cases):
            case["_i"] = i
            result = run_case(surface, case, timeout)
            f = classify(result, surface)
            if f:
                findings.append(f)
                write_finding(out_f, f, surface, case)
            if i % 50 == 0:
                print(f"  [{surface}] {i + 1}/{n}  findings={len(findings)}", flush=True)
    finally:
        if surface in _SURFACE_SERVER:
            _stop_rest_server()
    return findings


def cli_one_shot(surface: str, argv: list[str], which: str, timeout: float) -> dict:
    """True subprocess CLI invocation with NUL-sanitised argv."""
    module_for = {"untell": "untell.scripts.cli", "score": "untell.scripts.score",
                  "sentences": "untell.scripts.sentences", "scrub": "untell.scripts.scrub",
                  "tells": "untell.scripts.tells", "preserve": "untell.scripts.preserve"}
    clean = sanitise_argv(argv)
    sanitised = clean != argv
    cmd = [PY, "-m", module_for[which]] + clean
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, env=ENV, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              cwd=REPO, stdin=subprocess.DEVNULL)
        stderr = proc.stderr or ""
        tb = "Traceback (most recent call last)" in stderr
        return {"surface": f"cli:{which}:subprocess", "argv": clean,
                "sanitised_nul": sanitised, "status": "exception" if tb else "ok",
                "code": proc.returncode, "elapsed": round(time.time() - t0, 1),
                "stderr_tail": stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"surface": f"cli:{which}:subprocess", "argv": clean,
                "sanitised_nul": sanitised, "status": "hang",
                "elapsed": round(time.time() - t0, 1), "stderr_tail": ""}
    except Exception as exc:
        return {"surface": f"cli:{which}:subprocess", "argv": clean,
                "sanitised_nul": sanitised, "status": f"spawn_error:{type(exc).__name__}",
                "elapsed": round(time.time() - t0, 1), "stderr_tail": str(exc)[:200]}


def run_subprocess_cli(n: int, out_f) -> list[dict]:
    rng = random.Random(MASTER_SEED + 99)
    findings = []
    for i in range(n):
        which = rng.choice(["untell", "score", "sentences", "scrub", "tells"])
        argv = rand_argv(rng)
        if which in ("untell", "score", "sentences"):
            # The subprocess surface is SPAWN/ARGV robustness (NUL sanitisation,
            # surrogate argv, encoding) — not the scoring loop, which the `api`
            # surface covers. Force the fast lite path so a bare-text or --file
            # case does not spend minutes loading the full-tier ensemble (five
            # transformer models at `--tier full`, which is the CLI default);
            # arg-parsing bugs still surface identically.
            argv = ["--tier", "lite"] + argv
            timeout = 60
        else:
            timeout = 40
        r = cli_one_shot("cli", argv, which, timeout)
        if r["status"] in ("exception", "hang", "spawn_error") or r["sanitised_nul"]:
            findings.append(r)
            out_f.write(json.dumps({"surface": r["surface"], **r},
                                   ensure_ascii=True, default=str) + "\n")
            out_f.flush()
        if i % 20 == 0:
            print(f"  [cli subprocess] {i + 1}/{n}", flush=True)
    return findings


# --- main ----------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="untell robustness fuzz harness")
    ap.add_argument("--surface", choices=sorted(_SURFACES), default=None)
    ap.add_argument("--quick", action="store_true", help="small case count per surface")
    ap.add_argument("--n", type=int, default=0, help="cases per surface (0 = default)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--timeout", type=float, default=0.0)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out_f = open(args.out, "w", encoding="utf-8")
    counts = {s: (30 if args.quick else 120) for s in _SURFACES}
    timeouts = {s: (20 if args.quick else 40) for s in _SURFACES}
    # The soak is ONE case (500 sequential + 50 parallel calls happen inside it) and
    # needs a long per-case budget; the transport surfaces need room for the slow box.
    counts["soak"] = 1
    timeouts["soak"] = 900
    counts["rest_socket"] = 30 if args.quick else 60
    timeouts["rest_socket"] = 60 if args.quick else 90
    # mcp_stdio runs one process with a ~38s first-call warmup; the per-surface
    # timeout must cover it or every quick run reports a false warmup DEFECT.
    counts["mcp_stdio"] = 30 if args.quick else 60
    timeouts["mcp_stdio"] = 90 if args.quick else 240
    if args.n:
        counts = {s: args.n for s in _SURFACES}
        counts["soak"] = 1
    if args.timeout:
        timeouts = {s: args.timeout for s in _SURFACES}
        timeouts["soak"] = max(args.timeout, 900)

    surfaces = [args.surface] if args.surface else sorted(_SURFACES)
    all_findings = []
    t_start = time.time()
    for surface in surfaces:
        print(f"== surface: {surface} ==", flush=True)
        if surface == "mcp_stdio":
            # One MCP subprocess runs the whole battery (handshake + warmup + frames);
            # the generic per-case loop would spawn a process per frame.
            frames = build_mcp_frames(counts[surface], MASTER_SEED + hash(surface) % 1000)
            findings = run_mcp_stdio_surface(frames, timeouts[surface], out_f)
        else:
            findings = run_surface(surface, counts[surface], timeouts[surface], out_f,
                                   args.quick)
        all_findings += findings
        print(f"   {surface}: {len(findings)} findings", flush=True)

    if args.surface not in ("cli", "mcp_stdio", "soak"):
        print("== cli subprocess one-shots ==", flush=True)
        sub_findings = run_subprocess_cli(15 if args.quick else 40, out_f)
        for f in sub_findings:
            if f["status"] in ("exception", "hang", "spawn_error"):
                print(f"   {f['surface']} {f['argv'][:3]!r} -> {f['status']}", flush=True)
            elif f["sanitised_nul"]:
                # NUL was stripped and the CLI still answered — the point of the
                # sanitisation. Informational, kept in the JSONL only.
                print(f"   {f['surface']} NUL-sanitised argv handled cleanly", flush=True)

    out_f.close()

    print("\n" + "=" * 78)
    print(f"UNTELL FUZZ HARNESS — {len(all_findings)} findings "
          f"({time.time() - t_start:.0f}s) -> {args.out}")
    print("=" * 78)
    for i, f in enumerate(all_findings, start=1):
        surface = f.get("surface") or f.get("case", {}).get("surface", "?")
        print(f"\n{i}. [{f['severity']}] {f['status']} on {surface}")
        if f.get("input_preview"):
            print(f"   input : {f['input_preview']!r}")
        if f.get("exc"):
            print(f"   exc   : {f['exc'][:200]}")
        if f.get("site"):
            print(f"   site  : {f['site'][:300]}")
        if f.get("elapsed"):
            print(f"   time  : {f['elapsed']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
