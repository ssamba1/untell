"""Local LoRA-policy rewriter — the RL-trained moat as a rewriter backend.

Loads the GRPO/LoRA adapter produced by ``training/rl_humanizer.py`` (path in ``UNTELL_POLICY_DIR``)
on top of its base instruct model and rewrites in a SINGLE forward pass — the whole point of the moat:
no API key, no inference loop, runs local (GPU, or CPU slowly). Heavy deps (torch/transformers/peft)
are imported lazily so this module stays importable on a no-GPU box; ``available()`` just returns
False there, exactly like the hosted (Anthropic/OpenAI) rewriters.

Wire-up: set ``UNTELL_POLICY_DIR=out/rl-humanizer`` and ``get_rewriter()`` returns this in preference
to the API rewriters, so the existing loop / eval harness uses the trained policy with no other change.

Env:
    UNTELL_POLICY_DIR    adapter dir (the trained LoRA). Required for ``available()``.
    UNTELL_POLICY_BASE   base model id (default ``Qwen/Qwen2.5-3B-Instruct``; must match training).
    UNTELL_POLICY_4BIT   "1" to load the base in 4-bit (QLoRA inference, fits a 16GB GPU).
    UNTELL_POLICY_MAXTOK max new tokens (default 512).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# The single source of truth for the training prompt: rl_humanizer, dpo_humanizer and distill all
# import it from here. It used to be re-typed as a literal in two of them, so a change here would
# have left DPO and the distilled SFT data tuned on one instruction while inference used another —
# with nothing to detect the drift but the quality of the output.
#
# The policy was RL-trained on THIS exact instruction, so feeding it the loop's richer rubric prompt
# (rewriter/prompts.py) would be out-of-distribution. The moat is single-pass by design — the
# per-iteration detector feedback the API rewriter consumes does not apply here; we just (re)sample
# from the trained prompt.
_TRAIN_PROMPT = (
    "Rewrite the following text so it reads as natural human writing while preserving its exact "
    "meaning:\n\n{text}"
)
# The UNTUNED path needs its own instruction, and reusing the one above is what made it useless.
# `_TRAIN_PROMPT` works on a policy that was RL-trained to stay faithful; handed to a base instruct
# model it is out of distribution in the other direction — nothing anchors the output to the source,
# so the model summarises. MEASURED (Result 168) on Qwen2.5-1.5B-Instruct, RAID, 3 documents: every
# candidate was vetoed by `meaning_preserved` and every veto was correct — entailment 0.037-0.229
# with near-zero contradiction, one candidate deleting 58 words against a 27-word allowance, another
# EXPANDING by 47 and scoring 0.7555 -> 0.9992, worse than its input. Two of the three opened "In
# their paper titled ...," / "This research introduces EdgeFlow" — third-person descriptions of an
# abstract rather than rewrites of it.
#
# Each rule below is one of those failures. The per-sentence requirement is the load-bearing one:
# it makes deletion and reframing structurally awkward rather than something the gates catch after
# the fact, which is the only reason the gates were rejecting 4 of 5 candidates.
_BASE_PROMPT = (
    "Rewrite the text below, sentence by sentence, so it reads as natural human writing.\n\n"
    "Rules:\n"
    "- Preserve every fact, number, name, and claim exactly as stated.\n"
    "- Rewrite the text itself. Do not describe it, summarise it, or refer to its authors or to "
    '"the paper" / "this research".\n'
    "- Keep the same point of view and grammatical person as the input.\n"
    "- Write one sentence of output for each sentence of input, in the same order.\n"
    "- Add nothing that is not in the input, and drop nothing that is.\n"
    "- Stay within 10% of the input's length.\n"
    "- Output only the rewritten text — no preamble, heading, quotes, or commentary.\n\n"
    "Text:\n{text}"
)

# One sentence in, one sentence out. The document-level prompt above encodes the same intent as
# rules, and MEASURED on Qwen2.5-1.5B it does not hold: with six explicit constraints the model still
# opened "In the paper titled ...", ran to 108% length on one document and compressed another to 29%.
# Instruction-following at this scale is not strong enough to carry the constraint.
#
# Feeding one sentence removes the opportunity instead of forbidding it — a model that cannot see the
# document cannot summarise it. MEASURED on five sentences of the document that failed worst:
# entailment 0.967 / 0.989 / 0.973 / 0.960 / 0.287 and contradiction 0.002-0.005, against 0.037-0.229
# for the whole-document prompt on the same corpus.
_SENTENCE_PROMPT = (
    "Rewrite this one sentence so it reads as natural human writing. Keep every fact, number and "
    "name. Do not add or remove information. Reply with the rewritten sentence and nothing else."
    "\n\nSentence: {text}"
)

# A rewritten sentence is kept only when it is at least this entailed by the original. The fifth
# sentence of the probe above came back at 0.287 while its four neighbours cleared 0.96 — so the
# per-sentence failure mode is real, it is rare, and reverting that one sentence costs the document
# nothing. Below this, the source sentence is used unchanged: the same only-ever-help rule the T5
# path already follows, applied one sentence at a time.
_SENTENCE_ENTAILMENT_FLOOR = 0.60

# Mechanical fallback when the NLI stack is absent, and a backstop when it is not.
#
# The first version of this band was (0.6, 1.6) and it made the rewriter emit candidates its own
# pipeline was arithmetically certain to reject. `meaning_preserved` allows a document to lose
# `max(10, 10% of its words)`; a 310-word document may lose 31. A per-sentence floor of 0.6 lets
# EVERY sentence shed 40%, which on the traced document is ~112 words — nearly four times the
# budget, and the loop then throws the whole rewrite away. Sentence-level faithfulness and
# document-level faithfulness are different constraints, and satisfying only the first is what
# produced the byte-identical no-op that three earlier fixes each failed to explain.
#
# 0.8 was then too tight, for the same reason in reverse. TRACED over the 9 sentences of that
# document: three were rejected at ratios 0.74-0.77 while scoring entailment 0.935 and 0.951 —
# faithful compressions, discarded by a band that was standing in for a budget that now exists. The
# floor is a guard against a dropped clause, not a length policy; the running budget below is the
# length policy, and it is the one that knows what the document can still afford.
_SENTENCE_LENGTH_BAND = (0.7, 1.4)

DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"


# "Output only the rewritten text" is an instruction, not a guarantee, and a base instruct model
# obeys it most of the time. The failure is expensive and silent: a leading "Here is the rewritten
# text:" is counted as added content by `words_lost` and drags the whole candidate's entailment
# down, so one stray line can veto a rewrite that was otherwise fine.
#
# Deliberately narrow, and narrower than it first was. "A short line ending in a colon" seemed like
# a safe description of a preamble until a known-negative in the test suite failed on *"The committee
# reached the following conclusions after reviewing every dataset at length:"* — twelve words, a real
# sentence, and the whole document after it was thrown away. A rewrite silently losing its first
# sentence is a worse defect than the preamble this exists to remove.
#
# So match what a preamble actually IS. Model boilerplate is stereotyped and opens with a small set
# of announcing words; prose that happens to end in a colon does not. Anything else is the model's
# rewrite and is not this function's business to edit. The trained policy never sees this at all —
# its output shape is what it was trained on.
_PREAMBLE_RE = re.compile(
    r"^(?:sure|certainly|of course|okay|ok|here(?:'s| is| are)|the (?:rewritten|revised)|"
    r"rewritten|revised|output|result)\b[^.!?]*:$",
    re.IGNORECASE,
)

# The loop rewrites LOCKED text: citations, versions and quantities are replaced by ⟦HZ0007⟧
# sentinels before any transform sees them, and a candidate that does not carry them back is
# rejected. MEASURED on the RAID sample this arm uses: doc 0 has 12 locked spans and **all 9 of its
# sentences carry a sentinel**, doc 1 six of ten. So on the sentence path, nearly every unit handed
# to the model contains a token it has never seen, in a Unicode range it has almost no training
# signal for — and a 1.5B model paraphrases it away. Every sentence then fails the integrity check,
# every sentence reverts, and the rewriter returns its input: the byte-identical no-op measured
# before this existed.
#
# `[REF7]` is the same information in a shape small models copy reliably, because it looks like the
# citation markers they have seen a great deal of. Swapped in before generation and back out after,
# so the loop still gets its own sentinels and nothing downstream knows this happened.
_SHIELD_FMT = "[REF{}]"
_SHIELD_RE = re.compile(r"\[REF(\d+)\]")


def _shield_sentinels(text: str) -> tuple[str, dict[str, str]]:
    """Swap ⟦HZxxxx⟧ for [REFn] so a small model will reproduce it."""
    from untell.scripts.preserve import SENTINEL_RE

    back: dict[str, str] = {}
    def _one(match: re.Match) -> str:
        token = _SHIELD_FMT.format(len(back))
        back[token] = match.group(0)
        return token

    return SENTINEL_RE.sub(_one, text), back


def _unshield(text: str, back: dict[str, str]) -> str:
    for token, sentinel in back.items():
        text = text.replace(token, sentinel)
    # A shield the model invented or renumbered maps to nothing; leaving `[REF9]` in the output
    # would ship a literal placeholder to the reader. The sentinel check below rejects the sentence
    # anyway, but only if what remains is not mistaken for prose.
    return _SHIELD_RE.sub("", text)


def _next_torch_seed() -> int:
    """Draw the next generation seed from the module the loop already seeded.

    Split out from the call site so the property can be tested without loading a 1.5B model: same
    ``random.seed`` gives the same sequence, a different one gives a different sequence, and the
    sequence advances so ``best_of=N`` samples N different candidates rather than one N times.
    """
    import random

    return random.getrandbits(63)


def _sentinels_intact(source: str, candidate: str) -> bool:
    """Same sentinels, same number of each — compared on the TEXT, never on the mapping.

    `Counter(mapping)` reads dict VALUES as counts and silently reports agreement; this repository
    has already been bitten by exactly that. Compare what the regex finds in each string.
    """
    from collections import Counter

    from untell.scripts.preserve import SENTINEL_RE

    return Counter(SENTINEL_RE.findall(source)) == Counter(SENTINEL_RE.findall(candidate))


def _strip_preamble(text: str) -> str:
    """Drop an announcing first line and any wrapper around the whole output."""
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            body = parts[1]
            text = body.split("\n", 1)[1].strip() if "\n" in body else body.strip()
    head, sep, rest = text.partition("\n")
    if sep and rest.strip() and _PREAMBLE_RE.match(head.strip()):
        text = rest.strip()
    if len(text) > 1 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    return text


def _env_max_new_tokens(source_tokens: int, use_adapter: bool) -> int:
    """The token budget for one generation: ``UNTELL_POLICY_MAXTOK`` if set, else the default.

    The env value used to be handed straight to ``int()`` inside ``_generate_once``, so
    ``UNTELL_POLICY_MAXTOK=abc`` died mid-generation with a bare ``ValueError`` — the one
    env var documented (README) as a token cap that could crash on a typo. Same treatment
    as ``UNTELL_RATE_LIMIT`` in the API server: warn and fall back to the computed default.

    A value that parses but is not positive is refused the same way: ``max_new_tokens=0``
    makes the model emit nothing, and a negative value is a transformers-side error that
    names neither the variable nor the fix.
    """
    budget = os.environ.get("UNTELL_POLICY_MAXTOK")
    if budget is None or budget.strip() == "":
        return max(512, int(source_tokens * 1.6)) if not use_adapter else 512
    try:
        n = int(budget)
    except ValueError:
        logger.warning(
            "ignoring UNTELL_POLICY_MAXTOK=%r: expected a whole number of tokens; "
            "using the default budget instead.",
            budget,
        )
        return max(512, int(source_tokens * 1.6)) if not use_adapter else 512
    if n <= 0:
        logger.warning(
            "ignoring UNTELL_POLICY_MAXTOK=%r: must be a positive number of tokens; "
            "using the default budget instead.",
            budget,
        )
        return max(512, int(source_tokens * 1.6)) if not use_adapter else 512
    return n


class LocalPolicyRewriter:
    """Rewriter backed by a locally-loaded base model + trained LoRA adapter.

    Set ``use_adapter=False`` to load the *base* model with no adapter — used by the eval harness to
    A/B the trained policy against the untuned base on identical inputs.
    """

    name = "local-policy"

    def __init__(
        self,
        adapter_dir: str | None = None,
        base_model: str | None = None,
        *,
        use_adapter: bool = True,
    ):
        self.adapter_dir = adapter_dir or os.environ.get("UNTELL_POLICY_DIR", "")
        self.base_model = base_model or os.environ.get("UNTELL_POLICY_BASE", DEFAULT_BASE)
        self.use_adapter = use_adapter
        self._model = None
        self._tok = None
        if not use_adapter:
            self.name = "base-model"

    def available(self) -> bool:
        """True when the adapter dir exists (when using one) and torch/transformers/peft import."""
        if self.use_adapter and (not self.adapter_dir or not os.path.isdir(self.adapter_dir)):
            return False
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            if self.use_adapter:  # peft is only needed to load the adapter; base-only eval doesn't use it
                import peft  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kw: dict[str, Any] = {}
        if os.environ.get("UNTELL_POLICY_4BIT") == "1":
            if not torch.cuda.is_available():
                # bitsandbytes 4-bit needs CUDA; without it from_pretrained dies with an opaque BNB
                # error. Fail with a clear message instead.
                raise RuntimeError(
                    "UNTELL_POLICY_4BIT=1 requires a CUDA GPU (bitsandbytes 4-bit). "
                    "Unset it to load on CPU."
                )
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
            )
        else:
            kw["dtype"] = "auto"  # torch_dtype= is deprecated in transformers 5.x
        if torch.cuda.is_available():
            # `device_map="auto"` is the right call for a policy model that may not fit one GPU —
            # but it hard-requires `accelerate`, which transformers does NOT pull in. Without it
            # from_pretrained dies with "Using a `device_map` ... requires `accelerate`", the same
            # opaque failure that made local_judge dead on arrival. Fail with a clear message
            # instead, exactly as the 4-bit branch above already does for bitsandbytes.
            import importlib.util

            if importlib.util.find_spec("accelerate") is None:
                raise RuntimeError(
                    "loading the policy model on a GPU needs `accelerate` (device_map='auto'); "
                    "install it with `pip install accelerate`, or run on CPU."
                )
            kw["device_map"] = "auto"

        model = AutoModelForCausalLM.from_pretrained(self.base_model, **kw)
        if self.use_adapter:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, self.adapter_dir)
        model.eval()
        tok = AutoTokenizer.from_pretrained(self.base_model)
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token
        self._model, self._tok = model, tok

    def _sentence_is_faithful(self, source: str, candidate: str) -> bool:
        """Keep a rewritten sentence only if it still says what the source said."""
        if not candidate or candidate == source:
            return False
        if not _sentinels_intact(source, candidate):
            return False
        low, high = _SENTENCE_LENGTH_BAND
        words = len(source.split())
        if words and not (low <= len(candidate.split()) / words <= high):
            return False
        from untell.scripts import entailment

        if not entailment.available():  # mechanical band only; never a silent pass on a dead model
            return True
        score = entailment.entailment_score(source, candidate)
        return score is not None and score >= _SENTENCE_ENTAILMENT_FLOOR

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        """Rewrite ``text``. ``score_result``/``threshold`` are accepted for the ``Rewriter``
        protocol but unused — the policy was trained to untell from the bare prompt, not from
        detector feedback.

        The trained policy rewrites the whole document in one pass, as it was trained to. The
        untuned base path rewrites sentence by sentence, because whole-document prompting measured
        as summarisation there (see ``_SENTENCE_PROMPT``). ``UNTELL_POLICY_WHOLE_DOC=1`` forces the
        single-pass path on the base model, which is what the A/B behind that decision needs.
        """
        self._load()
        if self.use_adapter or os.environ.get("UNTELL_POLICY_WHOLE_DOC") == "1":
            return self._generate_once(text)

        from untell.text_split import split_sentences

        pieces = split_sentences(text)
        if not pieces:
            return text
        # The band above bounds one sentence; this bounds the document. Ten sentences each shrinking
        # by an allowed 20% still overruns a 10% document budget, so the two guards have to be the
        # same guard — spend from one budget and stop accepting compressive rewrites when it is out.
        from untell.scripts.entailment import deletion_allowance

        budget = deletion_allowance(text)
        spent = 0.0
        out, changed = [], 0
        for piece in pieces:
            # Short fragments are headings, list markers and stubs; a 1.5B model asked to make one
            # "read as human" invents a sentence around it.
            if len(piece.split()) < 8:
                out.append(piece)
                continue
            shielded, back = _shield_sentinels(piece)
            candidate = _unshield(self._generate_once(shielded, sentence=True), back)
            shrink = max(0, len(piece.split()) - len(candidate.split()))
            if self._sentence_is_faithful(piece, candidate) and spent + shrink <= budget:
                out.append(candidate)
                spent += shrink
                changed += 1
            else:
                out.append(piece)  # only-ever-help: a rejected draw costs the sentence nothing
        # Every sentence reverted means the caller gets its input back, which the loop reads as a
        # no-op rather than as a rewrite it should adopt.
        return " ".join(out) if changed else text

    def _generate_once(self, text: str, *, sentence: bool = False) -> str:
        """One prompt, one sample, decoded."""
        import torch

        # The trained policy gets the instruction it was trained on and nothing else; only the
        # untuned base path takes an anchored prompt. Sending either of the others to the adapter
        # would be the same out-of-distribution mistake in the opposite direction.
        if self.use_adapter:
            template = _TRAIN_PROMPT
        else:
            template = _SENTENCE_PROMPT if sentence else _BASE_PROMPT
        messages = [{"role": "user", "content": template.format(text=text)}]
        # UNTELL_POLICY_NO_SYSTEM=1 suppresses the tokenizer's default system turn (e.g. Qwen's
        # "You are a helpful assistant") — some base models read as more human without it. Not every
        # template accepts the kwarg, so fall back to the plain call on any failure.
        tmpl_kw = {"tokenize": False, "add_generation_prompt": True}
        if os.environ.get("UNTELL_POLICY_NO_SYSTEM") == "1":
            try:
                prompt = self._tok.apply_chat_template(messages, system_prompt="", **tmpl_kw)
            except (TypeError, ValueError):
                prompt = self._tok.apply_chat_template(messages, **tmpl_kw)
        else:
            prompt = self._tok.apply_chat_template(messages, **tmpl_kw)
        # Use a real parameter's device, not self._model.device: when accelerate dispatches the model
        # across devices (device_map="auto" with >1 GPU or CPU offload) there is no single .device.
        # `generate(do_sample=True)` draws from torch's global RNG, and nothing in this project seeds
        # it: `untell_text` sets `random.seed(effective_seed)` (run.py) which torch never consults.
        # MEASURED: the same document, same code, same `seed=0` gave 0.9591 -> 0.1925 on one run and
        # a byte-identical no-op on the next — so a figure taken from this rewriter could not be
        # reproduced even by re-running the command that produced it.
        #
        # Result 144 records this exact class of defect being fixed in `structural.py`, where an
        # unseeded stream left published README figures that no commit reproduces. Deriving the torch
        # seed from the already-seeded `random` module keeps one source of randomness: fixed for a
        # given `seed=`, and still advancing between draws so `best_of=N` samples N different things.
        torch.manual_seed(_next_torch_seed())
        device = next(self._model.parameters()).device
        inputs = self._tok(prompt, return_tensors="pt", truncation=True, max_length=2048).to(device)
        # A fixed 512-token cap and "one sentence out per sentence in" are in direct conflict on a
        # long document: the generation stops mid-rewrite and the loop sees the remainder as deleted
        # content, which `words_lost` vetoes. The source is the only thing that says how much room
        # the output needs, so the untuned path budgets from it. An explicit env value still wins —
        # the trained policy is single-pass and short by design, so its default is untouched.
        source_tokens = len(self._tok(text)["input_ids"])
        max_new = _env_max_new_tokens(source_tokens, self.use_adapter)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=max_new,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=self._tok.pad_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[1] :]
        decoded = self._tok.decode(gen, skip_special_tokens=True).strip()
        return decoded if self.use_adapter else _strip_preamble(decoded)
