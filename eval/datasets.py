"""Dataset loading for the benchmark.

Pulls AI-generated samples to humanize. Uses HuggingFace ``datasets`` when the ``[eval]`` extra
is installed; otherwise falls back to a small built-in bootstrap sample so the harness still
runs (and tests pass) with zero downloads.

Supported names:
  - ``hc3``   -> Hello-SimpleAI/HC3 ChatGPT answers
  - ``raid``  -> liamdugan/raid machine-generated split
  - ``builtin`` (default fallback) -> packaged sample paragraphs
"""

from __future__ import annotations

# A few machine-flavored paragraphs (formulaic transitions, uniform cadence) for zero-download
# runs. Intentionally "AI-sounding" so the lite detector flags them.
_BUILTIN: list[str] = [
    (
        "Artificial intelligence has fundamentally transformed numerous industries in recent "
        "years. Moreover, it has enabled organizations to streamline their operations and "
        "improve efficiency. Furthermore, machine learning algorithms can analyze vast amounts "
        "of data quickly. Overall, the impact of artificial intelligence continues to grow "
        "significantly across various sectors."
    ),
    (
        "Climate change represents one of the most pressing challenges of our time. Additionally, "
        "it poses significant risks to ecosystems and human societies alike. Furthermore, rising "
        "global temperatures contribute to more frequent extreme weather events. In conclusion, "
        "addressing climate change requires coordinated global action and sustained commitment."
    ),
    (
        "Effective communication plays a crucial role in the success of any organization. "
        "Moreover, it fosters collaboration and strengthens relationships among team members. "
        "Additionally, clear communication helps prevent misunderstandings and conflicts. "
        "Overall, organizations that prioritize communication tend to achieve better outcomes."
    ),
    (
        "Regular physical exercise offers numerous benefits for both physical and mental health. "
        "Furthermore, it helps reduce the risk of chronic diseases such as diabetes and heart "
        "disease. Additionally, exercise releases endorphins that improve mood and reduce stress. "
        "In summary, incorporating regular exercise into daily routines is highly beneficial."
    ),
    (
        "The development of renewable energy sources is essential for a sustainable future. "
        "Moreover, solar and wind power have become increasingly cost-effective in recent years. "
        "Furthermore, transitioning to renewable energy reduces dependence on fossil fuels. "
        "Overall, investing in renewable energy infrastructure yields long-term environmental "
        "and economic benefits."
    ),
]


def _builtin(n: int) -> list[str]:
    if n <= len(_BUILTIN):
        return _BUILTIN[:n]
    # Repeat to satisfy larger n requests without external data.
    out = list(_BUILTIN)
    while len(out) < n:
        out.append(_BUILTIN[len(out) % len(_BUILTIN)])
    return out[:n]


def load_samples(dataset: str = "builtin", n: int = 5) -> list[str]:
    """Return up to ``n`` AI-generated text samples for the named dataset.

    Falls back to the built-in sample if ``datasets`` isn't installed or the load fails, so the
    harness never hard-requires a network download.
    """
    name = dataset.lower()
    if name in ("builtin", "sample"):
        return _builtin(n)

    try:
        from datasets import load_dataset
    except Exception:
        return _builtin(n)

    try:
        if name == "hc3":
            ds = load_dataset("Hello-SimpleAI/HC3", "all", split="train")
            texts: list[str] = []
            for row in ds:
                answers = row.get("chatgpt_answers") or []
                for a in answers:
                    if a and len(a.split()) > 30:
                        texts.append(a.strip())
                        break
                if len(texts) >= n:
                    break
            return texts[:n] or _builtin(n)

        if name == "raid":
            ds = load_dataset("liamdugan/raid", split="train", streaming=True)
            texts = []
            for row in ds:
                gen = row.get("generation") or row.get("text")
                if gen and row.get("model", "human") != "human" and len(gen.split()) > 30:
                    texts.append(gen.strip())
                if len(texts) >= n:
                    break
            return texts[:n] or _builtin(n)
    except Exception:
        return _builtin(n)

    return _builtin(n)
