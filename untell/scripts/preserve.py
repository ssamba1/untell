"""Preserve-lock: mask spans that must survive a rewrite verbatim, then restore them.

The untell loop rewrites prose freely but must NOT alter citations, numeric facts, quoted
material, or named entities. We replace each such span with an opaque sentinel before the
rewrite and substitute the originals back afterward. This is the citation/meaning-integrity
differentiator (report gap #5).

API:
    lock(text)      -> (masked_text, mapping)   # mapping: sentinel -> original span
    restore(masked, mapping) -> text            # exact inverse of lock

Sentinels look like ``⟦HZ0007⟧`` — unlikely to occur in prose and stable across a rewrite as a
single unbreakable token (the skill instructs Claude to keep them intact). Entity masking uses
spaCy NER when installed; otherwise regex-only locking still covers citations/numbers/quotes.

Round-trip guarantee: ``restore(*lock(t)) == t`` for any text ``t`` — including text that already
contains literal ``⟦HZxxxx⟧`` sentinels, which are themselves locked so they survive a rewrite
verbatim instead of being rewritten by ``restore`` (asserted in tests).
"""

from __future__ import annotations

import logging
import re

# The environments whose content must not be rewritten, defined once in `latex` and imported here
# so the mask and the prose extractor cannot drift apart. `latex` imports nothing from this module,
# so there is no cycle.
# RUN DIRECTLY (`python .../untell/scripts/preserve.py`), put the directory that *contains* the package
# on sys.path so `import untell` resolves from any cwd. SKILL.md tells Claude to run this file by
# path on the zero-dependency tier, where nothing is installed — without this it dies on its first
# `from untell...` line. Must sit BEFORE those imports: below them it is unreachable.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.latex import ENV_ALTERNATION as _LATEX_ENV_ALTERNATION
from untell.text_split import _ABBREVIATIONS  # noqa: E402

logger = logging.getLogger(__name__)

# 4-OR-MORE digits: lock() numbers sentinels with f"⟦HZ{i:04d}⟧" (minimum width 4), which overflows
# to 5 digits past 9999 locked spans. Matching exactly \d{4} would make restore()/find_sentinels miss
# those, silently dropping the locked citation/fact on restore — so the round-trip must accept \d{4,}.
_SENTINEL_RE = re.compile(r"⟦HZ\d{4,}⟧")
# Public alias. The rewriters that have to verify sentinel survival (mt_pivot, t5_paraphrase,
# targeted) each had their own copy of this pattern. It guards every locked citation, number and
# quote, and the `{4,}` above is load-bearing — a copy written as `\d{4}` would stop matching past
# 9999 locked spans and silently drop them on restore. One definition, imported, cannot drift.
SENTINEL_RE = _SENTINEL_RE

# Units that may follow a number. Measured: with only the original short list
# (%|kg|km|cm|mm|mol|°|years|days|hours|minutes), "5 mg" locked NOTHING and "16 GB" locked "16"
# and left "GB" rewritable — the documented worst case, where a sentinel appears so the span looks
# protected while the unit stays mutable and a dose/size can silently change magnitude.
#
# ORDER IS LOAD-BEARING *within* this alternation: it is first-match-wins, so every LONGER unit must
# precede a shorter one that prefixes it, or "30 seconds" locks as "30 s" and leaves "econds" loose.
_UNIT = (
    r"percent|per cent|%"
    # time (longest first)
    r"|centuries|century|decades?|months?|weeks?|days?|hours?|minutes?|seconds?"
    r"|msec|µs|us|ns|ms|hrs?|mins?|secs?|yrs?|years?"
    # data
    r"|Gbps|Mbps|kbps|bps|GHz|MHz|kHz|Hz|GB|MB|KB|TB|PB|Gb|Mb|kb"
    # mass / volume
    r"|tonnes?|kcal|cal|kJ|kg|mg|µg|ug|lbs?|oz|mL|ml|dL|gal|mol|nmol|µmol"
    # distance / speed
    r"|kilometres|kilometers|metres|meters|miles|inches|yards|feet"
    r"|km/h|kph|mph|rpm|km|cm|mm|nm|µm|ft|yd|mi"
    # energy / electrical
    r"|kWh|MW|kW|mW|mV|mA|kV|W|V|A|J"
    # temperature (bare ° and °C/°F)
    r"|°[CF]?|K"
    # magnitudes / currency codes
    r"|trillion|billion|million|thousand|bn|USD|EUR|GBP|JPY"
    # bare SI singles last: they prefix nothing, and each is a real unit in prose ("100 m", "30 s")
    r"|kg|g|L|m|s|x|×"
)

# Month + weekday names: a date is a fact, but "March 15, 2024" locked only "15" and "2024",
# leaving the MONTH free to be rewritten to April while both sentinels survived intact.
_MONTH = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_WEEKDAY = r"Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:rs(?:day)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?"
# Split for the BARE-weekday case only. Abbreviations are matched case-sensitively there because
# "sat", "sun", "wed", "mon" and "fri" are ordinary words; see the date pattern below. The combined
# `_WEEKDAY` above is still used where a month or a number pins the context.
_WEEKDAY_FULL = r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_WEEKDAY_ABBR = r"Mon|Tues|Tue|Wed|Thurs|Thur|Thu|Fri|Sat|Sun"

# The dotted abbreviations, taken from the sentence splitter rather than retyped, so the two cannot
# drift apart — the whole defect this guards was the two disagreeing about what a sentence end is.
_ABBR_DOTTED = "|".join(
    sorted((re.escape(a) for a in _ABBREVIATIONS if "." in a), key=len, reverse=True)
)

# One author-year entry, and the signal words that can introduce one. Split out because the
# parenthetical rule below repeats the entry either side of a semicolon; see the measurement there.
#
# The prefix list is deliberately CLOSED. An open one — anything lowercase before the author —
# would swallow ordinary parentheses that happen to end in a year, and over-locking is the more
# expensive error here: a frozen span is prose the rewriter cannot improve, silently, forever.
_CITE_PREFIX = (
    r"(?:see\s+also|but\s+see|see|cf\.?|e\.g\.?|i\.e\.?|compare|reviewed\s+in|as\s+in|after)\s*,?"
)
_CITE_ENTRY = (
    r"[A-Z][A-Za-z'’.-]+(?:\s+(?:&|and|et al\.?)\s*[A-Za-z'’.-]*)*"
    r",?\s*\d{4}[a-z]?(?:,\s*pp?\.?\s*\d+(?:\s*[-–]\s*\d+)?)?"
)

# Ordered patterns. Every match from every pattern is collected and OVERLAPPING/ADJACENT spans are
# merged into their union (see `_merge`), so a broad pattern and a narrow one covering part of the
# same fact combine into one lock rather than competing — adding a pattern can only widen a lock.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Sentinel literals already present in the INPUT must themselves be locked. Otherwise lock()
    # may reuse the same ⟦HZxxxx⟧ token for a real span, and restore() would then rewrite the
    # user's literal token too — corrupting the round-trip. Lock them first so each maps uniquely.
    ("sentinel", _SENTINEL_RE),
    # Fenced and inline code. A rewrite that "improves the flow" of a code block destroys it, and
    # nothing else in this list covers it: ``src/main.py`` and ``parse_json()`` are prose-shaped
    # enough that every other pattern let them through untouched.
    ("code", re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)),
    ("code", re.compile(r"`[^`\n]{1,200}`")),
    # The same thing in HTML. Markdown's backticks were covered and their exact equivalent was not,
    # so any document written in HTML — a README rendered from it, a docs page, an issue body —
    # had its code free for the rewriter. MEASURED through the shipped loop, 6 tags x 2 styles:
    #
    #     <code>run a; then b</code>  ->  <code>run a. Then b</code>      12 of 12 DAMAGED
    #
    # Every tag in the family, both styles, no exceptions. Bounded so a stray unclosed tag cannot
    # swallow a document; the backreference keeps `<code>x</pre>` from matching at all.
    (
        "code",
        re.compile(r"<(code|pre|kbd|samp|tt|var)\b[^>]{0,200}>.{0,2000}?</\1>", re.DOTALL | re.IGNORECASE),
    ),
    # LaTeX. MEASURED before these entries existed: `lock()` protected **0 spans** of
    #     r"As \citep{smith2020} shows, see Eq.~\ref{eq:main}. We use $E = mc^2$ and \cite{jones}."
    # so every citation key, cross-reference and equation in a .tex file was free for the rewriter
    # to "improve". This is the repo's headline promise — citations survive — failing outright for
    # the one audience most likely to need it, and it is the single most-named gap in the competitor
    # census (41 of 111 profiles that beat us at something named the academic/LaTeX domain).
    #
    # Ordered BEFORE the citation and number rules below: those would otherwise take the numeric
    # core of \ref{tab:1} or the year inside \citep{smith2020} and leave the command shell
    # rewritable, which this file's own ordering comment calls the worst possible outcome.
    #
    # Math first — $...$ and \[...\] can contain braces and commands, so a command pattern would
    # otherwise carve them up.
    ("latex_math", re.compile(r"\$\$.+?\$\$|\\\[.+?\\\]|\$[^$\n]{1,200}\$", re.DOTALL)),
    # Environments whose CONTENT must survive byte-for-byte — not every environment.
    #
    # This used to be `\\begin\{(\w+\*?)\}.*?\\end\{\1\}`, matching ANY environment, and
    # `document` is an environment. MEASURED on a four-paragraph paper: the whole file masked to
    # `⟦HZ0000⟧\n⟦HZ0001⟧` and the rewriter received nothing at all, so `untell humanize --file
    # paper.tex` returned the input unchanged. LaTeX support is a headline promise of the academic
    # niche, and on a real document it was a no-op — the mirror image of the "LaTeX entirely
    # unprotected" defect it was written to fix.
    #
    # Locked (content is data, or the roadmap says never rewrite it): maths, floats and their
    # captions, theorem-like blocks, verbatim, tabular, the abstract.
    # NOT locked (containers whose content is the prose the user came here to humanize):
    # document, itemize, enumerate, description, quote, quotation, center.
    (
        "latex_env",
        re.compile(
            r"\\begin\{(" + _LATEX_ENV_ALTERNATION + r")\}.*?\\end\{\1\}",
            re.DOTALL,
        ),
    ),
    # Citation/reference/label commands, including the natbib and cleveref families, with their
    # optional argument: \citep[see][p. 4]{smith2020}
    (
        "latex_cite",
        re.compile(
            r"\\(?:cite[a-zA-Z]*|[Cc]ref|[Aa]utoref|nameref|ref|eqref|label|bibitem|nocite)"
            r"(?:\[[^\]]*\])*\{[^}]*\}"
        ),
    ),
    # Any other command that takes a braced argument (\textbf{...}, \includegraphics{...}), and
    # bare commands (\LaTeX, \newline). The braced form is listed first so the argument is kept
    # inside the lock rather than left loose.
    #
    # The lookbehind keeps these off WINDOWS PATHS, which are full of backslash-letter sequences.
    # Without it, `C:\Users\me\file.txt` matched three "commands" — \Users, \me, \file — and the
    # path rule below, which exists precisely to lock such a path as ONE span, would find its
    # target already carved up. A real LaTeX command never follows a letter, digit or colon.
    ("latex_cmd", re.compile(r"(?<![A-Za-z0-9:])\\[a-zA-Z@]+(?:\[[^\]]*\])*\{[^{}]{0,300}\}")),
    ("latex_cmd", re.compile(r"(?<![A-Za-z0-9:])\\[a-zA-Z@]+\*?")),
    # Bracketed numeric citations: [12], [3, 4], [1-5]
    ("citation", re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]")),
    # Parenthetical author-year (APA/MLA): (Smith, 2020), (Smith & Lee, 2019, p. 4),
    # (see Smith, 2019), (Smith 2019; Jones 2020), (cf. Smith 2019; Jones 2020, p. 4).
    #
    # The prefix and the semicolon list were added after MEASURING the end rather than the means.
    # The old pattern demanded a capitalised author immediately after `(` and closed at the first
    # `)`, so a multi-work or prefixed citation matched nothing and the parenthesis stayed OPEN to
    # the rewriter. Through the shipped loop, 8 of 16 form-by-style runs came back damaged:
    #
    #     (Smith, 2019; Jones, 2020)  ->  (Smith, 2019. Jones, 2020)
    #     (see Smith, 2019)           ->  (see Smith. 2019)
    #
    # The semicolon-to-sentence transform was editing INSIDE the citation. Single-work forms were
    # never damaged, which is why this was invisible: every example in the tests was one work.
    #
    # Written as a strict superset — one entry with no prefix is the old pattern — so the forms
    # that already worked keep matching exactly as they did.
    (
        "citation",
        re.compile(
            r"\(\s*(?:" + _CITE_PREFIX + r"\s*)?" + _CITE_ENTRY
            + r"(?:\s*;\s*(?:" + _CITE_PREFIX + r"\s*)?" + _CITE_ENTRY + r")*\s*\)"
        ),
    ),
    # Narrative author-year: Smith (2020), Smith et al. (2019)
    ("citation", re.compile(r"[A-Z][A-Za-z'’.-]+(?:\s+et al\.?)?\s+\(\d{4}[a-z]?\)")),
    # DOIs and URLs
    ("url", re.compile(r"https?://\S+|doi:\s*\S+", re.IGNORECASE)),
    # Quoted spans (straight or curly double quotes)
    ("quote", re.compile(r"[\"“][^\"”]{1,400}[\"”]")),
    # Single-quoted spans. British and academic house styles quote this way as a matter of course,
    # and until this line they were the one form of quotation the rewriter was free to edit.
    # MEASURED through the shipped loop on the same sentence in three punctuations, 3 seeds:
    #
    #     "double quotes"   2 of 2 quotations preserved
    #     “curly quotes”    2 of 2 preserved
    #     'single quotes'   0 of 2 preserved   -- 'we utilize a seamless methodology' was rewritten
    #
    # The reason to leave them out is the apostrophe: a naive `'...'` locks from "team's" to
    # "didn't" and swallows the prose between. The guards are what make it safe — an opening quote
    # at a word boundary, a closing quote followed by space or punctuation, no whitespace before
    # the close, and six characters minimum.
    #
    # MEASURED over 80 HC3 texts (both halves): **0** spurious matches, and 0 on an
    # apostrophe-dense probe ("The team's results didn't match Jones' figures, and the councils'
    # plans weren't ready."), while the genuine quotation matches.
    ("quote", re.compile(r"(?<![\w'])'([^'\n]{6,300}?[^\s'])'(?=[\s.,;:!?)\]]|$)")),
    # Curly single quotes. These were excluded above for a stated reason — U+2019 is the typographic
    # apostrophe, so `‘...’` cannot be told from "don’t" by shape alone — and the reason has a hole
    # in it: **U+2018 is not an apostrophe.** Nothing writes `don‘t`. The OPENING delimiter is
    # unambiguous, so it anchors the match, and only the close is in doubt. That makes this rule
    # safer than the straight one above, which has an ambiguous character at both ends.
    #
    # The cost of the exclusion, MEASURED through the shipped loop with the transform that is
    # actually known to fire — semicolon-to-sentence — 2 styles:
    #
    #     ‘the scheme paid for itself; the region kept the surplus’
    #         ->  ‘the scheme paid for itself. The region kept the surplus’    2 of 2 DAMAGED
    #     the same words in straight, curly-double and straight-double quotes  0 of 6 damaged
    #
    # So the one quotation style British and academic house styles use as a matter of course was
    # the one the rewriter could still edit — which is exactly the gap the straight-quote rule
    # above was added to close, left half-open by the character it declined to handle.
    #
    # An interior `’` is admitted only when a letter follows it, which is the apostrophe's shape
    # ("the dog’s bowl") and never a closing quote's.
    #
    # The rule above cites 80 HC3 texts for its false-positive bar. **That corpus cannot test this
    # rule**: 0 of its 160 halves contain a single U+2018, so the sweep returns 0 spurious matches
    # for the reason a dead regex does — there was nothing there to match. It was run, and it is
    # recorded here as worthless rather than quoted as evidence.
    #
    # The control that carries weight is the apostrophe-dense probe, which contains the character
    # actually at risk. MEASURED, 3 probes, 11 U+2019 apostrophes, no U+2018: **0** matches, e.g.
    # "The team’s results didn’t match Jones’ figures, and the councils’ plans weren’t ready."
    # With a genuine quotation present, all 4 positive forms match in full, including one with an
    # interior apostrophe.
    ("quote", re.compile(r"‘(?:[^‘’\n]|’(?=[A-Za-z])){5,299}[^\s‘’]’(?=[\s.,;:!?)\]]|$)")),
    # Email addresses — a fact a rewrite must never "tidy".
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # Software identifiers: full version strings, dependency pins, and file paths. These MUST come
    # before the number rules, which otherwise take the numeric core and leave the rest free — the
    # partial lock this list's ORDER comment calls the worst possible outcome. MEASURED before this
    # entry existed:
    #   "v1.2.3-rc4"      -> "⟦HZ0000⟧-rc4"            (pre-release tag rewritable)
    #   "untell==0.2.0"   -> "untell==⟦HZ0000⟧.0"      (locked "0.2", left ".0")
    #   "numpy>=1.24"     -> "numpy⟦HZ0000⟧"           (the package name outside the lock)
    #   "1.2.3+build.99"  -> "⟦HZ0000⟧.3+build.⟦HZ0001⟧" (two spans, build metadata severed)
    #   r"C:\Users\me\file.txt" -> r"C:\Users\me\⟦HZ0000⟧" (the directory rewritable)
    # A version that reads as "1.2.3" and installs as something else is wrong in the way nobody
    # catches by eye, and these are the spans a reader copies verbatim.
    (
        "version",
        re.compile(
            # Dependency specifier with its package name: untell==0.2.0, numpy>=1.24, x ~= 2.1
            r"\b[A-Za-z_][\w.-]*\s*(?:==|>=|<=|~=|!=|<|>)\s*\d[\w.*+-]*"
            # Full version, with any pre-release or build metadata: v1.2.3-rc4, 1.2.3+build.99
            r"|\bv?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.-]*)+\b"
        ),
    ),
    (
        "path",
        re.compile(
            # Windows path with a drive letter, or any slash-separated path with a file extension.
            # Requires a separator AND an extension, so ordinary prose ("and/or", "he said/she
            # said") cannot match.
            r"\b[A-Za-z]:\\[^\s\"']+"
            r"|(?<![\w/])(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+\.[A-Za-z][A-Za-z0-9]{0,7}\b"
        ),
    ),
    # Significant numbers. Avoids locking bare single digits (a lone "5" stays rewritable; "5 days"
    # locks via its unit).
    #
    # ORDER IS LOAD-BEARING: alternation is first-match-wins, so every COMPOUND form must precede the
    # plain-number forms that would otherwise consume its prefix. Measured before this ordering
    # existed, 7 of 28 fact types locked only PARTIALLY — the worst possible outcome, because a
    # sentinel appears and the span looks protected while the rest stays mutable:
    #   "-15"        -> locked "15", dropping the MINUS SIGN (restores as a positive number)
    #   "p<0.05"     -> locked "0.05", leaving "<" free to become ">" (inverts the claim)
    #   "3.5%"       -> locked "3.5", leaving "%" free to become " percent"
    #   "9:30"       -> locked "30" only, so the hour was rewritable
    #   "2024-03-15" -> locked "2024", "03", "15" as three spans, so the date could be reordered
    #   "v2.1.3"     -> locked "1.3"
    #   "10-20"      -> locked the endpoints separately, so the range could be flipped
    (
        "number",
        re.compile(
            r"\bv\d+(?:\.\d+)+\b"  # semantic version: v2.1.3
            r"|\b\d{4}-\d{2}-\d{2}\b"  # ISO date: 2024-03-15
            r"|\b\d+(?:\.\d+)?[eE][+-]?\d+\b"  # scientific notation: 1.5e10
            # Slash date BEFORE the fraction rule, which would otherwise take "03/04" and leave
            # "/2021" as free text: measured, "03/04/2021" masked to "⟦HZ0000⟧/⟦HZ0001⟧" with the
            # separator rewritable and the day/month pair severed from its year.
            r"|\b\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}\b"  # slash date: 03/04/2021
            # Clock time INCLUDING any meridiem. "9:30 AM" locked only "9:30" and left "AM" free,
            # so a rewrite could move a meeting twelve hours while every sentinel survived intact.
            # `[Mm]\.?` would swallow a sentence-ending full stop after "PM", leaving the masked
            # text without a terminator and breaking sentence splitting downstream. Match either
            # the fully dotted form or the undotted one, so only a dot that belongs to the
            # abbreviation is absorbed.
            # The `\b` belongs to the UNDOTTED branch only: after "a.m." the next character is a
            # space, so a trailing \b can never match and the dotted form would fall through to the
            # bare-time rule below, leaving the meridiem outside the lock again.
            r"|\b\d{1,3}:\d{1,3}(?::\d{2})?\s*(?:[AaPp]\.[Mm]\.|[AaPp][Mm]\b)"  # 9:30 AM, 4:15 p.m.
            r"|\b\d{1,3}:\d{1,3}(?::\d{2})?\b"  # time or ratio: 9:30, 3:1, 1:02:33
            r"|\b\d+\s*/\s*\d+\b"  # fraction: 2/3
            # Comparison against a number: p<0.05, n >= 30. The operator must be inside the lock or a
            # rewrite can invert the assertion while the sentinel survives intact.
            r"|\b[A-Za-z]{1,3}\s*[<>≤≥]=?\s*[-−]?\d[\d,]*(?:\.\d+)?"
            r"|[<>≤≥]=?\s*[-−]?\d[\d,]*(?:\.\d+)?"
            r"|[-−]?[$€£]\s?\d[\d,]*(?:\.\d+)?"  # currency, optionally negative
            # Number + unit, allowing a decimal and a leading sign. The terminator is (?!\w), NOT \b:
            # `\b` requires a word character on one side, and "%" / bare "°" are non-word, so a
            # trailing `\b` could only succeed when the symbol was followed by a letter or digit —
            # which never happens in prose. That made "5%" match nothing at all and "42%" lock only
            # its digits.
            r"|[-−]?\b\d[\d,]*(?:\.\d+)?\s*(?:" + _UNIT + r")(?!\w)"
            r"|\b\d+\s*[-–—]\s*\d+\b"  # numeric range: 10-20
            r"|[-−]\d[\d,]*(?:\.\d+)?\b"  # negative number: -15, -3.2
            r"|\b\d[\d,]*\.\d+\b"  # decimals
            r"|\b\d{1,3}(?:,\d{3})+\b"  # comma-grouped thousands
            r"|\b\d{2,}\b"  # standalone integers of 2+ digits
        ),
    ),
    # Calendar dates written with a month or weekday NAME. The name carries as much of the fact as
    # the digits do, so it has to be inside the same sentinel: measured, "March 15, 2024" locked
    # "15" and "2024" as two separate spans and left "March" freely rewritable.
    (
        "date",
        re.compile(
            r"\b(?:" + _WEEKDAY + r"),?\s+(?:" + _MONTH + r")\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?"
            r"|\b(?:" + _MONTH + r")\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4}"
            r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MONTH + r"),?\s*\d{4}"
            r"|\b(?:" + _MONTH + r")\s+\d{4}\b"
            r"|\b(?:" + _MONTH + r")\s+\d{1,2}(?:st|nd|rd|th)\b"
            r"|\b\d{1,2}(?:st|nd|rd|th)\s+of\s+(?:" + _MONTH + r")\b"
            # Bare weekday. This pattern carries re.IGNORECASE and the three-letter abbreviations
            # are ordinary English words, so measured: "She **sat** on the bench", "The **sun** was
            # bright" and "the **wed**ding" all locked as date facts — pinning ordinary prose the
            # rewriter is supposed to be free to change. The abbreviations now require their
            # capitalised form, which costs nothing (a weekday in real prose is capitalised); the
            # full names stay case-insensitive because "sunday" is unambiguous either way.
            r"|\b(?:" + _WEEKDAY_FULL + r")\b"
            r"|(?-i:\b(?:" + _WEEKDAY_ABBR + r")\b)"
            r"|\b[QH][1-4]\s*(?:of\s+)?(?:FY)?\d{2,4}\b"  # Q3 2024, H1 FY25
            r"|\bFY\s?\d{2,4}\b"
            r"|\b\d+(?:st|nd|rd|th)\b",  # bare ordinal: the 3rd
            re.IGNORECASE,
        ),
    ),
    # Dotted numeric identifiers: bare semantic versions (1.26.4), IPv4 addresses (192.168.1.24),
    # section and clause numbers (2.3.1). Three or more components, so an ordinary decimal is
    # untouched.
    #
    # Ordered BEFORE every numeric rule below, because the decimal pattern stops at the SECOND
    # component and leaves the rest of the token in open text. MEASURED, the state before this
    # entry existed:
    #
    #     "Requires numpy 1.26.4 or newer."       ->  "Requires numpy ⟦HZ0000⟧.4 or newer."
    #     "The host was 192.168.1.24 yesterday."  ->  "The host was ⟦HZ0000⟧.⟦HZ0001⟧ yesterday."
    #
    # The sentinel survives and the tail does not: a rewrite can turn 1.26.4 into 1.26.7 with every
    # lock intact. `v2.10.3` masked whole only because the leading `v` makes it an identifier, so
    # the protection depended on notation rather than on what the token means. This is the same
    # failure shape as the CD4+ note below — locking the stem and leaving the part that carries the
    # distinction.
    #
    # Components are unbounded in length. A first attempt capped each at four digits, and a real
    # Windows build number — 10.0.19045.3803 — split at the 5-digit component into "10.0" and
    # "19045.3803", reproducing the exact defect this entry fixes.
    (
        "dotted",
        re.compile(r"\b\d+(?:\.\d+){2,}\b"),
    ),
    # Two-component dotted identifiers: `word.number` where the second component has a non-digit
    # character (`np.float64`, `untell.score`, `os.path`). The 3+ numeric-component pattern above
    # misses these because the second component contains letters. Ordered after it so purely-numeric
    # "1.2" still falls through to the number rules.
    #
    # `model.01` was listed here as a third example and never matched: the second component must
    # contain a LETTER, and "01" does not. MEASURED — it locks as `⟦HZ0000⟧` for "01" alone, leaving
    # "model." outside the lock, which is the partial lock this list's ORDER comment calls the worst
    # possible outcome. Left standing and recorded rather than widened, because widening this rule
    # to `word.digits` would claim every "Section 3" and "Figure 2" in the language; the example was
    # wrong, not the pattern.
    #
    # `\d*` matches ZERO digits, so this also claims any `word.word` — including the dotted
    # ABBREVIATIONS, 13 of the 47 the sentence splitter knows about: e.g, i.e, a.m, p.m, u.s, u.k,
    # ph.d, m.d, b.a, m.a, d.c. Locking one is not harmless, because the sentinel hides the evidence
    # every abbreviation-aware guard downstream depends on. `⟦HZ0000⟧.` looks exactly like the end of
    # a sentence, so `split_sentences` mis-splits there and the capital-restore pass upcases what
    # follows. FOUND on RAID, which writes in the register that uses these:
    #
    #     "(e.g. small branches or blurred edges)"  ->  "(e.g. Small branches or blurred edges)"
    #
    # 2 of 50 RAID halves, 0 of 50 HC3 halves — forum prose does not write "e.g." at all.
    #
    # Excluded here rather than guarded downstream because the blindness is not confined to one
    # pass: sentence splitting feeds burstiness, per-sentence scoring and the targeted rewriter's
    # unit of work, and all of them see the masked text.
    (
        "dotted",
        re.compile(rf"\b(?!(?i:{_ABBR_DOTTED})\b)[A-Za-z_][\w.-]*\.\d*[A-Za-z][\w.-]*\b"),
    ),
    # Phone numbers: international E.164, national formats, extensions. A rewrite that changes a
    # phone number while the sentinel survives intact is the worst possible outcome.
    # (?<! ) prevents the pattern from consuming a trailing space — without it, the match would
    # include the space and the sentinel would restore with an extra trailing space.
    (
        "phone",
        re.compile(
            r"\+[0-9][0-9.-]{7,20}(?<! )"
            r"|\b0[0-9]{2}[.\s-]?[0-9]{3}[.\s-]?[0-9]{4}\b"
            r"|\b1[-.]?[0-9]{3}[-.]?[0-9]{3}[-.]?[0-9]{4}\b"
            r"|\b[0-9]{3}[-.]?[0-9]{3}[-.]?[0-9]{4}\b"
        ),
    ),
    # Short hex literals: C-style `0xFF`, `\x1B`, and URL percent-encoding `%2F`. These are facts
    # (colour values, escape codes, URI components) that must not be altered. Ordered BEFORE the
    # long-form hexid pattern, which requires 7+ chars and would not match these.
    (
        "hexid",
        re.compile(
            r"\b0[xX][0-9a-fA-F]{1,6}\b"  # 0xFF, 0x1A3
            r"|\\x[0-9a-fA-F]{1,4}"  # \x1B escape sequences
            r"|%[0-9a-fA-F]{2}"  # URL percent-encoding: %2F, %E2
        ),
    ),
    # Hex identifiers: git short shas (4f2a91c), full shas, MD5/SHA digests. One altered character
    # makes them point at nothing, and no rule above covered them.
    #
    # The obvious pattern is a bare hex class, and the obvious objection is that English is full of
    # hex-shaped words. MEASURED over 240 real texts (120 HC3 + 120 RAID pairs) plus a set of prose
    # traps:
    #
    #     [0-9a-f]{7,40}                     0 corpus locks, but locks "defaced"
    #     + at least one digit               0 corpus locks, 0 traps, 4/4 shas
    #     + at least one digit AND letter    0 corpus locks, 0 traps, 4/4 shas
    #
    # The last is used. Requiring a digit rules out "defaced", "deadbeef" and "facade"; requiring a
    # letter keeps a run of plain digits out of this rule, where the 4-or-more-digits number rule
    # already handles it and would otherwise be shadowed.
    #
    # LOWERCASE ONLY, and it costs nothing. Git writes shas in lower case; the UPPERCASE forms are
    # already locked by the `identifier` rule below, which takes letter-and-digit tokens whole —
    # CHECKED, not assumed: "A3F5B2C9D8E14F6072B3C4D5E6F70819" and "Model ABCDEF1" both mask as one
    # span without this entry. Admitting A-F here would add nothing and would put ordinary part
    # numbers in range of a hex rule, so the two rules split the space by case.
    (
        "hexid",
        re.compile(r"\b(?=[0-9a-f]{7,40}\b)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"),
    ),
    # Ratios and scales expressed in words — "1 in 5", "4 out of 5", "3 per 100", "2 to 1". Both
    # numbers and the connective must move together or the ratio inverts while looking protected.
    (
        "ratio",
        re.compile(
            r"\b\d[\d,]*(?:\.\d+)?\s+(?:in|out of|of|per|to)\s+\d[\d,]*(?:\.\d+)?\b",
            re.IGNORECASE,
        ),
    ),
    # Tolerance and approximation markers. "12 ± 3" locked only "12"; "~500" locked only "500",
    # dropping the "about" and asserting an exact figure.
    (
        "number",
        re.compile(
            r"\d[\d,]*(?:\.\d+)?\s*(?:±|\+/-|\+-)\s*\d[\d,]*(?:\.\d+)?"
            r"|[~≈≃]\s*[-−]?\d[\d,]*(?:\.\d+)?"
        ),
    ),
    # Numbered cross-references and legal citations. "Section 3.2" locked "3.2" alone, so the label
    # could become "Chapter"; "42 U.S.C. 1983" split into two unrelated integers.
    (
        "reference",
        re.compile(
            r"\b\d+\s+U\.?\s?S\.?\s?C\.?\s*§*\s*\d+(?:\([a-z0-9]+\))*"
            r"|§+\s*\d+(?:\.\d+)*(?:\([a-z0-9]+\))*"
            r"|\b(?:Section|Sec|Chapter|Ch|Figure|Fig|Table|Tab|Appendix|Annex|Equation|Eq|Step|Part"
            r"|Volume|Vol|Issue|No|Article|Clause|Item|Level|Phase|Grade|Room|Page|pp?)\.?\s*"
            r"[A-Z]?\d+(?:\.\d+)*[a-z]?\b",
        ),
    ),
    # Alphanumeric identifiers: chemical formulae (H2O2), gene symbols (BRCA1), model and standard
    # names (GPT4, ISO 9001), hex colours. Each is a fact whose digits carry the meaning, and none
    # matched anything above because the digits are welded to letters.
    (
        "identifier",
        re.compile(
            r"#[0-9A-Fa-f]{3,8}\b"
            # The +/- variants come FIRST: alternation is first-match-wins, so the plain rules
            # below would otherwise take "CD4" and leave the sign outside the lock.
            #
            # A trailing +/- is part of the identifier, not punctuation beside it. Immunology and
            # lab notation use it to carry POLARITY — CD4+ and CD4- are opposite cell populations —
            # so locking only the stem left the sign freely rewritable while the sentinel survived
            # intact, and a rewrite could invert the finding. Measured: "CD4+" masked to
            # "⟦HZ0000⟧+" while "CD8-" happened to mask whole, so the two behaved differently
            # inside one sentence.
            r"|\b[A-Z]{2,}[- ]?\d+(?:[-.]\d+)*[+-](?!\w)"
            r"|\b[A-Z][A-Za-z]*\d+[A-Za-z0-9]*[+-](?!\w)"  # CD4+, CD8-, Rh+
            r"|\b[A-Z]{2,}[- ]?\d+(?:[-.]\d+)*\b"  # ISO 9001, IEEE 802.11
            r"|\b[A-Z][A-Za-z]*\d+[A-Za-z0-9]*\b"  # H2O2, BRCA1, B12, GPT4
        ),
    ),
    # Paths and code identifiers appearing bare in prose (outside backticks).
    (
        "code",
        re.compile(
            r"\b[\w.-]+(?:/[\w.-]+)+\.\w{1,6}\b"  # src/main.py
            r"|\b[\w-]+\.(?:py|js|ts|tsx|jsx|json|ya?ml|md|txt|csv|tsv|html?|css|sh|ps1|toml|ini|cfg"
            r"|xml|sql|go|rs|java|rb|php|c|cpp|hpp|swift|kt)\b"  # main.py
            r"|\b[A-Za-z_]\w*\(\)"  # parse_json()
            r"|\b[a-z]+(?:_[a-z0-9]+)+\b"  # snake_case_identifier
            # Long CLI flags: --tier, --best-of. A rewrite that turns "Pass --tier full" into "use
            # the full tier" has silently deleted the instruction. Only the `--x` form, because a
            # single `-x` collides with hyphenated prose and with "--" used as an em-dash.
            r"|(?<![\w-])--[A-Za-z][\w-]*"
            # Environment variables and other SCREAMING_SNAKE identifiers: UNTELL_ENABLE_RADAR.
            # The underscore is required, so ordinary acronyms (AI, NASA, HTTP) are left rewritable
            # and are handled by the entity pass instead.
            r"|\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"
        ),
    ),
]


_WARNED_NO_NER = False


def _warn_no_ner() -> None:
    """Say once that named-entity locking is off, and how to turn it on."""
    global _WARNED_NO_NER
    if not _WARNED_NO_NER:
        logger.warning(
            "spaCy is installed but the 'en_core_web_sm' model is not, so NAMED ENTITIES "
            "(people, organisations, places) are NOT being locked — only citations, numbers, "
            "quotes and URLs are. Enable it with: python -m spacy download en_core_web_sm"
        )
        _WARNED_NO_NER = True


def _spacy_entity_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans for named entities via spaCy, or [] if spaCy is absent."""
    try:
        nlp = _spacy_entity_spans._nlp  # type: ignore[attr-defined]
    except AttributeError:
        # Check for the MODEL before importing spacy. `import spacy` alone costs ~5s, and without
        # en_core_web_sm it buys nothing — so the common install (spacy present, model absent) was
        # paying five seconds of first-call latency for zero locked entities. find_spec is a cheap
        # path lookup; the model ships as an ordinary importable package.
        import importlib.util

        if importlib.util.find_spec("en_core_web_sm") is None:
            _warn_no_ner()
            _spacy_entity_spans._nlp = None  # type: ignore[attr-defined]
            return []
        try:
            import spacy
        except (ImportError, OSError):
            _spacy_entity_spans._nlp = None  # type: ignore[attr-defined]
            return []
        try:
            nlp = spacy.load("en_core_web_sm")
        except (ImportError, OSError):
            # DO NOT fall back to spacy.blank("en"). A blank pipeline has no NER component at all
            # (pipe_names == []), so it returns zero entities — while still costing ~4 seconds to
            # construct on first use. Measured, that was the entire cost/benefit: 4.26s of startup
            # latency buying nothing, and named-entity locking silently inert even though the README
            # promises entities are locked byte-for-byte. Skip spaCy entirely and say so once, so the
            # gap is visible and fixable instead of invisible and slow.
            _warn_no_ner()
            _spacy_entity_spans._nlp = None  # type: ignore[attr-defined]
            return []
        _spacy_entity_spans._nlp = nlp  # type: ignore[attr-defined]
    if nlp is None:  # cached "unavailable" — don't retry the failed load per call
        return []
    try:
        doc = nlp(text)
    except (ImportError, OSError):
        return []
    keep = {"PERSON", "ORG", "GPE", "LOC", "WORK_OF_ART", "LAW", "PRODUCT", "EVENT", "NORP", "FAC"}
    return [(e.start_char, e.end_char) for e in getattr(doc, "ents", []) if e.label_ in keep]


def _collect_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for _label, pat in _PATTERNS:
        for m in pat.finditer(text):
            if m.start() != m.end():
                spans.append((m.start(), m.end()))
    spans.extend(_spacy_entity_spans(text))
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping/adjacent spans so masks never collide."""
    if not spans:
        return []
    spans = sorted(set(spans))
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # overlap or touch
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def lock(text: str) -> tuple[str, dict[str, str]]:
    """Replace protected spans with sentinels. Returns (masked_text, mapping)."""
    spans = _merge(_collect_spans(text))
    mapping: dict[str, str] = {}
    out: list[str] = []
    cursor = 0
    for i, (start, end) in enumerate(spans):
        out.append(text[cursor:start])
        sentinel = f"⟦HZ{i:04d}⟧"
        mapping[sentinel] = text[start:end]
        out.append(sentinel)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), mapping


# A span is safe to capitalise only when its first word is plain lowercase letters. That excludes
# every form whose case is load-bearing: "doi:10.1000/xyz" (colon), "iPhone" and "mRNA" (internal
# capitals), "e-mail" is fine but "pH" is not. Getting this wrong writes "Doi:10.1000/xyz" into a
# citation, which is worse than the lowercase sentence it fixes.
_PLAIN_LOWERCASE_WORD = re.compile(r"^[a-z]+(?=\s|$)")
# Sentinel at the very start, or following a sentence terminator — i.e. where a capital belongs.
_SENTINEL_AT_SENTENCE_START = re.compile(r"(?:^|(?<=[.!?])\s+)(⟦HZ\d{4,}⟧)")

# An article immediately before a sentinel. A rewriter cannot see inside a locked span, so when the
# span already opens with an article the rewriter may supply a second one. MEASURED in
# t5_paraphrase output: "...worth mentioning that the ⟦HZ0004⟧ best seller list..." restored to
# "the the New York Times best seller list". Neither side is at fault — the rewriter is blind to the
# span by design, and the span is correct — so restore is the only place that can see both.
_ARTICLE_BEFORE_SENTINEL = re.compile(r"\b(a|an|the)(\s+)(⟦HZ\d{4,}⟧)", re.IGNORECASE)


def restore(masked: str, mapping: dict[str, str]) -> str:
    """Inverse of :func:`lock` — substitute each sentinel with its original span.

    A span locked mid-sentence carries mid-sentence casing, and the rewriter is free to move it.
    MEASURED on real output: "the New York Times" was locked out of "...published by various
    organizations, and the New York Times is just one...", the loop split the sentence at that
    clause, and restore wrote it back verbatim — "...in the book industry. the New York Times Best
    seller list is..." The masked candidate is clean; the lowercase sentence start is created here,
    which is why no check on the rewriter's output could see it.

    So a sentinel that lands at a sentence start has its span capitalised, and only when that is
    unambiguously safe — see `_PLAIN_LOWERCASE_WORD`.
    """
    def _sub(m: re.Match) -> str:
        return mapping.get(m.group(0), m.group(0))

    def _capitalise(m: re.Match) -> str:
        span = mapping.get(m.group(1))
        if span and _PLAIN_LOWERCASE_WORD.match(span):
            return m.group(0).replace(m.group(1), span[0].upper() + span[1:])
        return m.group(0)

    def _dedupe_article(m: re.Match) -> str:
        span = mapping.get(m.group(3))
        if not span:
            return m.group(0)
        first = span.split(maxsplit=1)[0] if span.split() else ""
        # Any article, not only a matching one: "a ⟦HZ⟧" over "the modest gain" restores to
        # "a the modest gain", which is just as broken as the doubled "the". Dropping the OUTER
        # article is safe in every case because the locked span is never touched — the span keeps
        # whatever article it was locked with, which is the one the source author chose.
        if first.lower() in ("a", "an", "the"):
            return m.group(3)
        return m.group(0)

    # Order matters: the duplicate article is removed while the sentinel is still a sentinel, and
    # that can leave the sentinel at a sentence start, which the capitalisation pass then fixes.
    out = _ARTICLE_BEFORE_SENTINEL.sub(_dedupe_article, masked)
    return _SENTINEL_RE.sub(_sub, _SENTINEL_AT_SENTENCE_START.sub(_capitalise, out))


def find_sentinels(text: str) -> set[str]:
    """Return the set of sentinel tokens (``⟦HZxxxx⟧``) present in ``text``.

    Used by the loop to mechanically enforce the lock: a rewrite is only accepted if it still
    contains *exactly* the sentinels it was given — neither dropping one (which would silently
    lose a locked citation/number/fact on restore) nor inventing one.
    """
    return set(_SENTINEL_RE.findall(text))


def main(argv: list[str] | None = None) -> int:
    """CLI for lock (default) and restore.

    Lock:    ``python -m untell.scripts.preserve "text"`` -> JSON {masked, mapping}
    Restore: ``python -m untell.scripts.preserve --restore --mapping '<json>' "masked text"``
             (or ``--mapping-file path.json``) -> the restored text
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import argparse
    import json

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)

    parser = argparse.ArgumentParser(prog="untell.scripts.preserve")
    parser.add_argument("text", nargs="?", help="text to lock, or masked text to restore")
    parser.add_argument("--restore", action="store_true", help="restore sentinels using --mapping")
    parser.add_argument("--mapping", help="JSON object {sentinel: original} for --restore")
    parser.add_argument("--mapping-file", help="path to a JSON mapping file for --restore")
    args = parser.parse_args(argv)

    if args.text is not None:
        text = args.text
    else:
        # None means stdin is a terminal; reading it would block with no prompt and no output.
        from untell.scripts.io_utils import read_stdin_or_none

        piped = read_stdin_or_none()
        if piped is None:
            print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
            return 2
        text = piped

    if args.restore:
        mapping: dict[str, str] = {}
        if args.mapping_file:
            with open(args.mapping_file, encoding="utf-8") as fh:
                mapping = json.load(fh)
        elif args.mapping:
            mapping = json.loads(args.mapping)
        missing = set(mapping) - find_sentinels(text)
        if missing:  # a locked span was dropped during rewriting — make it loud, don't lose it silently
            logger.warning(
                "%d locked span(s) are missing from the text and will "
                "NOT appear in the output (dropped during rewriting): %s",
                len(missing), ", ".join(sorted(missing)),
            )
        print(restore(text, mapping))
        return 0

    masked, mapping = lock(text)
    # ensure_ascii=True so the U+27E6 sentinels survive a non-UTF-8 (Windows cp1252) stdout;
    # they decode back to the real characters when the skill json-parses this output.
    print(json.dumps({"masked": masked, "mapping": mapping}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
