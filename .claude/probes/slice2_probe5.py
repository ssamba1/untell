"""Round 2 probes: heights, dimensions, email/citation corners."""
import sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
from untell.scripts.preserve import lock

CASES = [
    ("height 5'10", 'He is 5\'10" tall. Then he left.'),
    ("height 6'2", 'She is 6\'2". Then she left.'),
    ("height decimal", "The child is 4'6.5\" now."),
    ("dim x", "The box is 10\u00d75 cm. Then pack."),
    ("dim x compact", "The box is 10x5 cm. Then pack."),
    ("dim x unit", "The room is 3\u00d74 m. It is large."),
    ("email multi-tld", "Write to a.b+c@sub.domain.co.uk. Then send."),
    ("email parens", "Contact (foo@bar.com) today."),
    ("email 1-char tld", "Email foo@bar.c today."),
    ("email no tld", "Email foo@bar today."),
    ("cite p range", "As shown (Smith, 2020, p. 4-5) earlier."),
    ("cite pp range", "(Smith & Lee, 2019, pp. 12\u201315) supports this."),
    ("cite semicolon prefix", "(Smith 2019; cf. Jones 2020, p. 3) agrees."),
    ("cite year letter", "Per Smith (2020a) and Jones (2020b), it holds."),
    ("bracket semicolon", "Prior work [12; 15] supports this."),
    ("quote number inside", 'He said "the 5% increase" then left.'),
    ("apostrophe dense", "The team's results didn't match Jones' figures, and the councils' plans weren't ready."),
    ("5's and 6's", "Count the 5's and 6's in the list."),
    ("footnote 5'", "See note 5' for details."),
]
for label, text in CASES:
    masked, mapping = lock(text)
    print(f"{label}: {masked!r}")
