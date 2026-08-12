# Mutation survivors

Lines no test pins, each found by breaking it and watching the suite stay green.
Append-only; a human deletes a row once it has a killing test, or marks it
unkillable with the reason. Written by `mutate.py --record`.

| module | line | mutation | source |
| --- | --- | --- | --- |
| untell/_retry.py | 35 | constant: 408 -> 409 | `_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 529})` |
| untell/_retry.py | 128 | boundary: < -> <= | `if max_attempts < 1:` |
| untell/_retry.py | 141 | constant: 2 -> 3 | `delay = min(base_delay * (2 ** (attempt - 1)) + _JITTER.random(), max_delay)` |
