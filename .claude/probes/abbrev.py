import json
from untell.text_split import ends_with_abbreviation

out = {}
out["dr"] = ends_with_abbreviation("Dr.")
out["eg"] = ends_with_abbreviation("e.g.")
out["pm"] = ends_with_abbreviation("p.m.")
out["fig"] = ends_with_abbreviation("Fig.")
out["hello"] = not ends_with_abbreviation("hello")
out["hello_period"] = not ends_with_abbreviation("hello.")
out["initials"] = ends_with_abbreviation("J.R.R.")
out["etc"] = ends_with_abbreviation("etc.")
out["upper_dr"] = ends_with_abbreviation("DR.")
out["decimal"] = not ends_with_abbreviation("3.5")
out["section_marker"] = ends_with_abbreviation("1.")
print(json.dumps(out, indent=1))
