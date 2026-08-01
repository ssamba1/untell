# Thresholds & loop defaults

These are the knobs the `untell` loop uses. Override per-run if the user asks.

| Parameter | Default | Meaning | Rationale |
|---|---|---|---|
| `threshold` | `0.30` | Stop when the **max** detector P(AI) drops below this. | Below ~0.3, most proxy detectors no longer flag text. The loop drives the *max* across detectors, so this is a strict multi-detector bar. |
| `similarity bar` | `0.88` BERTScore / `0.76` embedding / `0.50` token-overlap | A rewrite is only acceptable if similarity to the original stays ≥ this. **Metric-aware** — the three metrics live on different scales. | `0.76` is the P-SP threshold (semantic embeddings). `0.88` is the BERTScore-F1 bar (rescaled with baseline), used when `bert-score` is installed — its recall term catches dropped claims a single cosine averages away. The lite token-overlap fallback scores faithful paraphrases far lower, so it uses `0.50` and is treated as *advisory* (`confidence: low`) — it cannot actually judge meaning. `quality.py` reports the right bar + `passes`; trust those, never a remembered number. |
| `meaning gate` (NLI) | contradiction `< 0.50`, entailment `≥ 0.005` | A rewrite is rejected outright if it contradicts the original or fails to entail it, **regardless of similarity or detector score**. | Similarity cannot separate a faithful reword from a reversal: "runs faster" → "runs slower" scores `0.974` cosine, far above the `0.76` bar, while genuinely faithful register shifts score lower. Entailment separates them — that same inversion scores `0.998` contradiction. Run `scripts/entailment.py` (exit `0` preserved, `1` rejected). Unavailable without the `.[full]` extra, in which case it is skipped, not failed. |
| `max iterations` | `5` | Hard cap on rewrite rounds. | The closed-loop evasion literature (arXiv 2506.07001) converges within ~3–5 iterations; more rounds risk meaning drift for little gain. |
| aggregation | `max` | Which detector score the stop condition uses. | Targeting the hardest detector forces genuine multi-detector evasion (report gap #3), not just fooling the weakest one. |

## Tuning guidance

- **Stricter evasion:** lower `threshold` to `0.15–0.20`. Expect more iterations and more pressure
  on similarity — watch the quality gate.
- **Tighter meaning preservation:** install the `.[full]` extra so the NLI meaning gate runs —
  that is the lever that actually catches reversals, and it costs no evasion strength because it
  rejects only rewrites that changed the claim. Raising the `similarity bar` to `0.80+` is the
  blunter knob: it also rejects faithful rewrites that merely reword heavily, so fewer aggressive
  rewrites pass and the loop may stop while still mildly flagged.
- **Quick demo:** raise `threshold` to `0.50` and cap iterations at `3`.

## Reading the score JSON

`untell-score` / `score.py` emit:

- `tier` — `lite` (heuristic, weak), `full` (RoBERTa-OpenAI + HC3-RoBERTa + Fast-DetectGPT + GPT-2
  perplexity; MAGE when its config loads — real CPU signal), or `heavy` (adds Binoculars, GPU).
  Always report which tier ran.
- `detectors` — per-detector P(AI); use these to decide *what* to change in the rewrite.
- `max` / `mean` — aggregate proxies; the loop drives `max`.
- `flagged` — `true` when `max >= threshold` (keep rewriting).
