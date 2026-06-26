# Free AI-detector web-UI probe log

Live Playwright probes of free web detectors for the `--browser` checker (`untell/browser_check.py`).
Goal: find sites that (a) take pasted text without login/captcha, (b) return a parseable % with a
**stable** selector, and (c) are an actual detector. Dated 2026-06-25.

| Site | Input | Submit | Result | Verdict |
|---|---|---|---|---|
| **zerogpt.com** | `#textArea` (textarea) | `button.scoreButton` "Detect Text" (JS click — ad overlay) | `.percentage-div` → "100%AI GPT*" | ✅ **built-in.** Clean, stable, real detector. |
| decopy.ai/ai-detector | `#operate-input-textarea` | "Detect text" button | `.operate-report-chartdesc2` (no stable class on the number) | ⚠️ clean input but **weak detector** (scored clearly-AI text 0% AI) + noisy result DOM |
| detecting-ai.com | `textarea.form-control.text` | `a.btn.btn-primary` "Detect AI" (anchor, not button) | result % mixed with marketing %s, no stable selector | ⚠️ works but result extraction unreliable |
| sapling.ai/ai-content-detector | `#content-editor` (contenteditable) | "Check Again" button | framework gauge, no plain % | ⚠️ fragile + rate-limited |
| gptzero.me | `[role=textbox]` (placeholder "Paste your text") | "Scan" button | "AI N%" via body regex on `app.gptzero.me` | ❌ **re-probed 2026-06-26:** the free scan *works for a human* with no login under 10k chars, BUT the result page `app.gptzero.me` is **Cloudflare bot-gated** ("Hang on while we verify your browser") — headless Playwright is blocked, so it is **not automatable**. Don't ship a `--browser gptzero`; real GPTZero in the loop needs the paid API (`GPTZERO_API_KEY`, `--tier commercial`). |
| quillbot.com/ai-content-detector | `#aidr-input-editor` | "Detect AI" | — | ❌ reCAPTCHA-gated |
| scribbr.com/ai-detector | — | — | — | ❌ tool is an iframe widget (no DOM access) |
| brandwell.ai/ai-content-detector | — | — | — | ❌ iframe widget |
| writer.com/ai-content-detector | — | — | — | ❌ free tool removed (redirects to enterprise) |
| smodin.io/...detector | — | — | — | ❌ SPA/iframe, tool not in DOM |
| hivemoderation.com/...detection | — | — | — | ❌ demo behind a separate gated page |
| isgen.ai/ai-detector | — | — | — | ❌ 404 |

## Takeaways
- **2026 reality:** nearly every free detector is bot-gated (captcha / login-redirect / iframe) or
  hides results in framework components without stable, content-labeled selectors. ZeroGPT is the
  exception.
- Adding a site = a JSON entry (no code) once you confirm it has a stable input + result selector —
  see `examples/browser_sites.example.json` and the README. Re-probe with the same DOM-query method
  used here (query `textarea`/`[contenteditable]`, check for `recaptcha`/`hcaptcha`, find the submit
  button text, then locate a stable result element holding the %).
- For *reliable* multi-checker verification, the paid **commercial API** adapters (`--tier
  commercial`, key-gated) remain the dependable path; browser checking is a free best-effort extra.
