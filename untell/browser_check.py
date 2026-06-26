"""Browser-driven AI-detection via free web UIs (no API key).

Some detectors have no affordable API but a free web checker. This drives a real browser
(Playwright) to paste text into one and read the score — a $0 way to get a real-checker signal.

**Config-driven.** A site is just a ``SiteConfig`` (url + selectors). One built-in ships (ZeroGPT,
confirmed live 2026-06: input ``#textArea``, "Detect Text" button clicked via JS to dodge an ad
overlay, result ``.percentage-div`` → "100%AI GPT*"). Add your own sites without code via a JSON
file — see ``get_browser_checker`` / ``HUMANIZE_BROWSER_SITES``.

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


def parse_ai_percent(text: str) -> float | None:
    """Pull the first percentage out of a result string and return it as P(AI) in [0, 1].

    e.g. "100%AI GPT*" -> 1.0, "55% AI Generated" -> 0.55. Returns None if no percentage found.
    """
    m = _PCT.search(text or "")
    if not m:
        return None
    try:
        return clamp01(float(m.group(1)) / 100.0)
    except ValueError:
        return None


@dataclass
class SiteConfig:
    """How to drive one free web detector."""

    name: str
    url: str
    input_selector: str
    input_mode: str = "textarea"  # "textarea" | "contenteditable"
    submit_button_text: str = "detect"  # JS-click the first <button> whose text matches (regex, i)
    result_selector: str = ".result"
    wait_s: float = 45.0
    extra: dict = field(default_factory=dict)


ZEROGPT = SiteConfig(
    name="zerogpt",
    url="https://www.zerogpt.com/",
    input_selector="#textArea",
    input_mode="textarea",
    submit_button_text="detect",
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
                if c.input_mode == "contenteditable":
                    page.evaluate(
                        "([sel, txt]) => { const e = document.querySelector(sel);"
                        " if (e) { e.focus(); e.textContent = txt;"
                        " e.dispatchEvent(new InputEvent('input', {bubbles: true})); } }",
                        [c.input_selector, text],
                    )
                else:
                    page.fill(c.input_selector, text, timeout=c.wait_s * 1000)
                # JS-click the submit control (ad overlays steal normal pointer events on some
                # sites; some sites use <a> or <input> rather than <button>).
                page.evaluate(
                    "(reText) => { const rx = new RegExp(reText, 'i');"
                    " const b = [...document.querySelectorAll('button, a, input[type=submit]')]"
                    ".find(x => rx.test((x.textContent || x.value || '').trim())); if (b) b.click(); }",
                    c.submit_button_text,
                )
                page.wait_for_selector(c.result_selector, timeout=c.wait_s * 1000)
                pct = parse_ai_percent(page.inner_text(c.result_selector))
                return pct if pct is not None else 0.5
            finally:
                browser.close()


class ZeroGPTChecker(WebUIChecker):
    """Built-in ZeroGPT checker (kept as a named class for convenience)."""

    url = ZEROGPT.url

    def __init__(self):
        super().__init__(ZEROGPT)


_BUILTINS: dict[str, SiteConfig] = {"zerogpt": ZEROGPT}


def _user_sites() -> dict[str, SiteConfig]:
    """Load user-defined sites from ``$HUMANIZE_BROWSER_SITES`` (a JSON path) or ``./browser_sites.json``.

    JSON shape: ``{"sitename": {"url": ..., "input_selector": ..., "result_selector": ..., ...}}``.
    """
    path = os.environ.get("HUMANIZE_BROWSER_SITES") or "browser_sites.json"
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


def get_browser_checker(name: str) -> WebUIChecker | None:
    """Return a checker for ``name`` (built-in or user-configured), or None if unknown."""
    key = name.lower()
    if key in _BUILTINS:
        return WebUIChecker(_BUILTINS[key])
    user = _user_sites()
    if key in user:
        return WebUIChecker(user[key])
    return None


def available_browser_checkers() -> list[str]:
    return sorted(set(_BUILTINS) | set(_user_sites()))
