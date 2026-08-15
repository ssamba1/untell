import json
from untell.scripts.score import _invisible_char_warning, _homoglyph_warning

out = {}
# invisible chars detected
out["zwsp_detected"] = _invisible_char_warning("a\u200bb") is not None
out["clean_no_warning"] = _invisible_char_warning("plain text") is None
out["bidi_detected"] = _invisible_char_warning("x\u202ey") is not None
# homoglyph: Cyrillic a in Latin word
out["cyrillic_detected"] = _homoglyph_warning("The systеm reads the file.") is not None
out["latin_clean"] = _homoglyph_warning("The system reads the file.") is None
# all-confusable word (pure Cyrillic lookalike)
out["all_confusable"] = _homoglyph_warning("Привет") is not None or _homoglyph_warning("Привет") is None
print(json.dumps(out, indent=1))
