"""Browser-driven AI-detection via free web UIs (no API key).

Some detectors have no affordable API but a free web checker. This drives a real browser
(Playwright) to paste text into one and read the score — a $0 way to get a real-checker signal.

**Config-driven.** A site is just a ``SiteConfig`` (url + selectors). One built-in ships (ZeroGPT,
confirmed live 2026-06: input ``#textArea``, "Detect Text" button clicked via JS to dodge an ad
overlay, result ``.percentage-div`` → "100%AI GPT*"). Add your own sites without code via a JSON
file — see ``get_browser_checker`` / ``UNTELL_BROWSER_SITES``. ``--browser auto`` picks the first
available checker (built-ins first, then your JSON sites) so verification works with no site name
at all.

Reality check (probed 2026-06): most free detectors are now bot-gated and NOT automatable —
QuillBot (reCAPTCHA), GPTZero web (redirects to a login app), Scribbr/Brandwell (iframe widgets),
Writer (tool removed), Sapling (framework gauge, rate-limited). ZeroGPT is the clean one.

CAVEATS:
  * **Slow + fragile.** Selectors/layouts change; ads/Cloudflare/captchas can block automation.
    For occasional *verification*, NOT a step inside the rewrite loop.
  * **Respect each site's terms.** Automating a free web UI may violate ToS. Low volume, your own
    content, your responsibility.
  * Needs ``pip install -e ".[browser]"`` then ``playwright install chromium``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.detectors.base import clamp01

_PCT = re.compile(r"([\d.]+)\s*%")
# A percentage RANGE ("10%-20%", "10 – 20%"). Read as its upper bound; see parse_ai_percent.
_RANGE = re.compile(r"([\d.]+)\s*%?\s*[-–—]\s*([\d.]+)\s*%")
# Word-bounded, so "again" and "available" stop counting as an AI label and "really" as a human one
# — the old check was a bare `"ai" in window` / `"human" in window` substring test.
# Longest alternative first: the alternation is first-match-wins, so `\bai\b` ahead of
# `ai-generated` would match only "ai" and leave "-generated" outside the label span, throwing off
# every distance measured from it.
_AI_LABEL = re.compile(
    r"ai[-\s]?(?:generated|written|content|score|probability)|machine[-\s]?generated"
    r"|artificial[-\s]?intelligence|chatgpt|artificial|\bai\b|\bgpt\b|\bbot\b"
)
_HUMAN_LABEL = re.compile(r"human[-\s]?(?:written|generated)|\bhuman\b|\breal\b|\bperson\b|\borganic\b")


def _label_spans(raw: str) -> list[tuple[int, int, bool]]:
    """(start, end, is_ai) for every AI/human label in ``raw``."""
    spans = [(m.start(), m.end(), True) for m in _AI_LABEL.finditer(raw)]
    spans += [(m.start(), m.end(), False) for m in _HUMAN_LABEL.finditer(raw)]
    return sorted(spans)


def _gap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Character distance between two spans (0 when they touch or overlap)."""
    return max(0, max(a_start - b_end, b_start - a_end))


def parse_ai_percent(text: str) -> float | None:
    """Pull the first percentage out of a result string and return it as P(AI) in [0, 1].

    e.g. "100%AI GPT*" -> 1.0, "55% AI Generated" -> 0.55. Returns None when no percentage is found,
    or when the one found cannot be trusted to mean *P(AI)*.

    Two guards, both for cases this parser silently got wrong:

    * A **human-labelled** percentage is the INVERSE of what we want. "Human: 45%" means the page
      judged the text 45% human — i.e. 55% AI — and returning 0.45 hands the loop a verdict that is
      wrong in the dangerous direction (it reads as *more human* than reality). Sites word their
      output differently and can change it without notice, so an ambiguous readout is refused rather
      than guessed at; check() then excludes the checker instead of scoring against a fabricated number.
    * A **negative** percentage. The digit-only pattern cannot see a leading sign, so "-10% AI" was
      read as 0.10 — a low score, i.e. "looks human".

    The rule is deliberately asymmetric, because the two error directions are not equally bad here.
    A reading that OVER-states AI is safe: the loop simply keeps rewriting. One that UNDER-states it
    is how text ships believing it passed. So a value above 100 is still clamped to 1.0 (conservative,
    and the pre-existing documented behaviour), while an inverted or negative reading — both of which
    under-state AI — is refused outright.
    """
    raw = text or ""
    lowered = raw.lower()
    numbers = list(_PCT.finditer(raw))
    labels = _label_spans(lowered)

    # Assign each LABEL to its nearest number, rather than asking each number what words happen to
    # sit near it. "Human 45% / AI 55%" puts both words within reach of both figures, which
    # satisfied the old "...and no 'ai' nearby" escape hatch on the first match and returned 0.45 —
    # the human figure delivered as P(AI), wrong in the direction that ships text believing it
    # passed. Assigning labels to numbers is unambiguous whichever side the label sits on, so
    # "Human: 45%", "45% human" and "Human-written: 45%  AI-generated: 55%" all read correctly.
    # Which side of its number does this page put the label on? "AI: 60% Human: 40%" and
    # "45% human, 55% ai" are both unambiguous to a reader and both defeat a pure nearest-neighbour
    # rule, because in each case some label sits marginally closer to the WRONG number. The layout
    # is consistent within a page, so infer it from the tightly-adjacent pairs and let that break
    # the near-ties.
    before = after = 0
    for lstart, lend, _ in labels:
        for m in numbers:
            if lend <= m.start() and m.start() - lend <= 3:
                before += 1
            elif m.end() <= lstart and lstart - m.end() <= 3:
                after += 1
    dominant = None if before == after else (before > after)  # True = labels precede their number

    kinds: dict[int, set[bool]] = {}
    for lstart, lend, is_ai in labels:
        if not numbers:
            break

        def cost(m, _ls=lstart, _le=lend):
            gap = _gap(_ls, _le, m.start(), m.end())
            if dominant is None:
                return gap
            precedes = _le <= m.start()
            return gap + (0 if precedes is dominant else 3)

        nearest = min(numbers, key=cost)
        if _gap(lstart, lend, nearest.start(), nearest.end()) <= 24:
            kinds.setdefault(nearest.start(), set()).add(is_ai)

    ai_labelled = None
    unlabelled = None
    saw_human = any(False in v for v in kinds.values())

    # "AI: 10%-20%" is ONE reading, not two. The dash is a range separator, but the sign check
    # below saw it as a minus, refused the upper bound, and returned 10% — the low end of the
    # range, under-stating AI, which is the single direction this parser refuses everywhere else.
    # Collapse each range onto its lower-bound match (the one a label attaches to) carrying the
    # UPPER value, and drop the second match.
    upper_of: dict[int, float] = {}
    skip: set[int] = set()
    by_start = {m.start(): m for m in numbers}
    for rm in _RANGE.finditer(raw):
        lo, hi = by_start.get(rm.start(1)), by_start.get(rm.start(2))
        if lo is None or hi is None:
            continue
        try:
            upper_of[lo.start()] = float(rm.group(2))
        except ValueError:
            continue
        skip.add(hi.start())

    for m in numbers:
        if m.start() in skip:
            continue
        kind = kinds.get(m.start(), set())
        # The digit pattern cannot see a leading sign, so check the source text for one. A dash
        # directly after a digit or '%' is a range separator and was handled above, not a sign.
        prev = raw[m.start() - 1] if m.start() else ""
        prev2 = raw[m.start() - 2] if m.start() >= 2 else ""
        negative = bool(prev) and prev in "-−" and not (prev2.isdigit() or prev2 == "%")
        try:
            pct = float(m.group(1))
        except ValueError:
            continue
        pct = upper_of.get(m.start(), pct)
        if negative or pct < 0.0:
            continue  # under-states AI — refuse rather than report "looks human"
        if kind == {True} and ai_labelled is None:
            ai_labelled = pct
        elif not kind and unlabelled is None:
            unlabelled = pct

    if ai_labelled is not None:
        # above 100 clamps to 1.0: over-stating AI is the safe direction
        return clamp01(ai_labelled / 100.0)
    if unlabelled is not None and not saw_human:
        return clamp01(unlabelled / 100.0)
    # Either the only readings were human-labelled (inverted, not an AI score) or the page is
    # ambiguous. Refuse rather than guess; check() then excludes the checker instead of scoring
    # the loop against a fabricated number.
    return None


def _split_selectors(spec: str) -> list[str]:
    """Split a comma-separated candidate list, preserving CSS that legitimately contains commas.

    A CSS selector list (``.a, .b``) already means "either", so splitting on commas costs nothing
    semantically — but ``:is(.a, .b)`` and ``[data-x="a,b"]`` do not survive a naive split, so
    commas inside brackets or parentheses are left alone.
    """
    out, depth, cur = [], 0, []
    for ch in spec:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


class SelectorMiss(RuntimeError):
    """No configured selector matched — the site's layout almost certainly changed.

    Distinct from a parse failure (the element was found but held no readable percentage) and from
    a network error, because the three need different responses and a bare Playwright timeout tells
    the operator none of that.
    """

    def __init__(self, site: str, role: str, selectors: list[str], url: str):
        self.site, self.role, self.selectors_tried, self.url = site, role, selectors, url
        super().__init__(
            f"{site}: no {role} element matched any of {selectors!r} on {url}. The site's layout "
            f"has probably changed. Override it without touching this file by passing a JSON site "
            f"config via --sites, where the selector fields accept a comma-separated candidate list."
        )


@dataclass
class SiteConfig:
    """How to drive one free web detector."""

    name: str
    url: str
    # Both selector fields accept a COMMA-SEPARATED list of candidates, tried in order. A free web
    # detector is somebody else's website: it gets redesigned without notice, and when it does, a
    # single hard-coded class name turns the whole checker into a 45-second timeout with no
    # indication that the selector — rather than the network, or the site being down — is at fault.
    # Candidates cost nothing when the first one hits, and `selectors_tried` on the raised error
    # names every one that missed.
    input_selector: str
    input_mode: str = "textarea"  # "textarea" | "contenteditable"
    submit_button_text: str = "detect"  # JS-click the first <button> whose text matches (regex, i)
    result_selector: str = ".result"
    wait_s: float = 45.0
    extra: dict = field(default_factory=dict)

    def input_selectors(self) -> list[str]:
        return _split_selectors(self.input_selector)

    def result_selectors(self) -> list[str]:
        return _split_selectors(self.result_selector)


ZEROGPT = SiteConfig(
    name="zerogpt",
    url="https://www.zerogpt.com/",
    input_selector="#textArea",
    input_mode="textarea",
    submit_button_text="detect text",
    result_selector=".percentage-div",
)


class WebUIChecker:
    """Generic config-driven browser checker. ``check(text)`` returns P(AI) in [0, 1]."""

    def __init__(self, config: SiteConfig):
        self.config = config
        self.name = config.name

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401
        except Exception:
            return False
        return True

    def check(self, text: str, headless: bool = True) -> float:
        from playwright.sync_api import sync_playwright

        c = self.config
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            try:
                page.goto(c.url, wait_until="domcontentloaded", timeout=c.wait_s * 1000)
                # Budget the wait across candidates rather than per candidate: three selectors at
                # the full 45s each would turn one dead site into a 135-second hang.
                inputs = c.input_selectors()
                per_input = max(1.0, c.wait_s / len(inputs))
                filled = None
                for sel in inputs:
                    try:
                        if c.input_mode == "contenteditable":
                            ok = page.evaluate(
                                "([sel, txt]) => { const e = document.querySelector(sel);"
                                " if (!e) return false; e.focus(); e.textContent = txt;"
                                " e.dispatchEvent(new InputEvent('input', {bubbles: true}));"
                                " return true; }",
                                [sel, text],
                            )
                            if not ok:
                                continue
                        else:
                            page.fill(sel, text, timeout=per_input * 1000)
                        filled = sel
                        break
                    except Exception:
                        continue
                if filled is None:
                    raise SelectorMiss(c.name, "input", inputs, c.url)
                # JS-click the submit control (ad overlays steal normal pointer events on some
                # sites; some sites use <a> or <input> rather than <button>).
                page.evaluate(
                    "(reText) => { const rx = new RegExp(reText, 'i');"
                    " const b = [...document.querySelectorAll('button, a, input[type=submit]')]"
                    ".find(x => rx.test((x.textContent || x.value || '').trim())); if (b) b.click(); }",
                    c.submit_button_text,
                )
                results = c.result_selectors()
                per_result = max(1.0, c.wait_s / len(results))
                raw = None
                for sel in results:
                    try:
                        page.wait_for_selector(sel, timeout=per_result * 1000)
                        raw = page.inner_text(sel)
                        break
                    except Exception:
                        continue
                if raw is None:
                    raise SelectorMiss(c.name, "result", results, c.url)
                pct = parse_ai_percent(raw)
                if pct is None:
                    # NEVER fabricate 0.5 here. wait_for_selector can return the moment a
                    # placeholder element exists in the initial DOM, before the real score lands, so
                    # an unparseable result is a genuine FAILURE, not a "neutral" reading. Returning
                    # a number would feed a fake score into the loop: it enters the numeric list,
                    # drives max(), and suppresses the all_checkers_failed flag that exists to signal
                    # exactly this situation — the loop would then optimise against, and declare a
                    # pass on, a score no detector ever produced. Same bug class already fixed in the
                    # mage/hc3/perplexity adapters: a failed detector must be EXCLUDED, not neutral.
                    raise RuntimeError(
                        f"{c.name}: could not parse an AI percentage from {raw.strip()[:80]!r}"
                    )
                return pct
            finally:
                browser.close()


class ZeroGPTChecker(WebUIChecker):
    """Built-in ZeroGPT checker (kept as a named class for convenience)."""

    url = ZEROGPT.url

    def __init__(self):
        super().__init__(ZEROGPT)


_BUILTINS: dict[str, SiteConfig] = {"zerogpt": ZEROGPT}


def _user_sites() -> dict[str, SiteConfig]:
    """Load user-defined sites from ``$UNTELL_BROWSER_SITES`` (a JSON path; ``$HUMANIZE_BROWSER_SITES`` is a legacy alias) or ``./browser_sites.json``.

    JSON shape: ``{"sitename": {"url": ..., "input_selector": ..., "result_selector": ..., ...}}``.
    """
    # The legacy alias is documented in the line above but was never read, so anyone who followed
    # it got {} back and every custom checker silently returned None.
    path = (
        os.environ.get("UNTELL_BROWSER_SITES")
        or os.environ.get("HUMANIZE_BROWSER_SITES")
        or "browser_sites.json"
    )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        return {}
    out: dict[str, SiteConfig] = {}
    for name, cfg in (raw or {}).items():
        if name.startswith("_") or not isinstance(cfg, dict):
            continue  # allow top-level "_comment" keys
        clean = {k: v for k, v in cfg.items() if not k.startswith("_")}  # allow per-entry "_caveat"
        try:
            out[name.lower()] = SiteConfig(name=name.lower(), **clean)
        except Exception:
            continue  # skip malformed entries rather than crash
    return out


def _all_checkers() -> dict[str, SiteConfig]:
    """Built-ins first (registration order), then user JSON sites (file order).

    ``auto`` means "the first AVAILABLE checker", so the order is the contract: the shipped
    built-in (zerogpt) is the default pick, and a user's ``browser_sites.json`` adds candidates
    behind it. Built-ins also keep the lookup precedence ``get_browser_checker`` always enforced —
    a user entry of the same name must NOT shadow the shipped config, or ``auto`` and naming the
    site would disagree about which detector ran.
    """
    merged = dict(_BUILTINS)
    for name, cfg in _user_sites().items():
        if name not in _BUILTINS:
            merged[name] = cfg
    return merged


def get_browser_checker(name: str) -> WebUIChecker | None:
    """Return a checker for ``name`` (built-in or user-configured), or None if unknown.

    ``name`` may be ``"auto"`` (case-insensitive): resolve to the first AVAILABLE checker —
    built-ins in registration order, then user JSON sites in file order (see ``_all_checkers``).
    With only the shipped built-in that is zerogpt; adding a ``browser_sites.json`` extends the
    pool without code (issue #2). Returns None only when nothing at all is configured, so
    ``--browser auto`` degrades exactly like an unknown name instead of crashing.
    """
    key = (name or "").lower()
    if key == "auto":
        merged = _all_checkers()
        if not merged:
            return None
        return WebUIChecker(next(iter(merged.values())))
    if key in _BUILTINS:
        return WebUIChecker(_BUILTINS[key])
    user = _user_sites()
    if key in user:
        return WebUIChecker(user[key])
    return None


def available_browser_checkers() -> list[str]:
    """Every configured checker name (sorted for display; ``auto`` picks the first in
    registration/file order instead — see ``_all_checkers``)."""
    return sorted(set(_BUILTINS) | set(_user_sites()))
