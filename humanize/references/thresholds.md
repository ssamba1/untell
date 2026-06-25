# Thresholds & loop defaults

These are the knobs the `humanize` loop uses. Override per-run if the user asks.

| Parameter | Default | Meaning | Rationale |
|---|---|---|---|
| `threshold` | `0.30` | Stop when the **max** detector P(AI) drops below this. | Below ~0.3, most proxy detectors no longer flag text. The loop drives the *max* across detectors, so this is a strict multi-detector bar. |
| `similarity bar` | `0.76` embedding / `0.50` token-overlap | A rewrite is only acceptable if similarity to the original stays ≥ this. **Metric-aware** — the two metrics live on different scales. | `0.76` is the P-SP threshold (semantic embeddings, full tier). The lite token-overlap fallback scores faithful paraphrases far lower, so it uses `0.50` and is treated as *advisory* (`confidence: low`) — it cannot actually judge meaning. `quality.py` reports the right bar + `passes`; trust those. |
| `max iterations` | `5` | Hard cap on rewrite rounds. | The closed-loop evasion literature (arXiv 2506.07001) converges within ~3–5 iterations; more rounds risk meaning drift for little gain. |
| aggregation | `max` | Which detector score the stop condition uses. | Targeting the hardest detector forces genuine multi-detector evasion (report gap #3), not just fooling the weakest one. |

## Tuning guidance

- **Stricter evasion:** lower `threshold` to `0.15–0.20`. Expect more iterations and more pressure
  on similarity — watch the quality gate.
- **Tighter meaning preservation:** raise the `similarity bar` to `0.80+`. Fewer aggressive
  rewrites will pass; the loop may stop while still mildly flagged.
- **Quick demo:** raise `threshold` to `0.50` and cap iterations at `3`.

## Reading the score JSON

`humanize-score` / `score.py` emit:

- `tier` — `lite` (heuristic, weak), `full` (RoBERTa-OpenAI + MAGE + GPT-2 PPL, real CPU signal),
  or `heavy` (adds Binoculars, GPU). Always report which tier ran.
- `detectors` — per-detector P(AI); use these to decide *what* to change in the rewrite.
- `max` / `mean` — aggregate proxies; the loop drives `max`.
- `flagged` — `true` when `max >= threshold` (keep rewriting).
