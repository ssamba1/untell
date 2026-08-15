import os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rich_output import print_humanize_result

printed = []
class C:
    @staticmethod
    def print(*a, **k):
        printed.append(a)
import untell.rich_output as R
R._CONSOLE = C()
R._RICH = True
print_humanize_result(
    original="The system reads the file.",
    final="The system reads the file and processes it.",
    pre_score={"max": None, "tier": "lite"},
    post_score={"max": 0.42, "tier": "lite"},
    iterations=2, stopped="passed",
)
for i, p in enumerate(printed):
    if p:
        print(i, type(p[0]).__name__, repr(str(p[0])[:80]))
