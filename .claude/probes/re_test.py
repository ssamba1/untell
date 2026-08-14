import untell.text_split as T
import re
p = T._QUOTED_PERIOD_END_RE
print('pattern:', p.pattern)
# test each component
print('class test .":', bool(re.search(r'[.!?]["\'”’)]}»]', 'at 3."')))
print('class test .: ', bool(re.search(r'[.!?]', 'at 3.')))
print('search on plain:', bool(re.search(r'[.!?]', 'at 3.')))
# manual
m = re.search(r'[.!?]["\'”’)]}»]\s*$', 'at 3."')
print('manual full:', bool(m))
m2 = re.search(r'[.!?]["\'”’)]}»]', 'at 3."')
print('manual class-only:', bool(m2))
