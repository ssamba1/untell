import re
# exactly the file's class with real unicode
pat = re.compile(r'[.!?]["\'”’)]}»]\s*$')
print('file pattern:', pat.pattern)
print('match 3.":', bool(pat.search('at 3."')))
print('match done.":', bool(pat.search('He said "Done."')))
# without the single-quote escape
pat2 = re.compile(r'[.!?]["”’)]}»]\s*$')
print('no-esc match 3.":', bool(pat2.search('at 3."')))
