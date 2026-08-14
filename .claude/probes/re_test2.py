import re
tests = [
    (r'[.!?["\]]', 'at 3."'),
    (r'[.!?]["\']', 'at 3."'),
    (r'[.!?]["\x27]', 'at 3."'),
    (r'[.!?]["\u201d)]}', 'at 3."'),
    (r'[.!?]["]', 'at 3."'),
    (r'\."$', 'at 3."'),
]
for pat, s in tests:
    print(repr(pat), '->', bool(re.search(pat, s)))
