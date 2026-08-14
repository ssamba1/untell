from untell.layout import blocks
for label, text in [
    ("CRLF", "Line one here.\r\nLine two there.\r\n```\r\ncode block\r\n```\r\n"),
    ("LF",   "Line one here.\nLine two there.\n```\ncode block\n```\n"),
]:
    segs = list(blocks(text))
    print(f"--- {label}: {len(segs)} segments")
    for s in segs:
        print("   ", repr(s)[:100])
