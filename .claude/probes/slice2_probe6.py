"""Over-lock regression battery: ordinary prose must stay mostly free."""
import sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
from untell.scripts.preserve import lock

PROSE = [
    ("The study found that the new method works well in practice.", 0),
    ("She sat on the bench and read for an hour.", 0),
    ("The team's results didn't match Jones' figures, and the councils' plans weren't ready.", 0),
    ("We need to discuss the budget before the end of the week.", 0),
    ("The answer is 5 or 6. It depends on the context.", 0),
    ("I walked to the store and bought some apples.", 0),
    ("In my view, this is the best option available.", 0),
    ("The map was on the table next to the notebook.", 0),
    ("Mode of operation matters less than the outcome.", 0),
    ("We will insert the changes tomorrow morning.", 0),
    ("The speed of sound is about 343 m/s at sea level.", 1),  # fact, should lock
    ("He scored in the 95th percentile on the exam.", 1),
]
for text, expect_lock in PROSE:
    masked, mapping = lock(text)
    locked = bool(mapping)
    flag = "OK " if locked == bool(expect_lock) else "!! "
    print(f"{flag}{text!r} -> locked={locked} {list(mapping.values())[:3]}")