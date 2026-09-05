"""Every technique class for removing AI tells, measured on one corpus against the same axes.

**The comparison table this repo publishes covers three techniques. The census it also publishes
identifies twelve categories across 435 repositories.** `eval/compare_humanizers.py` measures
synonym substitution, back-translation and our own loop; the census
(`docs/humanizer-census.json`) sorts the field into prompt-guide (184 repos),
api-wrapper (75), adversarial-perturbation (39), rule-based-rewriter (38), research-code (19),
fine-tuned-model (11), paraphrase-model (7), unicode-trickery (7), back-translation (3),
detector-with-evasion (5) and dataset (1). Several of the unmeasured classes are **implemented in
this repository** and have never appeared in a benchmark row — homoglyph substitution, the MT pivot,
the T5 paraphraser, the ensemble, the targeted rewriter.

This module measures every class that can run here, on one corpus, against four axes at once.

WHY FOUR AXES AND NOT THE USUAL ONE. A humanizer benchmark that reports the detector score alone
answers "did this fool the detector in the loop", which is the question with the least external
validity in the whole field — the free-ceiling report names in-loop-versus-held-out as the central
unknown. Three more axes are cheap and each catches a different way of winning without succeeding:

* **detector score** — what everyone reports; the loop optimises it directly, so it flatters any
  method that has the detector inside it.
* **catalogued tells** — the rewriter's own rubric. Rounds eighty-one and eighty-two measured this
  catalogue as a REGISTER detector (AUROC 1.0000) and an authorship detector (0.2697), so moving it
  is evidence about register and not about authorship.
* **stylometric displacement** — Burrows's Delta to the machine centroid, from `eval.homogenization`.
  Nobody in the census reports this. It is the axis that shows a rewrite lowering a detector's score
  while leaving the document exactly where it was in style space, which is what the shipped
  rewriters MEASURABLY do.
* **integrity** — whether the output is still the same text a human can use. Unicode trickery scores
  spectacularly on axis one and fails this, and a table without it ranks an attack that breaks
  copy-paste above one that rewrites prose.

    python -m eval.technique_matrix --n 30
    python -m eval.technique_matrix --n 30 --tier full --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import unicodedata

DEFAULT_N = 30


def _availability() -> dict[str, str | None]:
    """Why each technique cannot run here, or None if it can.

    ⚠️ **A technique that could not run and a technique that did nothing produce the same row, and
    in a COMPARISON table the difference decides who wins.** `back_translate` documents itself as
    returning the input unchanged when its models are absent — a reasonable API and a ruinous
    benchmark input. MEASURED here: it reports 0 of 25 documents changed and no movement on any
    axis, which reads as "back-translation does not work" when the truth is "back-translation was
    never tested".

    ⚠️ **This module had that bug; `eval/compare_humanizers.py` did not.** That file already treats
    a technique which changed no sample as unavailable rather than recording the raw-AI baseline as
    its measurement — the guard predates this module and is correct. What a no-change rule cannot do
    is tell "absent" from "ran and genuinely changed nothing", and this repo has a measured instance
    of the second: `surgical` returns its input on text carrying no catalogued tell (round one
    hundred and nine). Collapsing both to "unavailable" would file that real finding as a missing
    package, so both files now probe availability directly and keep the no-change guard for what it
    is actually good at.
    """
    from untell.attacks.back_translation import BackTranslator
    from untell.rewriter import get_rewriter

    reason = _model_blocker()
    out: dict[str, str | None] = {}
    out["back_translation"] = None if BackTranslator().available() else reason
    for name in ("structural", "targeted", "mt_pivot", "t5_paraphrase", "ensemble", "composite"):
        rewriter = get_rewriter(name)
        out[name] = (None if rewriter is not None and rewriter.available() else reason)
    return out


def _model_blocker() -> str:
    """WHY a model-backed technique cannot run: a missing package, or unreachable weights.

    ⚠️ **These are two different walls and this repo's documents have been calling both "torch is
    absent".** They are not the same fact and they do not have the same remedy: one is `pip install`,
    the other cannot be fixed from inside the environment at all.

    MEASURED here, and the assumed cause is the wrong one:

        pip download torch          554.6 MB wheel, downloaded fine — PyPI is REACHABLE
        curl https://huggingface.co  CONNECT tunnel failed, response 403 — egress policy
        local weight cache           empty; no .safetensors or pytorch_model.bin anywhere

    So `torch` is installable and installing it would change nothing: every model-backed technique
    here — the T5 paraphraser, the MT pivot, and the model-backed detectors — needs weights from a
    host the organization blocks. **The three untested rows in the technique matrix are not untested
    through neglect or a missing package; they are unreachable, and 554 MB of torch would not make
    one of them measurable.** Saying "torch is absent" invites a reader to install it and discover
    that for themselves.

    The probe is cheap, bounded and never raises: a HEAD request with a short timeout, and any
    failure to determine reachability degrades to the weaker, still-true statement.
    """
    import importlib.util

    have_torch = importlib.util.find_spec("torch") is not None
    have_transformers = importlib.util.find_spec("transformers") is not None
    missing = [n for n, present in (("torch", have_torch),
                                    ("transformers", have_transformers)) if not present]
    reachable = _weights_reachable()
    if reachable is False:
        return ("model weights unreachable: huggingface.co is blocked by egress policy (403). "
                "Installing " + (" and ".join(missing) if missing else "the packages") +
                " would not make this measurable")
    if missing:
        return f"not installed: {' and '.join(missing)}"
    return "the technique reports itself unavailable"


def _weights_reachable(timeout: float = 5.0) -> bool | None:
    """True / False / None-if-undetermined for the model host. Never raises, never retries.

    A 403 from the proxy is an organization policy decision, not a transient error, so this makes
    exactly one attempt and reports it. `None` means the question could not be answered, which is
    reported as such rather than assumed either way.
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request("https://huggingface.co/", method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code not in (401, 403, 407)
    except Exception:
        # A tunnel refused by the proxy surfaces as a transport error rather than an HTTPError.
        return False


def _techniques() -> dict[str, object]:
    """Name -> (category, callable). Anything whose dependencies are absent reports itself absent.

    Categories are the census's own, so a reader can map a row to the slice of the field it stands
    for rather than to one library's name.
    """
    from untell.attacks import back_translate, homoglyph_substitute, surgical_substitute

    def _rewriter(prefer: str):
        def run(text: str) -> str:
            from untell.rewriter import get_rewriter
            from untell.scripts.score import score_text

            rewriter = get_rewriter(prefer)
            if rewriter is None or not rewriter.available():
                raise RuntimeError(f"{prefer} is not available in this environment")
            return rewriter.rewrite(text, score_text(text, tier="lite"), 0.30)

        return run

    def _loop(prefer: str, best_of: int = 3):
        def run(text: str) -> str:
            from untell.scripts.run import untell_text

            result = untell_text(text, tier="lite", threshold=0.30, max_iters=5,
                                 rewriter=prefer, best_of=best_of)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("final", text)

        return run

    return {
        "none (control)": ("—", lambda t: t),
        "homoglyph_substitute": ("unicode-trickery",
                                 lambda t: homoglyph_substitute(t, rate=0.15)),
        "synonym_swap": ("adversarial-perturbation",
                         lambda t: surgical_substitute(t, tier="lite", max_subs=10)["text"]),
        "back_translation": ("back-translation", back_translate),
        "structural": ("rule-based-rewriter", _rewriter("structural")),
        "targeted": ("rule-based-rewriter", _rewriter("targeted")),
        "mt_pivot": ("back-translation", _rewriter("mt_pivot")),
        "t5_paraphrase": ("paraphrase-model", _rewriter("t5_paraphrase")),
        "ensemble": ("research-code", _rewriter("ensemble")),
        "composite (our default)": ("rule-based-rewriter", _rewriter("composite")),
        "our closed loop": ("detector-in-loop", _loop("composite")),
    }


def integrity(original: str, rewritten: str) -> dict:
    """Is the output still text a human can use, or has it been sabotaged to fool a byte reader?

    Unicode trickery wins the detector axis by construction and fails here, and a table without this
    column ranks an attack that breaks copy-paste, search and screen readers above one that actually
    rewrites prose. Three checks, each naming a concrete consequence:

    * **hidden characters** — zero-width and formatting codepoints a reader cannot see and a
      paste-into-Word will carry.
    * **non-ASCII letters where the source had none** — homoglyphs. A Cyrillic `а` inside an English
      word breaks search, spellcheck and anything matching on the word.
    * **NFKC-fold equality** — whether the damage survives the normalisation that any serious
      pipeline applies. An attack that a single `unicodedata.normalize` undoes is not an attack on
      a detector, it is an attack on a detector that forgot to normalise.
    """
    from untell.attacks import count_hidden

    def _foreign_letters(text: str) -> int:
        return sum(1 for ch in text if ch.isalpha() and ord(ch) > 127)

    folded = unicodedata.normalize("NFKC", rewritten)
    return {
        "hidden_chars": count_hidden(rewritten) - count_hidden(original),
        "foreign_letters": _foreign_letters(rewritten) - _foreign_letters(original),
        "survives_nfkc": folded == rewritten,
    }


def measure(texts: list[str], tier: str = "lite", n: int = DEFAULT_N) -> dict:
    """Run every available technique over the same texts and score all four axes."""
    from eval.data.generated_abstracts import ABSTRACTS
    from eval.homogenization import DEFAULT_VOCAB, centroid, delta, profile, vocabulary
    from untell.scripts.score import score_text
    from untell.scripts.tells import score_tells

    texts = list(texts)[:n]
    machine = list(ABSTRACTS)
    # The stylometric frame is fixed ONCE, from the unrewritten corpus, so every technique is
    # measured against the same centroid and the same z-scale. Recomputing it per technique would
    # let each one move the ruler it is measured with.
    vocab = vocabulary(texts + machine, DEFAULT_VOCAB)
    machine_centre = centroid([profile(t, vocab) for t in machine])
    base_profiles = [profile(t, vocab) for t in texts]
    means = [statistics.fmean(p[i] for p in base_profiles) for i in range(len(vocab))]
    stdevs = [statistics.pstdev([p[i] for p in base_profiles]) for i in range(len(vocab))]

    def _delta(text: str) -> float:
        return delta(profile(text, vocab), machine_centre, means, stdevs)

    baseline = [{
        "score": score_text(t, tier=tier)["max"],
        "tells": score_tells(t).get("tells", 0),
        "words": len(t.split()),
        "delta": _delta(t),
    } for t in texts]

    absent = _availability()
    rows = []
    for name, (category, fn) in _techniques().items():
        # Probed, not inferred. A technique whose dependencies are missing is reported as untested,
        # never as tested-and-ineffective — see `_availability`.
        key = name.split(" ")[0]
        if absent.get(key):
            rows.append({"technique": name, "category": category,
                         "unavailable": absent[key], "note": "NOT TESTED — absent, not ineffective"})
            continue
        scores, tells, deltas, changed = [], [], [], 0
        hidden, foreign, nfkc_safe = 0, 0, 0
        try:
            for text, base in zip(texts, baseline):
                out = fn(text)
                changed += int(out != text)
                scores.append(score_text(out, tier=tier)["max"])
                tells.append(score_tells(out).get("tells", 0))
                deltas.append(_delta(out) - base["delta"])
                marks = integrity(text, out)
                hidden += marks["hidden_chars"]
                foreign += marks["foreign_letters"]
                nfkc_safe += int(marks["survives_nfkc"])
        except Exception as exc:
            rows.append({"technique": name, "category": category,
                         "unavailable": f"{type(exc).__name__}: {str(exc)[:110]}"})
            continue
        total_words = sum(b["words"] for b in baseline) or 1
        base_tells = sum(b["tells"] for b in baseline)
        rows.append({
            "technique": name,
            "category": category,
            "changed": changed,
            "n": len(texts),
            "score_before": round(statistics.fmean(b["score"] for b in baseline), 4),
            "score_after": round(statistics.fmean(scores), 4),
            "tells_per_100w_before": round(100 * base_tells / total_words, 3),
            "tells_per_100w_after": round(100 * sum(tells) / total_words, 3),
            # Positive means the technique moved the document AWAY from the machine centroid, which
            # is the direction "less machine-like" would have to mean if it meant anything
            # stylometric. Nobody in the census reports this axis.
            "delta_displacement": round(statistics.fmean(deltas), 4),
            "hidden_chars_added": hidden,
            "foreign_letters_added": foreign,
            "survives_nfkc": f"{nfkc_safe}/{len(texts)}",
        })
    return {"tier": tier, "n": len(texts), "rows": rows}


def _render(report: dict) -> str:
    lines = [
        f"Every technique class that runs here, {report['n']} machine-written abstracts, "
        f"tier={report['tier']}.",
        "",
        f"{'technique':<26}{'category':<26}{'chg':>4}{'P(AI)':>16}{'tells/100w':>18}"
        f"{'Δstyle':>9}{'hidden':>8}{'foreign':>9}",
    ]
    for row in report["rows"]:
        if "unavailable" in row:
            lines.append(f"{row['technique']:<26}{row['category']:<26}"
                         f"  NOT TESTED — {row['unavailable']}")
            continue
        lines.append(
            f"{row['technique']:<26}{row['category']:<26}{row['changed']:>4}"
            f"{row['score_before']:>7.4f}->{row['score_after']:<8.4f}"
            f"{row['tells_per_100w_before']:>8.2f}->{row['tells_per_100w_after']:<9.2f}"
            f"{row['delta_displacement']:>+9.4f}{row['hidden_chars_added']:>8}"
            f"{row['foreign_letters_added']:>9}"
        )
    lines += [
        "",
        "Δstyle is Burrows's Delta to the machine centroid: POSITIVE means the technique moved the",
        "document away from it. A technique that lowers P(AI) with Δstyle at zero has changed the",
        "detector's mind without changing the document's style, which is the in-loop/held-out gap",
        "made concrete. `hidden` and `foreign` are characters a reader cannot see and letters that",
        "are not the letters they look like — the columns that separate a rewrite from a sabotage.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    from eval.data.generated_abstracts import ABSTRACTS

    report = measure(list(ABSTRACTS), args.tier, args.n)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
