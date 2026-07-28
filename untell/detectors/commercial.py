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
import os
import time

from untell._retry import retry

from .base import clamp01


def _post_json(url: str, headers: dict, body: dict, timeout: float = 45.0) -> dict:
    """POST JSON and return parsed JSON. Isolated so tests can monkeypatch it (no network).
    Raises on HTTP/network errors; caller handles.
    """
    import requests

    resp = retry(
        requests.post,
        kw={"url": url, "headers": {"Content-Type": "application/json", **headers}, "json": body, "timeout": timeout},
        max_attempts=3,
    )
    resp.raise_for_status()
    return resp.json()


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
            return clamp01(float(data["score"]["ai"]))
        except (KeyError, TypeError, ValueError):
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
            return clamp01((100.0 - float(data["score"])) / 100.0)
        except (KeyError, TypeError, ValueError):
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
                ai = doc.get("completely_generated_prob", 0.5)
            return clamp01(float(ai))
        except (KeyError, TypeError, ValueError, IndexError):
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
            return clamp01(float(data["score"]))
        except (KeyError, TypeError, ValueError):
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
                return clamp01(float(score_data.get("is_gpt_generated", 50)) / 100.0)
            return None
        except (TypeError, ValueError):
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
        except (KeyError, TypeError, ValueError):
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
