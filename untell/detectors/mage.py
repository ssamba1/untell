"""MAGE detector adapter (full tier).

Wraps ``yaful/MAGE`` (a Longformer-based machine-generated-text detector) via a HF
text-classification pipeline on CPU. Stronger and more modern than RoBERTa-OpenAI, trained
across many generators/domains. Guarded: unavailable unless ``transformers``+``torch`` import.
"""

from __future__ import annotations

from .base import clamp01

_MODEL_ID = "yaful/MAGE"


class MageDetector:
    name = "mage"
    tier = "full"

    _pipe = None
    _warned = False
    _dead = False  # set once a load fails so we never re-attempt the heavy import per call

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self):
        if MageDetector._pipe is None:
            from transformers import pipeline

            MageDetector._pipe = pipeline(
                "text-classification",
                model=_MODEL_ID,
                tokenizer=_MODEL_ID,
                truncation=True,
                max_length=1024,
                top_k=None,
                device=-1,
            )
        return MageDetector._pipe

    def score(self, text: str) -> float | None:
        if MageDetector._dead:
            raise RuntimeError("mage disabled after a prior load failure")
        if not text.strip():
            return None
        try:
            pipe = self._load()
        except Exception as exc:
            # yaful/MAGE ships a config (int-valued id2label) newer huggingface_hub rejects, and a
            # NumPy 2.x / torch mismatch bites here too. Either way: disable and EXCLUDE this
            # detector — never fold in a fake neutral 0.5 that would silently pin the ensemble max.
            MageDetector._dead = True
            if not MageDetector._warned:
                import sys

                print(
                    f"[untell] mage failed to load and was EXCLUDED from the ensemble "
                    f"({type(exc).__name__}: {str(exc)[:140]}). "
                    "Often a NumPy 2.x / huggingface_hub mismatch — see README troubleshooting.",
                    file=sys.stderr,
                )
                MageDetector._warned = True
            raise
        out = pipe(text)
        scores = out[0] if isinstance(out[0], list) else out
        # MAGE label convention: "machine-generated" (or LABEL_0 in some exports) == AI.
        ai = next(
            (
                s["score"]
                for s in scores
                if "machine" in str(s["label"]).lower() or str(s["label"]).lower() in ("label_0", "ai", "fake")
            ),
            None,
        )
        if ai is None:
            human = next(
                (s["score"] for s in scores if "human" in str(s["label"]).lower() or str(s["label"]).lower() in ("label_1", "real")),
                0.5,
            )
            ai = 1.0 - human
        return clamp01(ai)
