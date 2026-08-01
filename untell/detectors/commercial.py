"""Commercial AI-detector adapters (the *real* checkers the product must beat).

Each wraps a paid HTTP API and is **key-gated**: ``available()`` is true only when ``requests`` is
installed (the ``[commercial]`` extra) and the service's API key env var(s) are set. With no keys
the detectors are simply absent from the ensemble, so nothing here runs — or costs money — unless
you configure it. Endpoints/field paths below are from each provider's current public docs.

Tier ``commercial`` sits above ``heavy``: ``load_detectors("commercial")`` returns every available
lite/full/heavy detector *plus* every configured commercial one, and the loop must drive the
``max`` across all of them under threshold — i.e. pass **every** checker you've wired up.

Env vars:
  ORIGINALITY_API_KEY · WINSTON_API_KEY · GPTZERO_API_KEY · SAPLING_API_KEY · ZEROGPT_API_KEY
  COPYLEAKS_EMAIL + COPYLEAKS_API_KEY
"""

from __future__ import annotations

import hashlib
import logging
import os
import time

from untell._retry import _RETRYABLE_HTTP, retry

from .base import clamp01

logger = logging.getLogger(__name__)

_SHAPE_WARNED: set[str] = set()


def _unusable(name: str, data, exc: Exception | None = None) -> None:
    """Say once that a paid API's response could not be read.

    Returning ``None`` on an unreadable response is correct — a fabricated score is worse than no
    score — but doing it *silently* means a provider changing its response shape shows up as the
    detector quietly vanishing from the ensemble, on a service the user is being billed for. Every
    other component in this package that disables itself says so once; these did not.
    """
    if name in _SHAPE_WARNED:
        return
    _SHAPE_WARNED.add(name)
    keys = sorted(data)[:8] if isinstance(data, dict) else type(data).__name__
    logger.warning(
        "%s returned a response this adapter cannot read, and was EXCLUDED from the ensemble "
        "(%s%s). Top-level keys: %s. The API may have changed its response shape.",
        name,
        type(exc).__name__ if exc else "missing score field",
        f": {str(exc)[:100]}" if exc else "",
        keys,
    )


def _post_json(url: str, headers: dict, body: dict, timeout: float = 45.0) -> dict:
    """POST JSON and return parsed JSON. Isolated so tests can monkeypatch it (no network).
    Raises on HTTP/network errors; caller handles.
    """
    import requests

    def _once():
        resp = requests.post(
            url=url,
            headers={"Content-Type": "application/json", **headers},
            json=body,
            timeout=timeout,
        )
        # raise_for_status INSIDE the retried callable. It used to sit after `retry(...)` returned,
        # so only connection-level exceptions were ever retried — a rate-limit or 503 comes back as
        # a perfectly successful `requests.post` with a 429/503 status, and was raised once, on the
        # last attempt, having never been retried. That is the exact case this module exists for,
        # and `_RETRYABLE_HTTP` was dead code confirming nobody had wired it up.
        if resp.status_code in _RETRYABLE_HTTP:
            raise RuntimeError(f"retryable HTTP {resp.status_code} from {url}")
        resp.raise_for_status()
        return resp.json()

    return retry(_once, max_attempts=3)


def _has(*env_vars: str) -> bool:
    """True when ``requests`` is importable and all named env vars are set and non-empty."""
    try:
        import requests  # noqa: F401
    except Exception:
        return False
    return all(os.environ.get(v) for v in env_vars)


class OriginalityDetector:
    name = "originality"
    tier = "commercial"

    def available(self) -> bool:
        return _has("ORIGINALITY_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            data = _post_json(
                "https://api.originality.ai/api/v1/scan/ai",
                {"X-OAI-API-KEY": os.environ["ORIGINALITY_API_KEY"], "Accept": "application/json"},
                {"content": text, "aiModelVersion": "1"},
            )
            data_seen = data
            return clamp01(float(data["score"]["ai"]))
        except (KeyError, TypeError, ValueError) as exc:
            _unusable(self.name, locals().get("data_seen"), exc)
            return None


class WinstonDetector:
    name = "winston"
    tier = "commercial"

    def available(self) -> bool:
        return _has("WINSTON_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            data = _post_json(
                "https://api.gowinston.ai/v2/ai-content-detection",
                {"Authorization": f"Bearer {os.environ['WINSTON_API_KEY']}"},
                {"text": text, "sentences": False, "language": "auto"},
            )
            data_seen = data
            return clamp01((100.0 - float(data["score"])) / 100.0)
        except (KeyError, TypeError, ValueError) as exc:
            _unusable(self.name, locals().get("data_seen"), exc)
            return None


class GPTZeroDetector:
    name = "gptzero"
    tier = "commercial"

    def available(self) -> bool:
        return _has("GPTZERO_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            data = _post_json(
                "https://api.gptzero.me/v2/predict/text",
                {"x-api-key": os.environ["GPTZERO_API_KEY"], "Accept": "application/json"},
                {"document": text},
            )
            docs = data.get("documents", [])
            if not docs:
                return None
            doc = docs[0]
            ai = doc.get("class_probabilities", {}).get("ai")
            if ai is None:
                # NO 0.5 DEFAULT. If neither score field is present the API told us nothing, and a
                # fabricated mid-score is worse than no score: it enters the ensemble, drives max(),
                # and suppresses the all-failed guard the rest of the code relies on. Return None so
                # this detector is EXCLUDED — the same rule already applied to mage/hc3/perplexity.
                ai = doc.get("completely_generated_prob")
            if ai is None:
                _unusable(self.name, doc)
                return None
            return clamp01(float(ai))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            _unusable(self.name, locals().get("data"), exc)
            return None


class SaplingDetector:
    name = "sapling"
    tier = "commercial"

    def available(self) -> bool:
        return _has("SAPLING_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            data = _post_json(
                "https://api.sapling.ai/api/v1/aidetect",
                {},
                {"key": os.environ["SAPLING_API_KEY"], "text": text, "sent_scores": False},
            )
            data_seen = data
            return clamp01(float(data["score"]))
        except (KeyError, TypeError, ValueError) as exc:
            _unusable(self.name, locals().get("data_seen"), exc)
            return None


class ZeroGPTDetector:
    name = "zerogpt"
    tier = "commercial"

    def available(self) -> bool:
        return _has("ZEROGPT_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            data = _post_json(
                "https://api.zerogpt.com/api/v1/detectText",
                {"Authorization": f"Bearer {os.environ['ZEROGPT_API_KEY']}"},
                {"input_text": text},
            )
            # ZeroGPT response has nested structure
            score_data = data.get("data", {})
            if isinstance(score_data, dict):
                # No 50 default: an absent field means the API returned no verdict, and 50 would
                # become a fabricated 0.5 in the ensemble (see GPTZeroDetector above).
                raw = score_data.get("is_gpt_generated")
                if raw is None:
                    _unusable(self.name, score_data)
                    return None
                return clamp01(float(raw) / 100.0)
            _unusable(self.name, data)
            return None
        except (TypeError, ValueError) as exc:
            _unusable(self.name, locals().get("data"), exc)
            return None


# Copyleaks needs a 2-step auth: login (email+key) -> 48h Bearer token -> detect.
_CL_TOKEN: dict = {"token": None, "exp": 0.0}


def _copyleaks_token() -> str:
    if _CL_TOKEN["token"] and time.time() < _CL_TOKEN["exp"]:
        return _CL_TOKEN["token"]
    data = _post_json(
        "https://id.copyleaks.com/v3/account/login/api",
        {},
        {"email": os.environ["COPYLEAKS_EMAIL"], "key": os.environ["COPYLEAKS_API_KEY"]},
    )
    _CL_TOKEN["token"] = data["access_token"]
    _CL_TOKEN["exp"] = time.time() + 40 * 3600  # token lives 48h; refresh well inside that
    return _CL_TOKEN["token"]


class CopyleaksDetector:
    name = "copyleaks"
    tier = "commercial"

    def __init__(self, sandbox: bool = False):
        # sandbox=True returns free *mock* results (still needs login) — for testing the pipeline,
        # not real detection. The score is not meaningful in sandbox mode.
        self.sandbox = sandbox

    def available(self) -> bool:
        return _has("COPYLEAKS_EMAIL", "COPYLEAKS_API_KEY")

    def score(self, text: str) -> float | None:
        if not self.available() or not text.strip():
            return None
        try:
            token = _copyleaks_token()
            scan_id = "hz" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]
            data = _post_json(
                f"https://api.copyleaks.com/v2/writer-detector/{scan_id}/check",
                {"Authorization": f"Bearer {token}"},
                {"text": text, "sandbox": self.sandbox},
            )
            return clamp01(float(data["summary"]["ai"]))  # 0-1
        except (KeyError, TypeError, ValueError) as exc:
            _unusable(self.name, locals().get("data"), exc)
            return None


def commercial_detectors() -> list:
    """Every commercial adapter (cheap to instantiate; no network until score())."""
    return [
        OriginalityDetector(),
        GPTZeroDetector(),
        WinstonDetector(),
        SaplingDetector(),
        ZeroGPTDetector(),
        CopyleaksDetector(),
    ]
