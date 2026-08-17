"""Server soak + transport-level robustness regression tests (slice 17).

Three things are pinned here, all against a REAL in-process uvicorn server talked
to over actual TCP with http.client (TestClient never touches a socket, so it
cannot see transport-level behaviour):

1. SOAK (marked ``soak`` — deselect with ``pytest -m "not soak"``): 500 sequential
   + 50 parallel POST /score calls. Assertions:
     * every call answers HTTP 200 (no 5xx; a malformed-but-well-formed request
       must never 500)
     * median latency of the last 100 calls < 2x the first 100 (no drift)
     * tracemalloc current/peak growth over the soak < 8MB (plateau, no leak)
2. Malformed-HTTP transport contract: bad methods, bad headers, chunked-encoding
   abuse and request-smuggling shapes all draw a 4xx (400/405/422) and never
   wedge the server — a follow-up /health probe must still answer.
3. Incomplete requests (a partial request line, a chunk body that never arrives)
   leave the server healthily WAITING for more input — not crashed.

Robustness note: this machine is often 100% CPU-saturated (sibling audit slices),
so every probe here is retried and every timeout is generous — a single slow
response is never mistaken for a wedge. The server runs on uvicorn 0.49's default
Windows event loop (Proactor), the same configuration the shipped `untell-server`
uses.
"""
from __future__ import annotations

import http.client
import json
import statistics
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("fastapi")

def _set_server_env(monkeypatch) -> None:
    """The soak makes 550 calls in ~a minute; the shipped rate limit is 60/min —
    the documented disable knob (UNTELL_RATE_LIMIT env var set to 0) is used so the
    soak measures latency/memory, not throttling (rate limiting has its own tests).
    Auth stays off unless the operator exported UNTELL_API_KEY; the soak clears it
    so requests are open like the documented quick start.
    """
    monkeypatch.setenv("UNTELL_RATE_LIMIT", "0")
    monkeypatch.delenv("UNTELL_API_KEY", raising=False)


def start_server(monkeypatch):
    """Boot one in-process uvicorn server on a random port; return (port, stop)."""
    import uvicorn

    from untell.api_server import app

    _set_server_env(monkeypatch)
    # uvicorn 0.49 runs ProactorEventLoop on Windows by default (the shipped
    # `untell-server` configuration too) — nothing to force; the retried probes and
    # generous timeouts below absorb the CPU-saturated box, not the loop.
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error",
                            lifespan="off")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(400):
        if server.started:
            break
        time.sleep(0.02)
    assert server.started, "in-process uvicorn server failed to start"
    port = server.servers[0].sockets[0].getsockname()[1]

    def stop():
        server.should_exit = True
        th.join(15)

    return port, stop


_SOAK_TEXT = ("The committee approved the proposal yesterday, and moreover the framework "
              "showcases remarkable results across several benchmarks. Dr. Smith and Prof. "
              "Jones agreed on the analysis, noting that the mean was 3.5 and variance low. "
              "It works... mostly. Meetings are common at 9:30 p.m. and the deadline is "
              "Friday, June 14th, 2026, at 5 p.m. precisely.") * 3
_SOAK_BODY = json.dumps({"text": _SOAK_TEXT, "tier": "lite"}).encode()


def soak_call(port: int, timeout: float = 120.0) -> tuple[int, float]:
    t0 = time.time()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/score", body=_SOAK_BODY,
                 headers={"content-type": "application/json"})
    r = conn.getresponse()
    r.read()
    status = r.status
    conn.close()
    return status, time.time() - t0


@pytest.mark.soak
class TestServerSoak:
    """500 sequential + 50 parallel REST calls: no 5xx, no latency drift, no leak."""

    def test_soak_no_5xx_plateau_latency(self, monkeypatch):
        port, stop = start_server(monkeypatch)
        try:
            # Warm up: the first call in a fresh process costs ~27-38s (imports +
            # detector resolution); it is not part of the measured window.
            st, _ = soak_call(port)
            assert st == 200, f"warmup answered {st}"
            st, _ = soak_call(port)
            assert st == 200, f"second warmup answered {st}"

            tracemalloc.start()
            latencies: list[float] = []
            checkpoints: list[tuple[int, int]] = []
            try:
                for batch in range(5):
                    for _ in range(100):
                        st, dt = soak_call(port)
                        assert st == 200, f"sequential call {batch * 100 + _} answered {st}"
                        latencies.append(dt)
                    cur, peak = tracemalloc.get_traced_memory()
                    checkpoints.append((cur, peak))
                with ThreadPoolExecutor(max_workers=16) as ex:
                    results = list(ex.map(lambda _: soak_call(port), range(50)))
                for i, (st, _dt) in enumerate(results):
                    assert st == 200, f"parallel call {i} answered {st}"
                cur, peak = tracemalloc.get_traced_memory()
                checkpoints.append((cur, peak))
            finally:
                tracemalloc.stop()

            # latency drift < 2x between the first and last 100 sequential calls
            first = statistics.median(latencies[:100])
            last = statistics.median(latencies[-100:])
            drift = last / first if first > 0 else float("inf")
            assert drift < 2.0, (
                f"latency drift {drift:.2f}x: first-100 median {first:.4f}s, "
                f"last-100 median {last:.4f}s"
            )

            # memory plateau: current and peak growth over the soak stay under 8MB
            cur_growth = checkpoints[-1][0] - checkpoints[0][0]
            peak_growth = checkpoints[-1][1] - checkpoints[0][1]
            assert cur_growth < 8 * 1024 * 1024, (
                f"tracemalloc current grew {cur_growth / 1e6:.1f}MB over the soak"
            )
            assert peak_growth < 8 * 1024 * 1024, (
                f"tracemalloc peak grew {peak_growth / 1e6:.1f}MB over the soak"
            )
        finally:
            stop()


# --- transport-level malformed-HTTP contract ---------------------------------------------

def send_raw(port: int, raw: bytes, timeout: float = 6.0) -> int | None:
    """Send raw bytes on a fresh connection; return the HTTP status or None if no
    response arrived (the server is waiting for more input).

    One retry on a total no-response: on this machine (16 cores at 100% from sibling
    slices) a brand-new server's first accept can take longer than the socket timeout
    without the server being broken — the retry separates that race from a real wedge.
    """
    import socket

    for _attempt in range(2):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
            conn.connect()
            conn.sock.sendall(raw)
            conn.sock.settimeout(timeout)
            try:
                resp = http.client.HTTPResponse(conn.sock)
                resp.begin()
                resp.read()
                return resp.status
            except socket.timeout:
                return None
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except (ConnectionResetError, BrokenPipeError, OSError):
            time.sleep(0.5)
    return None


def probe_health(port: int, attempts: int = 3) -> bool:
    """/health on a fresh connection, retried: this box is often 100% CPU-saturated,
    so a single slow probe is not evidence of a wedge (measured repeatedly)."""
    for _ in range(attempts):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
            conn.request("GET", "/health")
            r = conn.getresponse()
            ok = r.status == 200
            conn.close()
            if ok:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


class TestMalformedHttpStays4xx:
    """Transport-level fuzz regression pins: malformed HTTP must draw 4xx, never 5xx,
    and never wedge the server (found by scripts/fuzz_harness.py --surface rest_socket)."""

    @pytest.mark.parametrize(
        "raw",
        [
            b"BREW /score HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}",   # unknown method
            b"\x00GET /score HTTP/1.1\r\nHost: x\r\n\r\n",                        # NUL method
            b"GET\r\n /score HTTP/1.1\r\nHost: x\r\n\r\n",                        # CRLF in method
            b" /score HTTP/1.1\r\nHost: x\r\n\r\n",                               # no method
            b"GET /score HTTP/9.9\r\nHost: x\r\n\r\n",                            # bad version
            b"GET /score HTTP/1.1\r\nHost x\r\n\r\n",                             # no colon
            b"GET /score HTTP/1.1\r\nBad Header: x\r\n\r\n",                      # space in name
            b"GET /score HTTP/1.1\r\nX-Foo: a\x00b\r\n\r\n",                      # NUL in value
            b"POST /score HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\n"           # dup CL
            b"Content-Length: 6\r\n\r\nhello!",
            b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n"  # bad chunk size
            b"\r\nzzz\r\nhello",
            b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n"  # negative size
            b"\r\n-5\r\nhello",
            b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: gzip, chunked\r\n"
            b"\r\n0\r\n\r\n",                                                     # non-chunked TE
            b"   GET /score HTTP/1.1\r\nHost: x\r\n\r\n",                         # leading spaces
            b"\xff\xfe\x00\x01GARBAGE\r\n\r\n",                                   # binary garbage
            b"\r\nGET /score HTTP/1.1\r\nHost: x\r\n\r\n",                        # stray CRLF
        ],
    )
    def test_malformed_request_draws_4xx_not_5xx(self, monkeypatch, raw):
        port, stop = start_server(monkeypatch)
        try:
            status = send_raw(port, raw)
            assert status is not None, f"no response for {raw[:40]!r}"
            assert 400 <= status < 500, (
                f"{raw[:40]!r} answered HTTP {status}, expected 4xx"
            )
            assert probe_health(port), "server wedged after malformed request"
        finally:
            stop()

    @pytest.mark.parametrize(
        "raw",
        [
            b"GET /sco",                                                          # partial request line
            b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n"  # chunk body never ends
            b"\r\nFFFFFFFFFFFFFFFF\r\nhello",
            b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n"
            b"\r\n5\r\nhello\r\n",                                                # no final zero
        ],
    )
    def test_incomplete_request_waits_and_server_stays_alive(self, monkeypatch, raw):
        port, stop = start_server(monkeypatch)
        try:
            status = send_raw(port, raw, timeout=4.0)
            assert status is None, f"{raw[:40]!r} answered HTTP {status}, expected wait"
            assert probe_health(port), "server wedged by incomplete request"
        finally:
            stop()

    def test_huge_header_name_draws_400_and_server_survives(self, monkeypatch):
        port, stop = start_server(monkeypatch)
        try:
            raw = b"GET /score HTTP/1.1\r\n" + b"A" * 90000 + b": x\r\n\r\n"
            status = send_raw(port, raw, timeout=10.0)
            assert status is not None, "no response for oversized header name"
            assert 400 <= status < 500, f"huge header name answered HTTP {status}"
            assert probe_health(port), "server wedged by oversized header name"
        finally:
            stop()

    def test_request_smuggling_shapes_draw_4xx(self, monkeypatch):
        port, stop = start_server(monkeypatch)
        try:
            for raw in [
                b"POST /score HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n",                    # CL + TE
                b"POST /score HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n"
                b"Content-Length: 4\r\n\r\n0\r\n\r\n",                             # TE + CL
                b"GET /score HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}",  # GET with body
            ]:
                status = send_raw(port, raw)
                assert status is not None, f"no response for {raw[:40]!r}"
                assert 400 <= status < 500, f"{raw[:40]!r} answered HTTP {status}"
            assert probe_health(port), "server wedged after smuggling shapes"
        finally:
            stop()
