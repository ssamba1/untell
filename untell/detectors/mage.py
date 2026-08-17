"""MAGE detector adapter (full tier).

Wraps ``yaful/MAGE`` (a Longformer-based machine-generated-text detector) via a HF
text-classification pipeline on CPU. Stronger and more modern than RoBERTa-OpenAI, trained
across many generators/domains. Guarded: unavailable unless ``transformers``+``torch`` import.
"""

from __future__ import annotations

import logging

from .base import batched_windowed_max, clamp01

logger = logging.getLogger(__name__)

_MODEL_ID = "yaful/MAGE"


def _is_transport_error(exc: BaseException) -> bool:
    """True when *exc* means "the remote could not be reached or dropped the
    connection" rather than "the remote actively refused".

    Mirrors huggingface_hub's own offline classification (ConnectError,
    TimeoutException, OfflineModeIsEnabled) plus the transport-level classes it
    does NOT catch (TLS handshake failures, mid-response resets, stream
    errors). ``httpx.ProxyError`` is deliberately excluded: huggingface_hub
    re-raises it on purpose so a misconfigured proxy surfaces instead of being
    silently ignored.
    """
    import socket
    import ssl

    import httpx

    return isinstance(
        exc,
        (
            ssl.SSLError,
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.StreamError,
            httpx.DecodingError,
            httpx.TooManyRedirects,
            ConnectionError,
            socket.timeout,
            TimeoutError,
        ),
    )


def _snapshot_dir() -> str:
    """Resolve the local MAGE snapshot, tolerating a glitchy remote.

    ``snapshot_download`` revalidates the repo against the Hub on every call
    (the remote ETag/commit liveness check). huggingface_hub classifies
    connect/timeout/offline errors as "offline" and falls back to the cached
    snapshot, but transport failures it does not classify — TLS handshake
    errors (``ssl.SSLError``), connection resets mid-response
    (``httpx.ReadError``/``RemoteProtocolError``) — propagate. A one-off blip
    of that kind must not permanently kill a fully-cached detector (``_dead``
    in ``score`` is permanent for the process), so retry cache-only and load
    what is on disk. If nothing is cached, the original error propagates and
    the detector goes dead for real.
    """
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(_MODEL_ID)
    except Exception as exc:
        if not _is_transport_error(exc):
            raise
        try:
            return snapshot_download(_MODEL_ID, local_files_only=True)
        except Exception:
            raise exc from None


class MageDetector:
    name = "mage"
    tier = "full"

    _tok = None
    _model = None
    _warned = False
    _dead = False  # set once a load fails so we never re-attempt the heavy import per call

    def available(self) -> bool:
        # MAGE (Longformer) is the strongest free/local detector, so it is part of the default full
        # tier for scoring. It is heavy on CPU (~600MB, ~50-100x slower than base-size detectors); a
        # per-candidate RL reward can exclude it by setting UNTELL_DISABLE_MAGE=1 to keep training
        # fast, without weakening ordinary scoring/eval.
        import os

        if os.environ.get("UNTELL_DISABLE_MAGE") == "1":
            return False
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        # yaful/MAGE ships config.json with `id2label = {"0": 0, "1": 1}` — string keys but INT
        # *values*. transformers 5.x validates the config via a huggingface_hub strict dataclass that
        # only accepts dict[int,str] / dict[str,str], so `from_pretrained(_MODEL_ID)` raises before we
        # can touch the object. We can't patch it post-load and we can't override it via kwargs (the
        # on-disk dict is validated at construction). So: snapshot the repo, rewrite the offending
        # field in a real (un-symlinked) config.json in the local dir, then load from that dir where
        # id2label is now str->str and validation passes. The forward pass never needs the labels;
        # we resolve the AI index from the normalized map ourselves.
        if MageDetector._model is None:
            import json
            import os

            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            local = _snapshot_dir()
            cfg_path = os.path.join(local, "config.json")
            with open(cfg_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            i2l = raw.get("id2label") or {}
            if not (i2l and all(isinstance(v, str) for v in i2l.values())):
                # MAGE label convention: 0 == machine-generated, 1 == human.
                raw["id2label"] = {"0": "machine", "1": "human"}
                raw["label2id"] = {"machine": 0, "human": 1}
                raw["num_labels"] = 2
                with open(cfg_path + ".fixed", "w", encoding="utf-8") as fh:
                    json.dump(raw, fh)
                os.replace(cfg_path + ".fixed", cfg_path)  # replaces the symlink, leaves weight blobs intact
            tok = AutoTokenizer.from_pretrained(local)
            model = AutoModelForSequenceClassification.from_pretrained(local)
            MageDetector._tok, MageDetector._model = tok, model.eval()
        return MageDetector._tok, MageDetector._model

    def _score_batch(self, windows: list[str]) -> list[float | None]:
        """MAGE P(AI) per window from ONE batched forward.

        Windows are tokenised with per-window truncation at 1024 tokens (identical
        to the single-window path) and padded to the longest in the batch; with the
        attention mask every sample's logits are the same as a single-sample
        forward. If the tokenizer cannot produce tensors for a batch — e.g. a
        stubbed seam in a test — scoring falls back to one forward per window,
        which is exactly the pre-batch behaviour.
        """
        import torch

        tok, model = self._load()
        id2label = model.config.id2label  # str-keyed after _load()
        # MAGE label convention: "machine-generated" (or LABEL_0 in some exports) == AI.
        ai_idx = next(
            (
                int(k)
                for k, v in id2label.items()
                if "machine" in str(v).lower() or str(v).lower() in ("label_0", "ai", "fake")
            ),
            None,
        )
        if ai_idx is None:
            human_idx = next(
                (
                    int(k)
                    for k, v in id2label.items()
                    if "human" in str(v).lower() or str(v).lower() in ("label_1", "real")
                ),
                None,
            )
            if human_idx is None:
                return [None] * len(windows)
            idx, flip = human_idx, True
        else:
            idx, flip = ai_idx, False
        try:
            encs = [tok(w, return_tensors="pt", truncation=True, max_length=1024) for w in windows]
            maxlen = max(e["input_ids"].shape[1] for e in encs)
            pad = torch.nn.functional.pad
            ids = torch.cat([pad(e["input_ids"], (0, maxlen - e["input_ids"].shape[1])) for e in encs], dim=0)
            mask = torch.cat(
                [pad(torch.ones_like(e["input_ids"]), (0, maxlen - e["input_ids"].shape[1])) for e in encs],
                dim=0,
            )
        except Exception:
            return [self._score_one(w, idx, flip) for w in windows]
        with torch.no_grad():
            probs = torch.softmax(model(ids, attention_mask=mask).logits, dim=-1)
        p = probs[:, idx] if not flip else 1.0 - probs[:, human_idx]
        return [float(x) for x in p]

    def _score_one(self, window: str, idx: int, flip: bool) -> float:
        """Single-window P(AI) — the fallback (and the pre-batch) path."""
        import torch

        tok, model = self._load()
        inputs = tok(window, return_tensors="pt", truncation=True, max_length=1024)
        with torch.no_grad():
            probs = torch.softmax(model(**inputs).logits, dim=-1)[0]
        return float(probs[idx]) if not flip else 1.0 - float(probs[idx])

    def score(self, text: str) -> float | None:
        if MageDetector._dead:
            return None
        if not text.strip():
            return None
        try:
            self._load()
        except Exception as exc:
            # Any load failure: disable and EXCLUDE this detector — never fold in a fake neutral 0.5
            # that would silently pin the ensemble max.
            MageDetector._dead = True
            if not MageDetector._warned:
                logger.warning(
                    "mage failed to load and was EXCLUDED from the ensemble "
                    "(%s: %s). Often a NumPy 2.x / huggingface_hub mismatch - see README troubleshooting.",
                    type(exc).__name__, str(exc)[:140],
                )
                MageDetector._warned = True
            raise
        # Windowed at 1024 tokens (~750 words) for the same reason as the other adapters: past its
        # limit the text was silently discarded, so a long document was scored on its opening.
        p = batched_windowed_max(text, self._score_batch, 700)
        return None if p is None else clamp01(p)
