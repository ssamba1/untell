"""Apply slice-4 fixes to untell/text_split.py. Idempotent.

Every backslash in the target text is built from chr(92) so no layer of
shell/JSON/tool escaping can double or drop it.
"""
import io

PATH = r"C:/Users/Admin/Humanize/untell/text_split.py"
BS = chr(92)  # backslash

src = io.open(PATH, encoding="utf-8", newline="").read()
orig = src
crlf = "\r\n" in src
src = src.replace("\r\n", "\n")
changed = False

# --- F1: abbreviations -------------------------------------------------------
old = '"vs", "etc", "al", "cf", "approx", "est", "dept", "univ", "inc", "ltd", "co", "corp",'
new = (
    '"vs", "etc", "al", "cf", "approx", "ca", "viz", "nb", "op", "cit", "est", "dept", "univ",\n'
    '    "inc", "ltd", "co", "corp",'
)
if old in src:
    src = src.replace(old, new, 1)
    changed = True

# --- F2a: footnote marker class + split alternatives -------------------------
old = "_ZERO_WIDTH_CLASS = re.escape(_ZERO_WIDTH_BETWEEN)\n\n_SENT_SPLIT = re.compile("
new = (
    "_ZERO_WIDTH_CLASS = re.escape(_ZERO_WIDTH_BETWEEN)\n"
    "\n"
    "# Footnote/endnote markers that may sit between a sentence terminator and the next\n"
    '# sentence: "significant.[1] However" and "significant.\u00b9 However" are boundaries, and\n'
    "# the marker belongs to the sentence that ends \u2014 it stays behind the split point, the\n"
    "# same way a closer does. Superscript digits (\u00b9\u00b2\u00b3 \u2070\u2074\u2075\u2076\u2077\u2078\u2079) plus the dagger family\n"
    "# (\u2020 \u2021 *) and the bracketed form up to three digits \u2014 a footnote past [999] is a\n"
    "# document nobody writes, and the fallback for it is the old under-split.\n"
    '_FOOTNOTE_MARKERS = "\\u00b9\\u00b2\\u00b3\\u2070\\u2074\\u2075\\u2076\\u2077\\u2078\\u2079\\u2020\\u2021*"\n'
    "_FN = re.escape(_FOOTNOTE_MARKERS)\n"
    "\n"
    "_SENT_SPLIT = re.compile("
)
if old in src:
    src = src.replace(old, new, 1)
    changed = True

old = '    rf"|(?<=[.!?][{_ZERO_WIDTH_CLASS}][{_C}])"\n)'
new = (
    '    rf"|(?<=[.!?][{_ZERO_WIDTH_CLASS}][{_C}])"\n'
    "    # Footnote/endnote markers between the terminator and the next sentence. Each shape\n"
    "    # is a separate fixed-width lookbehind: bracketed digits (1, 2, 3 wide), a bracketed\n"
    '    # pair ("[1][2]"), a marker followed by a closer, and one or two superscript/dagger\n'
    '    # markers ("\u00b9", "\u2020\u2020").\n'
    '    rf"|(?<=[.!?]' + BS + "[" + BS + "d" + BS + "])" + BS + 's+"\n'
    '    rf"|(?<=[.!?]' + BS + "[" + BS + "d" + BS + "d" + BS + "])" + BS + 's+"\n'
    '    rf"|(?<=[.!?]' + BS + "[" + BS + "d" + BS + "d" + BS + "d" + BS + "])" + BS + 's+"\n'
    '    rf"|(?<=[.!?]' + BS + "[" + BS + "d" + BS + "]" + BS + "[" + BS + "d" + BS + "])" + BS + 's+"\n'
    '    rf"|(?<=[.!?]' + BS + "[" + BS + "d" + BS + "][{_C}])" + BS + 's+"\n'
    '    rf"|(?<=[.!?][{_FN}])' + BS + 's+"\n'
    '    rf"|(?<=[.!?][{_FN}][{_FN}])' + BS + 's+"\n'
    ")"
)
if old in src:
    src = src.replace(old, new, 1)
    changed = True

# --- F2b: footnote merge rule -------------------------------------------------
old = (
    "def _continues_after_a_quoted_period(previous: str, nxt: str) -> bool:\n"
    "    return bool(_QUOTED_PERIOD_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)\n"
    "\n"
    "\n"
    "def split_sentences(text: str) -> list[str]:"
)
footnote_re = (
    "    rf'[.!?](?:" + BS + "[" + BS + "d{{1,3}}" + BS + "]|[{_FN}])+["
    + BS + '"' + BS + "'\u2019)}}" + BS + "]{_ZERO_WIDTH_CLASS}]*"
    + BS + "s*$'\n"
)
new = (
    "def _continues_after_a_quoted_period(previous: str, nxt: str) -> bool:\n"
    "    return bool(_QUOTED_PERIOD_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)\n"
    "\n"
    "\n"
    '# A footnote marker between the period and the next fragment: "significant.[1] but only\n'
    "# marginally.\" \u2014 the marker belongs to the FIRST sentence, and a lowercase continuation\n"
    '# cannot open a new one, so the split must merge back, exactly like the quoted-period\n'
    '# rule above. A capitalised continuation ("significant.[1] However") keeps the split.\n'
    "# The marker itself is not a closer, which is why the split rule above exists and why a\n"
    '# separate end-test is needed here \u2014 `_QUOTED_PERIOD_END_RE` looks for a closer right\n'
    '# after the terminator and does not see through "[1]".\n'
    "_FOOTNOTE_END_RE = re.compile(\n"
    + footnote_re
    + ")\n"
    "\n"
    "\n"
    "def _continues_after_a_footnote(previous: str, nxt: str) -> bool:\n"
    "    return bool(_FOOTNOTE_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)\n"
    "\n"
    "\n"
    "def split_sentences(text: str) -> list[str]:"
)
if old in src:
    src = src.replace(old, new, 1)
    changed = True

old = (
    "            _continues_after_abbreviation(merged[-1], part)\n"
    "            or _continues_after_ellipsis(merged[-1], part)\n"
    "            or _continues_after_a_quoted_period(merged[-1], part)\n"
)
new = (
    "            _continues_after_abbreviation(merged[-1], part)\n"
    "            or _continues_after_ellipsis(merged[-1], part)\n"
    "            or _continues_after_a_quoted_period(merged[-1], part)\n"
    "            or _continues_after_a_footnote(merged[-1], part)\n"
)
if old in src:
    src = src.replace(old, new, 1)
    changed = True

io.open(PATH, "w", encoding="utf-8", newline="").write(
    src.replace("\n", "\r\n") if crlf else src
)
print("changed" if changed else "NO CHANGE (already applied?)")
