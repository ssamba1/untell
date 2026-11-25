"""The evidence brief: what one detector verdict on one document is worth.

Built for the person on the receiving end of a flag, and for whoever has to weigh it — an
advisor, an integrity panel, counsel. It contains only things that can be checked:

1. the document's own measurable properties (length, register warnings);
2. the verdict-stability test run on the document itself (:mod:`.stability`);
3. published error rates for the named detector, each with its source (:mod:`.rates`);
4. the Bayes arithmetic that turns a false-positive rate into what a flag actually implies, and
   the per-person rollup for someone who submitted many documents (:mod:`.stats`);
5. the questions a careful reviewer should ask before relying on the score.

It measures the detector, not the writer, and says so on its face. It is not legal advice.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import html
import json
import re

from . import rates as _rates
from . import stats as _stats

__all__ = ["build_brief", "render_markdown", "render_html", "QUESTIONS"]

DEFAULT_PRIORS = (0.01, 0.05, 0.10, 0.25, 0.50)

QUESTIONS = (
    "What is this detector's measured false-positive rate on human text of this length, register "
    "and writer background — and on how many documents was it measured?",
    "Which model version produced the score, on what date? Has the result been reproduced on a "
    "second run or a second detector?",
    "Is the score the only evidence? Does the institution's own policy permit a detector score "
    "as sole or primary evidence?",
    "Does the verdict survive formatting-only changes to the same words (see the stability "
    "section)? If not, what is it measuring?",
    "Is there process evidence — drafts, version history, notes, sources — and was it requested "
    "before the score was relied on?",
)

CONTEXT = (
    "Washington State University reportedly cancelled Turnitin's AI detection in February 2026, citing that "
    "33% of its 2023–25 AI-misconduct cases were dismissed where the detector was the only "
    "evidence. Several other universities have disabled AI detection (Waterloo, Curtin, the "
    "University of New England)."
)

_WORDS = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def _length_note(words: int) -> str | None:
    if words < 150:
        return ("Under 150 words. Detector accuracy degrades sharply on short text; most vendors "
                "recommend against relying on scores below a few hundred words.")
    if words < 300:
        return "Under 300 words: below the length at which most published accuracy figures were measured."
    return None


def build_brief(
    text: str,
    detector: str,
    *,
    observed_score: float | None = None,
    observed_flagged: bool | None = None,
    detector_version: str | None = None,
    stability: dict | None = None,
    fpr: float | None = None,
    tpr: float = 0.90,
    priors: tuple[float, ...] = DEFAULT_PRIORS,
    documents: int = 1,
    writer: str = "general",
    cohort: int = 1000,
    now: _dt.datetime | None = None,
) -> dict:
    """Assemble the brief as a JSON-serialisable dict.

    ``fpr`` overrides the published estimate; with neither, the Bayes section says it cannot be
    computed rather than inventing a rate. ``tpr`` is an assumption and labelled as one.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    words = len(_WORDS.findall(text))
    published = _rates.rates_for(detector)
    est = _rates.best_fpr_estimate(detector, population=writer)
    fpr_used, fpr_source = (fpr, "supplied by the user") if fpr is not None else (
        (est["fpr"], est["source"]) if est else (None, None))

    bayes: dict = {"tpr_assumed": tpr, "fpr": fpr_used, "fpr_source": fpr_source,
                   "writer_population": writer}
    if fpr_used is not None:
        bayes["by_prior"] = [
            {"prior": p,
             "p_ai_given_flag": _stats.posterior_ai_given_flag(fpr_used, tpr, p),
             "p_human_given_flag": 1.0 - _stats.posterior_ai_given_flag(fpr_used, tpr, p)}
            for p in priors
        ]
        bayes["honest_writer"] = _stats.honest_writer_table(
            fpr_used, ks=tuple(sorted({1, 5, 10, 20, 40, max(1, documents)})), cohort=cohort)
        bayes["this_writer"] = {
            "documents": documents,
            "p_at_least_one_false_flag": _stats.p_any_false_flag(fpr_used, max(1, documents)),
        }

    scored_by = ((stability or {}).get("scorer") or {})
    # untell's own ensemble standing in for the named detector: its scores test whether *untell*
    # is stable on this document, which says nothing about the named detector's verdict. Before
    # this, `brief --name turnitin --detector local` (and the API/MCP default) printed untell's
    # score as "Score: 0.176 — clear" under "Detector: Turnitin".
    substitute = (scored_by.get("kind") == "local"
                  and not (detector or "").strip().lower().startswith(("local", "untell")))
    if not substitute:
        if observed_score is None and stability:
            observed_score = stability.get("base", {}).get("score")
        if observed_flagged is None and stability:
            observed_flagged = stability.get("base", {}).get("flagged")

    return {
        "kind": "untell.evidence_brief",
        "schema": 1,
        "generated_at": now.isoformat(timespec="seconds"),
        "untell_version": _version(),
        "detector": {"name": detector, "version": detector_version},
        "document": {
            "words": words,
            "characters": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "length_note": _length_note(words),
        },
        "observed": {"score": observed_score, "flagged": observed_flagged},
        "stability": stability,
        "stability_scored_by": {"name": scored_by.get("name"), "kind": scored_by.get("kind"),
                                "is_the_named_detector": not substitute} if stability else None,
        "published_rates": published,
        "bayes": bayes,
        "questions": list(QUESTIONS),
        "context": CONTEXT,
        "disclaimer": ("This brief measures the detector, not the writer. It is not legal advice. "
                       "Published figures describe the detector version and text that were tested."),
    }


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("untell")
    except Exception:
        return "dev"


def _pct(x: float | None, digits: int = 1) -> str:
    if x is None or x != x:
        return "n/a"
    return f"{100 * x:.{digits}f}%"


# --- Markdown --------------------------------------------------------------------------------------

def render_markdown(b: dict) -> str:
    d, doc, obs, bay = b["detector"], b["document"], b["observed"], b["bayes"]
    L: list[str] = []
    L.append("# Detector evidence brief")
    L.append("")
    L.append(f"*Generated {b['generated_at']} by untell {b['untell_version']}. {b['disclaimer']}*")
    L.append("")
    L.append("## The verdict under review")
    L.append("")
    L.append(f"- **Detector:** {d['name']}" + (f" (version {d['version']})" if d.get("version") else
                                               " (version not recorded — ask for it)"))
    if obs.get("score") is not None:
        L.append(f"- **Score:** {obs['score']:.3f}" + (
            f" — {'flagged' if obs['flagged'] else 'not flagged'}" if obs.get("flagged") is not None
            else ""))
    L.append(f"- **Document:** {doc['words']} words · SHA-256 `{doc['sha256'][:16]}…`")
    if doc.get("length_note"):
        L.append(f"- **Length:** {doc['length_note']}")
    L.append("")

    st = b.get("stability")
    L.append("## 1. Does the verdict survive edits that cannot change authorship?")
    L.append("")
    if st:
        sb = b.get("stability_scored_by") or {}
        if sb and not sb.get("is_the_named_detector", True):
            L.append(f"> **These scores are untell's own detector (`{sb.get('name')}`), not "
                     f"{b['detector']['name']}'s.** They show whether untell's verdict is stable on "
                     f"this document, not whether {b['detector']['name']}'s is. To test "
                     f"{b['detector']['name']}, score each variant in it (`untell variants`) and pass "
                     "the scores.")
            L.append("")
        L.append(f"> {st['summary'].get('finding', '')}")
        L.append("")
        if sb.get("name"):
            L.append(f"Scored by: `{sb['name']}`.")
            L.append("")
        L.append("| id | edit | tier | chars changed | score | verdict |")
        L.append("|---|---|---|---:|---:|---|")
        for r in st["variants"]:
            if r["noop"]:
                continue
            sc = "—" if r["score"] is None else f"{r['score']:.3f}"
            fl = "—" if r["flagged"] is None else ("flagged" if r["flagged"] else "clear")
            flip = " ⚑" if (r["flagged"] is not None and st["base"].get("flagged") is not None
                            and r["flagged"] != st["base"]["flagged"]) else ""
            L.append(f"| {r['id']} | {r['label']} | {r['tier']} | {r['chars_changed']} | {sc} | "
                     f"{fl}{flip} |")
        L.append("")
        L.append("⚑ = verdict differs from the original. *null* edits keep exactly the same words "
                 "(checked mechanically); *light* edits are routine copy-editing.")
    else:
        L.append("Not run. Run `untell brief --detector <spec>` against the detector, or record its "
                 "scores for each variant by hand (`untell variants`, then `--detector manual:scores.csv`).")
    L.append("")

    L.append("## 2. What the detector's published error rates are")
    L.append("")
    if b["published_rates"]:
        L.append("| figure | condition | source | checked |")
        L.append("|---|---|---|---|")
        for e in b["published_rates"]:
            v = e.get("value")
            fig = (_pct(v) if v is not None else f"< {_pct(e.get('upper'))}") + (
                f" (n={e['n']})" if e.get("n") else "")
            L.append(f"| {e['metric'].replace('_', ' ')}: {fig} | {e.get('condition', '')} | "
                     f"[{e['source']}]({e['url']}) | {e.get('checked', '')} |")
    else:
        L.append(f"No published figures for `{d['name']}` are on file. Ask the vendor or the "
                 "institution for its measured false-positive rate, and the n it was measured on.")
    L.append("")

    L.append("## 3. What a flag implies (Bayes)")
    L.append("")
    if bay.get("fpr") is None:
        L.append("No false-positive rate is available, so this cannot be computed. A flag cannot be "
                 "interpreted as a probability of AI authorship without one.")
    else:
        pop = bay.get("writer_population", "general")
        if pop != "general":
            L.append(f"Writer population: **{pop}** — the rate below was measured on that population.")
            L.append("")
        L.append(f"Using a false-positive rate of **{_pct(bay['fpr'], 2)}** ({bay['fpr_source']}) "
                 f"and an *assumed* true-positive rate of {_pct(bay['tpr_assumed'], 0)}. The answer "
                 "depends on how common AI-written work is among the documents being screened:")
        L.append("")
        L.append("| if this share of screened work is AI-written | P(AI \\| flagged) | P(human \\| flagged) |")
        L.append("|---:|---:|---:|")
        for r in bay["by_prior"]:
            L.append(f"| {_pct(r['prior'], 0)} | {_pct(r['p_ai_given_flag'])} | "
                     f"{_pct(r['p_human_given_flag'])} |")
        L.append("")
        L.append("A false-positive rate is P(flag | human), not P(human | flag). Reading one as the "
                 "other is the prosecutor's fallacy.")
        L.append("")
        tw = bay["this_writer"]
        L.append(f"**Per person, not per document.** An honest writer who submits "
                 f"{tw['documents']} document(s) has a {_pct(tw['p_at_least_one_false_flag'])} "
                 "chance of at least one false flag at this rate:")
        L.append("")
        L.append("| documents per writer | P(≥1 false flag) | honest writers flagged per 1,000 |")
        L.append("|---:|---:|---:|")
        for r in bay["honest_writer"]:
            n_key = next(k for k in r if k.startswith("flagged_per_"))
            L.append(f"| {r['documents']} | {_pct(r['p_at_least_one_false_flag'])} | "
                     f"{r[n_key]:.0f} |")
    L.append("")

    L.append("## 4. Questions to ask before relying on the score")
    L.append("")
    for q in b["questions"]:
        L.append(f"- {q}")
    L.append("")
    L.append(f"*Context:* {b['context']}")
    L.append("")
    L.append("---")
    L.append("Generated by [untell](https://github.com/ssamba1/untell), an open-source "
             "detector-auditing toolkit. The document's text is not included in this brief; its "
             "SHA-256 identifies it.")
    return "\n".join(L) + "\n"


# --- HTML --------------------------------------------------------------------------------------------

_CSS = """
:root{--bg:#fbfaf7;--fg:#1c1b19;--muted:#5f5b53;--line:#d9d4c9;--accent:#8a3b12;--flag:#b42318;--ok:#22663a;--card:#fff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151412;--fg:#ece8df;--muted:#a39d91;--line:#38352f;--accent:#f0a36b;--flag:#ff8a7a;--ok:#7fd49a;--card:#1d1c19}}
:root[data-theme="dark"]{--bg:#151412;--fg:#ece8df;--muted:#a39d91;--line:#38352f;--accent:#f0a36b;--flag:#ff8a7a;--ok:#7fd49a;--card:#1d1c19}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,'Iowan Old Style',serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 64px}h1{font-size:2rem;margin:0 0 4px}
h2{font-size:1.2rem;margin:36px 0 10px;border-bottom:1px solid var(--line);padding-bottom:4px}
.meta{color:var(--muted);font-size:.9rem}.finding{border-left:4px solid var(--accent);background:var(--card);padding:12px 16px;margin:12px 0}
table{border-collapse:collapse;width:100%;font:14px/1.4 ui-sans-serif,system-ui,sans-serif;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}td.n{text-align:right;font-variant-numeric:tabular-nums}
.flip{color:var(--flag);font-weight:600}.clear{color:var(--ok)}a{color:var(--accent)}
ul{padding-left:20px}footer{margin-top:40px;color:var(--muted);font-size:.85rem}
@media print{body{background:#fff;color:#000}main{padding:0}a{color:#000}}
"""


def render_html(b: dict) -> str:
    e = html.escape
    d, doc, obs, bay = b["detector"], b["document"], b["observed"], b["bayes"]
    P: list[str] = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Detector Evidence Brief</title>", f"<style>{_CSS}</style></head><body><main>",
        "<h1>Detector evidence brief</h1>",
        f"<p class='meta'>Generated {e(b['generated_at'])} by untell {e(b['untell_version'])}. "
        f"{e(b['disclaimer'])}</p>",
        "<h2>The verdict under review</h2><ul>",
        f"<li><b>Detector:</b> {e(d['name'])} "
        + (f"(version {e(d['version'])})" if d.get("version") else
           "<i>(version not recorded — ask for it)</i>") + "</li>",
    ]
    if obs.get("score") is not None:
        verdict = "" if obs.get("flagged") is None else (" — flagged" if obs["flagged"] else " — not flagged")
        P.append(f"<li><b>Score:</b> {obs['score']:.3f}{verdict}</li>")
    P.append(f"<li><b>Document:</b> {doc['words']} words · SHA-256 <code>{doc['sha256'][:16]}…</code></li>")
    if doc.get("length_note"):
        P.append(f"<li><b>Length:</b> {e(doc['length_note'])}</li>")
    P.append("</ul>")

    st = b.get("stability")
    P.append("<h2>1. Does the verdict survive edits that cannot change authorship?</h2>")
    if st:
        sb = b.get("stability_scored_by") or {}
        if sb and not sb.get("is_the_named_detector", True):
            P.append(f"<p class='finding'><b>These scores are untell's own detector "
                     f"({e(sb.get('name'))}), not {e(b['detector']['name'])}'s.</b> They show whether "
                     f"untell's verdict is stable on this document, not whether "
                     f"{e(b['detector']['name'])}'s is.</p>")
        P.append(f"<p class='finding'>{e(st['summary'].get('finding', ''))}</p>")
        if sb.get("name"):
            P.append(f"<p class='meta'>Scored by: {e(sb['name'])}</p>")
        P.append("<table><thead><tr><th>id</th><th>edit</th><th>tier</th><th>chars</th><th>score</th>"
                 "<th>verdict</th></tr></thead><tbody>")
        bf = st["base"].get("flagged")
        for r in st["variants"]:
            if r["noop"]:
                continue
            sc = "—" if r["score"] is None else f"{r['score']:.3f}"
            if r["flagged"] is None:
                cell = "—"
            else:
                flipped = bf is not None and r["flagged"] != bf
                word = "flagged" if r["flagged"] else "clear"
                cell = f"<span class='{'flip' if flipped else 'clear'}'>{word}{' ⚑' if flipped else ''}</span>"
            P.append(f"<tr><td>{e(r['id'])}</td><td>{e(r['label'])}</td><td>{e(r['tier'])}</td>"
                     f"<td class='n'>{r['chars_changed']}</td><td class='n'>{sc}</td><td>{cell}</td></tr>")
        P.append("</tbody></table><p class='meta'>⚑ verdict differs from the original. <i>null</i> "
                 "edits keep exactly the same words (checked mechanically).</p>")
    else:
        P.append("<p>Not run.</p>")

    P.append("<h2>2. Published error rates for this detector</h2>")
    if b["published_rates"]:
        P.append("<table><thead><tr><th>figure</th><th>condition</th><th>source</th><th>checked</th>"
                 "</tr></thead><tbody>")
        for r in b["published_rates"]:
            v = r.get("value")
            fig = (_pct(v) if v is not None else f"&lt; {_pct(r.get('upper'))}") + (
                f" (n={r['n']})" if r.get("n") else "")
            P.append(f"<tr><td>{e(r['metric'].replace('_', ' '))}: {fig}</td><td>{e(r.get('condition', ''))}"
                     f"</td><td><a href='{e(r['url'])}'>{e(r['source'])}</a></td>"
                     f"<td>{e(r.get('checked', ''))}</td></tr>")
        P.append("</tbody></table>")
    else:
        P.append(f"<p>No published figures for <code>{e(d['name'])}</code> are on file.</p>")

    P.append("<h2>3. What a flag implies</h2>")
    if bay.get("fpr") is None:
        P.append("<p>No false-positive rate is available, so a flag cannot be turned into a "
                 "probability of AI authorship.</p>")
    else:
        P.append(f"<p>False-positive rate <b>{_pct(bay['fpr'], 2)}</b> ({e(str(bay['fpr_source']))}); "
                 f"true-positive rate <i>assumed</i> {_pct(bay['tpr_assumed'], 0)}.</p>")
        P.append("<table><thead><tr><th>share of screened work that is AI-written</th>"
                 "<th>P(AI | flagged)</th><th>P(human | flagged)</th></tr></thead><tbody>")
        for r in bay["by_prior"]:
            P.append(f"<tr><td class='n'>{_pct(r['prior'], 0)}</td><td class='n'>{_pct(r['p_ai_given_flag'])}"
                     f"</td><td class='n'>{_pct(r['p_human_given_flag'])}</td></tr>")
        P.append("</tbody></table><p>A false-positive rate is P(flag | human), not P(human | flag).</p>")
        tw = bay["this_writer"]
        P.append(f"<p><b>Per person:</b> an honest writer who submits {tw['documents']} document(s) has "
                 f"a <b>{_pct(tw['p_at_least_one_false_flag'])}</b> chance of at least one false flag.</p>")
        P.append("<table><thead><tr><th>documents per writer</th><th>P(≥1 false flag)</th>"
                 "<th>honest writers flagged per 1,000</th></tr></thead><tbody>")
        for r in bay["honest_writer"]:
            n_key = next(k for k in r if k.startswith("flagged_per_"))
            P.append(f"<tr><td class='n'>{r['documents']}</td><td class='n'>{_pct(r['p_at_least_one_false_flag'])}"
                     f"</td><td class='n'>{r[n_key]:.0f}</td></tr>")
        P.append("</tbody></table>")

    P.append("<h2>4. Questions to ask before relying on the score</h2><ul>")
    P.extend(f"<li>{e(q)}</li>" for q in b["questions"])
    P.append(f"</ul><p class='meta'>{e(b['context'])}</p>")
    P.append("<footer>Generated by <a href='https://github.com/ssamba1/untell'>untell</a>, an "
             "open-source detector-auditing toolkit. The document's text is not included; its "
             "SHA-256 identifies it.</footer>")
    payload = json.dumps(b).replace("</", "<\\/")  # cannot close the script element early
    P.append(f"<script type='application/json' id='untell-brief'>{payload}</script>")
    P.append("</main></body></html>")
    return "\n".join(P)
