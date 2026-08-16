"""Apply slice-4 fixes to untell/layout.py. Idempotent; CRLF-aware; backslashes via chr(92)."""
import io

PATH = r"C:/Users/Admin/Humanize/untell/layout.py"
BS = chr(92)
NL = chr(10)

src = io.open(PATH, encoding="utf-8", newline="").read()
orig = src
crlf = "\r\n" in src
src = src.replace("\r\n", NL)
changed = False

# --- F3: HR/setext underline is a layout line ---------------------------------
i = src.index("_SENTENCE_END_RE = re.compile(")
j = src.index(NL, i)
old = src[i:j]
new_lines = [
    old,
    "# A THEMATIC BREAK or SETEXT HEADING UNDERLINE is a whole-line construct: `---`, `===`,",
    "# `***`, `___` and the spaced `- - -` / `* * *` forms. It is not prose \u2014 a merge",
    '# transform turned "My Heading' + BS + BS + '==========" into "My Heading ==========" and welded',
    '# "---" onto the next paragraph ("--- Para two.") \u2014 so it is emitted verbatim like a',
    "# table row. The SETEXT underline gets the same treatment as the ATX marker: the heading",
    "# text above it is still prose; the underline itself is layout. Guarded by the fence/",
    "# math/blank branch above, so a `---` inside fenced code stays code.",
    "_HR_RE = re.compile(",
    "    r'" + "^" + BS + "s*(?:(?:-{3,}|={3,}|" + BS + "*{3,}|_{3,})|(?:[-*]" + BS + "s+){2,}[-*])" + BS + "s*$" + "'",
    ")",
    "",
    "",
    "def _is_table_row(line: str) -> bool:",
    '    """True when the line is a markdown table row, including inside a blockquote.',
    "",
    "    The leading-pipe test is what every markdown table row has and what ordinary prose",
    '    never starts with; a table quoted inside a blockquote starts with the quote arrow',
    '    instead, so peel any number of `>` markers first. Without that, `> | Method |` fell',
    "    through to the marker branch and the CELL CONTENT was handed to the transform \u2014 a",
    "    column heading got relabeled (Method -> Technique), which nothing downstream can",
    "    restore. Nested blockquotes (`> > | x |`) peel one arrow at a time.",
    '    """',
    '    s = line.lstrip()',
    '    while s.startswith(">"):',
    '        s = s[1:].lstrip()',
    '    return s.startswith("|")',
]
new = NL.join(new_lines)
assert old in src, "sentence-end anchor missing"
src = src.replace(old, new, 1)
changed = True

# --- F3b + F4: use _is_table_row and add the HR branch in _segments -------------
old_lines = [
    '        if line.lstrip().startswith("|"):',
    "            yield from flush()",
    '            yield ("layout", "", line)',
    "            continue",
]
old = NL.join(old_lines)
new_lines = [
    "        if _is_table_row(line):",
    "            yield from flush()",
    '            yield ("layout", "", line)',
    "            continue",
    "        # A thematic-break or setext-underline line is layout too (see _HR_RE). Must come",
    '        # before the marker branch: the spaced form "- - -" otherwise matches the bullet',
    "        # marker and is treated as a list item.",
    "        if _HR_RE.match(line):",
    "            yield from flush()",
    '            yield ("layout", "", line)',
    "            continue",
]
new = NL.join(new_lines)
assert old in src, "table-branch anchor missing"
src = src.replace(old, new, 1)
changed = True

io.open(PATH, "w", encoding="utf-8", newline="").write(
    src.replace(NL, "\r\n") if crlf else src
)
print("changed" if changed else "NO CHANGE (already applied?)")
