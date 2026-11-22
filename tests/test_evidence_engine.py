"""The evidence engine: statistics, null edits, stability, brief, report card, drift, capsule.

Every test here runs on the standard library alone (fake scorers stand in for detectors), so the
audit half of the product is pinned without a model download.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import pytest

from untell.evidence import stats as S
from untell.evidence.brief import build_brief, render_html, render_markdown
from untell.evidence.corpus import corpus_fingerprint, git_time_capsule, load_corpus, prose_of
from untell.evidence.perturb import light_variants, null_variants, same_words
from untell.evidence.rates import best_fpr_estimate, rates_for
from untell.evidence.report_card import drift, render_report_card_markdown, run_report_card
from untell.evidence.scorers import _parse_score, load_manual, resolve_scorer, scorer_from_function
from untell.evidence.stability import chars_changed, measure_stability

SAMPLE = (
    'When I started the project in March I didn\'t expect it to take the whole semester. The first '
    '"prototype" was a mess -- three spreadsheets and a notebook full of arrows... My advisor said '
    "it looked like a crime board, which was fair.\n\nMost of the work ended up being cleaning data. "
    "The color-coded categories, the dates and the zips all needed fixing. It's done now."
)


# --- stats -----------------------------------------------------------------------------------------

def test_wilson_zero_of_forty_is_not_never_wrong():
    lo, hi = S.wilson_interval(0, 40)
    assert lo == 0.0
    assert 0.08 < hi < 0.095  # the honest upper bound on "0 of 40"


def test_wilson_matches_known_value():
    lo, hi = S.wilson_interval(5, 30)
    assert lo == pytest.approx(0.0734, abs=1e-3)
    assert hi == pytest.approx(0.3365, abs=1e-3)


def test_posterior_is_not_one_minus_fpr():
    # FPR 1%, TPR 90%, base rate 5%: a flag is right ~82.6% of the time, not 99%.
    assert S.posterior_ai_given_flag(0.01, 0.90, 0.05) == pytest.approx(0.8257, abs=1e-3)


def test_per_person_risk_compounds():
    assert S.p_any_false_flag(0.01, 30) == pytest.approx(1 - 0.99**30)
    assert S.expected_false_flags(0.01, 1, 1000) == pytest.approx(10)


def test_probability_inputs_are_validated():
    with pytest.raises(ValueError):
        S.posterior_ai_given_flag(1.5, 0.9, 0.1)
    with pytest.raises(ValueError):
        S.p_any_false_flag(float("nan"), 3)


def test_recall_at_fpr_holds_the_cap():
    humans = [i / 100 for i in range(100)]  # 0.00 .. 0.99
    ais = [0.5, 0.97, 0.995, 0.999]
    r = S.recall_at_fpr(ais, humans, 0.02)
    assert r["achieved_fpr"] <= 0.02
    assert r["recall"] == pytest.approx(0.5)


def test_auroc_extremes_and_ties():
    assert S.auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert S.auroc([0.1], [0.9]) == 0.0
    assert S.auroc([0.5], [0.5]) == 0.5
    assert S.auroc([], [0.1]) is None


def test_flip_rate_excludes_unscored():
    r = S.flip_rate(True, [True, False, None, False])
    assert r == {**r, "variants_scored": 3, "variants_unscored": 1, "flips": 2}
    assert r["flip_rate"] == pytest.approx(2 / 3)


# --- perturbations -----------------------------------------------------------------------------------

def test_every_null_variant_keeps_the_same_words():
    vs = null_variants(SAMPLE)
    assert {v.id for v in vs} >= {"N1", "N3", "N4", "N5", "N6", "N8"}
    for v in vs:
        assert same_words(SAMPLE, v.text), v.id


def test_null_variants_actually_change_something():
    changed = [v for v in null_variants(SAMPLE) if not v.noop]
    assert len(changed) >= 6
    assert "“" in next(v.text for v in changed if v.id == "N1")
    assert "…" in next(v.text for v in changed if v.id == "N5")
    assert " " not in next(v.text for v in changed if v.id == "N8")


def test_noop_variants_are_marked():
    plain = "A plain sentence with nothing to change in it at all"
    assert next(v for v in null_variants(plain) if v.id == "N2").noop


def test_light_variants_are_not_word_identical():
    vs = {v.id: v for v in light_variants(SAMPLE)}
    assert "do not" in vs["L1"].text or "did not" in vs["L1"].text
    assert "colour" in vs["L4"].text
    assert "the dates, and the zips" in vs["L3"].text
    assert not same_words(SAMPLE, vs["L1"].text)


def test_same_words_rejects_a_changed_word():
    assert not same_words("the cat sat", "the dog sat")
    assert same_words("it's “fine”", "it’s \"fine\"")


# --- scorers -----------------------------------------------------------------------------------------

def test_parse_score_forms():
    assert _parse_score("0.73") == 0.73
    assert _parse_score('{"ai_likelihood": 0.4}') == 0.4
    assert _parse_score("AI: 87%") == pytest.approx(0.87)
    assert _parse_score("") is None
    assert _parse_score("no number") is None


def test_cmd_scorer_round_trip(tmp_path):
    script = tmp_path / "det.py"
    script.write_text("import sys; t=sys.stdin.read(); print(0.9 if '\\u201c' in t else 0.2)",
                      encoding="utf-8")
    sc = resolve_scorer(f"cmd:{sys.executable} {script}")
    assert sc.verdict('say "hi"').flagged is False
    assert sc.verdict("say “hi”").flagged is True


def test_manual_scorer_csv_and_percentages(tmp_path):
    p = tmp_path / "scores.csv"
    p.write_text("id,score,flagged\nbase,87,\nN1,12,no\nN3,,yes\n", encoding="utf-8")
    rows = load_manual(p)
    assert rows["base"]["score"] == pytest.approx(0.87)
    sc = resolve_scorer(f"manual:{p}")
    assert sc.verdict("x", "base").flagged is True
    assert sc.verdict("x", "N1").flagged is False
    assert sc.verdict("x", "N3").flagged is True
    assert sc.verdict("x", "N9").score is None


def test_unknown_detector_names_the_options():
    with pytest.raises(ValueError, match="manual:"):
        resolve_scorer("definitely-not-a-detector")


def test_failing_scorer_is_unscored_not_a_crash():
    def boom(t):
        raise RuntimeError("api down")
    v = scorer_from_function(boom).verdict("text")
    assert v.score is None and v.flagged is None and "api down" in v.detail["error"]


# --- stability ---------------------------------------------------------------------------------------

def _quote_sensitive(text: str) -> float:
    """A deliberately broken detector: reads curly quotes as human."""
    return 0.2 if "“" in text else 0.8


def test_stability_catches_a_typography_sensitive_detector():
    res = measure_stability(SAMPLE, scorer_from_function(_quote_sensitive, "fake")).to_dict()
    null = res["summary"]["null"]
    assert res["base"]["flagged"] is True
    assert null["flips"] >= 1
    assert null["smallest_flip"]["id"] == "N1"
    assert "same words" in res["summary"]["finding"]


def test_stability_reports_a_stable_detector_honestly():
    res = measure_stability(SAMPLE, scorer_from_function(lambda t: 0.9)).to_dict()
    assert res["summary"]["null"]["flips"] == 0
    assert "not evidence either way" in res["summary"]["finding"]


def test_noops_are_never_rescored():
    calls = []

    def f(t):
        calls.append(t)
        return 0.5

    measure_stability("plain words only here", scorer_from_function(f), tiers=("null",))
    assert len(calls) == 1 + sum(1 for v in null_variants("plain words only here") if not v.noop)


def test_chars_changed():
    assert chars_changed("abc", "abc") == 0
    assert chars_changed("a b", "a  b") == 1


def test_stability_rejects_empty_text():
    with pytest.raises(ValueError):
        measure_stability("   ", scorer_from_function(lambda t: 0.5))


# --- rates + brief -----------------------------------------------------------------------------------

def test_every_published_rate_names_a_source():
    for name in ("pangram", "gptzero", "originality", "turnitin"):
        entries = rates_for(name)
        assert entries, name
        for e in entries:
            assert e["url"].startswith("https://") and e["source"] and e["checked"]


def test_conservative_estimate_never_uses_an_observed_zero():
    est = best_fpr_estimate("pangram")
    assert est is not None and est["fpr"] > 0


def test_brief_does_not_contain_the_document():
    stab = measure_stability(SAMPLE, scorer_from_function(_quote_sensitive, "fake")).to_dict()
    b = build_brief(SAMPLE, "gptzero", stability=stab, documents=10)
    blob = json.dumps(b) + render_markdown(b) + render_html(b)
    assert "crime board" not in blob  # the text never appears, only its hash
    assert b["document"]["sha256"] in blob


def test_brief_sections_and_bayes():
    b = build_brief(SAMPLE, "turnitin", observed_score=0.91, observed_flagged=True, documents=30)
    md = render_markdown(b)
    for heading in ("## 1.", "## 2.", "## 3.", "## 4."):
        assert heading in md
    assert "prosecutor's fallacy" in md
    assert b["bayes"]["this_writer"]["p_at_least_one_false_flag"] == pytest.approx(1 - 0.99**30)


def test_brief_without_a_rate_refuses_to_guess():
    b = build_brief(SAMPLE, "some-unknown-detector")
    assert b["bayes"]["fpr"] is None
    assert "cannot be computed" in render_markdown(b)


def test_brief_html_embeds_parseable_json():
    b = build_brief(SAMPLE, "gptzero")
    page = render_html(b)
    start = page.index("id='untell-brief'>") + len("id='untell-brief'>")
    payload = page[start:page.index("</script>", start)]
    assert json.loads(payload)["kind"] == "untell.evidence_brief"
    assert "prefers-color-scheme: dark" in page and "@media print" in page


# --- corpus + report card + drift ------------------------------------------------------------------

def test_load_corpus_formats(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        json.dumps({"text": "hello there", "group": "esl", "author": "p1"}) + "\n"
        + json.dumps({"text": "x", "label": "1"}) + "\n", encoding="utf-8")
    docs = load_corpus(tmp_path / "a.jsonl")
    assert docs[0]["group"] == "esl" and docs[0]["author"] == "p1" and docs[1]["label"] == "ai"
    d = tmp_path / "dir" / "grade9"
    d.mkdir(parents=True)
    (d / "e1.txt").write_text("an essay", encoding="utf-8")
    assert load_corpus(tmp_path / "dir")[0]["group"] == "grade9"
    assert corpus_fingerprint(docs) == corpus_fingerprint(list(reversed(docs)))


def _docs(n_h: int = 30, n_ai: int = 10) -> list[dict]:
    words = " ".join(["word"] * 200)
    out = [{"id": f"h{i}", "text": f"{words} human {i}", "label": "human",
            "group": "esl" if i % 3 == 0 else "native", "author": f"p{i // 3}"} for i in range(n_h)]
    out += [{"id": f"a{i}", "text": f"{words} machine {i}", "label": "ai", "group": "ai"}
            for i in range(n_ai)]
    return out


def _biased(text: str) -> float:
    # flags every third human document (the 'esl' group) and every AI one
    if "machine" in text:
        return 0.95
    i = int(text.rsplit(" ", 1)[1])
    return 0.9 if i % 3 == 0 else 0.1


def test_report_card_finds_the_biased_slice():
    card = run_report_card(scorer_from_function(_biased, "biased"), _docs(), stability_sample=3)
    f = card["false_positive_rate"]
    assert f["by_group"]["esl"]["rate"] == 1.0
    assert f["by_group"]["native"]["rate"] == 0.0
    assert f["overall"]["k"] == 10 and f["overall"]["n"] == 30
    assert card["per_person"]["writers"] == 10
    assert card["detection"]["auroc"] > 0.8
    md = render_report_card_markdown(card)
    assert "group: esl" in md and "95% CI" in md


def test_drift_detects_a_silent_model_change():
    docs = _docs()
    old = run_report_card(scorer_from_function(lambda t: 0.1, "d", version="v1"), docs,
                          stability_sample=0)
    new = run_report_card(scorer_from_function(_biased, "d", version="v2"), docs,
                          stability_sample=0)
    d = drift(old, new)
    assert d["same_corpus"] and d["significant"]
    assert len(d["documents_whose_verdict_changed"]) == 20  # 10 humans + 10 AI flipped
    assert not drift(old, old)["significant"]


def test_report_card_needs_humans():
    with pytest.raises(ValueError):
        run_report_card(scorer_from_function(lambda t: 0.5), _docs(0, 3))


# --- the git time capsule ------------------------------------------------------------------------

def _git(repo, *args, date=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def test_capsule_reads_the_repo_as_it_was(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    old_prose = " ".join(f"Sentence number {i} was written long ago by a person." for i in range(30))
    (repo / "README.md").write_text(f"# Title\n\n{old_prose}\n\n```\ncode block\n```\n",
                                    encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "old", date="2020-01-01T12:00:00")
    (repo / "README.md").write_text("# Title\n\n" + " ".join(["NEWER"] * 300), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "new", date="2024-01-01T12:00:00")
    docs = git_time_capsule(repo, min_words=50)
    assert len(docs) == 1
    assert "NEWER" not in docs[0]["text"] and "code block" not in docs[0]["text"]
    assert docs[0]["provenance"]["commit_date"].startswith("2020-01-01")


def test_capsule_with_no_old_commit_fails_loudly(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.md").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "c", date="2025-01-01T12:00:00")
    with pytest.raises(ValueError, match="no commit before"):
        git_time_capsule(repo)


def test_prose_of_drops_non_prose():
    md = ("# H\n\n- a list item\n\n| t | a |\n\n    indented code\n\n"
          + " ".join(["real prose words"] * 12))
    assert prose_of(md).startswith("real prose words") and "list item" not in prose_of(md)


# --- CLI wiring ----------------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", ["brief", "stability", "variants", "flagmath", "report-card",
                                 "drift", "capsule"])
def test_evidence_commands_are_wired(cmd):
    from untell.scripts.cli import _COMMANDS
    assert cmd in _COMMANDS


def test_variants_command_writes_a_scoring_kit(tmp_path):
    from untell.evidence.cli import variants_main
    doc = tmp_path / "d.txt"
    doc.write_text(SAMPLE, encoding="utf-8")
    assert variants_main(["--file", str(doc), "--out", str(tmp_path / "kit")]) == 0
    rows = (tmp_path / "kit" / "scores.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("id,score,flagged") and rows[1].startswith("base,")
    ids = {r.split(",")[0] for r in rows[1:]}
    for vid in ids - {"base"}:
        assert (tmp_path / "kit" / f"{vid}.txt").exists()


def test_flagmath_json():
    import contextlib
    import io

    from untell.evidence.cli import flagmath_main
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        flagmath_main(["--fpr", "0.01", "--prior", "0.05", "--json"])
    out = json.loads(buf.getvalue())
    assert math.isclose(out["by_prior"][0]["p_ai_given_flag"], 0.8257, abs_tol=1e-3)


# --- Pangram adapter (no network: the HTTP helpers are monkeypatched) ---------------------------

def test_pangram_adapter_submits_polls_and_reads_fraction_ai(monkeypatch):
    from untell.detectors import commercial as C

    monkeypatch.setenv("PANGRAM_API_KEY", "dummy")
    monkeypatch.setattr(C, "_has", lambda *v: True)
    posted, polls = [], iter([
        {"stage": "STAGE_TEXT_INFERENCE"},
        {"stage": "STAGE_SUCCESS", "fraction_ai": 0.25, "fraction_ai_assisted": 0.5,
         "prediction_short": "Mixed", "version": "4.1"},
    ])
    monkeypatch.setattr(C, "_post_json", lambda url, h, body, timeout=45.0:
                        posted.append((url, h, body)) or {"task_id": "t1"})
    monkeypatch.setattr(C, "_get_json", lambda url, h, timeout=30.0: next(polls))
    det = C.PangramDetector(poll_interval=0)
    assert det.score("some text") == 0.25  # AI-assisted is NOT folded into the AI score
    assert posted[0][0].endswith("/task") and posted[0][1]["x-api-key"] == "dummy"
    assert det.version == "4.1" and det.last_result["prediction_short"] == "Mixed"


def test_pangram_failed_task_is_unscored(monkeypatch):
    from untell.detectors import commercial as C

    monkeypatch.setenv("PANGRAM_API_KEY", "dummy")
    monkeypatch.setattr(C, "_has", lambda *v: True)
    monkeypatch.setattr(C, "_post_json", lambda *a, **k: {"task_id": "t1"})
    monkeypatch.setattr(C, "_get_json", lambda *a, **k: {"stage": "STAGE_FAILED"})
    assert C.PangramDetector(poll_interval=0).score("x y z") is None


def test_pangram_is_registered():
    from untell.detectors.commercial import commercial_detectors
    assert "pangram" in {d.name for d in commercial_detectors()}


def test_a_population_specific_rate_is_never_applied_to_everyone():
    general = best_fpr_estimate("originality")
    esl = best_fpr_estimate("originality", population="non-native")
    assert general["population"] == "general" and general["fpr"] < 0.1
    assert esl["population"] == "non-native" and esl["fpr"] > 0.5
    assert best_fpr_estimate("pangram", population="non-native") is None  # nothing measured


def test_the_brief_names_the_writer_population():
    b = build_brief(SAMPLE, "gptzero", writer="non-native", documents=4)
    assert b["bayes"]["writer_population"] == "non-native" and b["bayes"]["fpr"] > 0.5
    assert "Writer population: **non-native**" in render_markdown(b)


def test_a_figure_checked_at_source_beats_one_seen_in_a_summary():
    est = best_fpr_estimate("pangram")
    assert est["checked"] == "primary"
    # Turnitin has only its own vendor claim on file, so that is what is used, and labelled so.
    assert best_fpr_estimate("turnitin")["checked"] == "vendor"


def test_n12_appends_or_strips_a_trailing_space():
    vs = {v.id: v for v in null_variants("A plain sentence.")}
    assert vs["N12"].text == "A plain sentence. " and same_words("A plain sentence.", vs["N12"].text)
    back = {v.id: v for v in null_variants(vs["N12"].text)}
    assert back["N12"].text == "A plain sentence."


def test_scoring_normalisation_drops_a_trailing_space_at_the_end_of_the_text():
    """MEASURED: one trailing space took hc3_roberta from 0.9098 to 0.0010 on a human essay."""
    from untell.detectors.base import RAW_INPUT, normalise_for_scoring

    assert normalise_for_scoring("Ends here.  ") == "Ends here."
    assert normalise_for_scoring("Line one.  \nLine two.\t") == "Line one.\nLine two."
    token = RAW_INPUT.set(True)
    try:
        assert normalise_for_scoring("Ends here.  ") == "Ends here.  "  # raw: untouched
    finally:
        RAW_INPUT.reset(token)
