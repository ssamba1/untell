"""unicode_tricks: scrub removes hidden classes, keeps legitimate text; count agrees with scrub."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks.unicode_tricks import scrub_hidden, count_hidden, homoglyph_substitute

out = {}
# ZWSP + bidi + variation selector + zero-width joiner all removed
dirty = "a\u200bb\u2066c\u2069d\ufe0fe\u200df"
clean = scrub_hidden(dirty)
out["zwsp_gone"] = "\u200b" not in clean
out["bidi_gone"] = "\u2066" not in clean and "\u2069" not in clean
out["vs_gone"] = "\ufe0f" not in clean
out["zwj_gone"] = "\u200d" not in clean
out["visible_kept"] = clean.replace("e", "") == "abcd" or "abcd" in clean
# count agrees: dirty count > 0, clean count == 0
out["count_dirty"] = count_hidden(dirty) > 0
out["count_clean"] = count_hidden(clean) == 0
# legitimate text untouched (accents are legitimate composition)
normal = "café naïve — résumé"
out["accents_kept"] = scrub_hidden(normal) == normal
# homoglyph substitute changes text but keeps length-ish
sub = homoglyph_substitute("The quick brown fox jumps over the lazy dog.", rate=1.0)
out["homoglyph_changed"] = sub != "The quick brown fox jumps over the lazy dog."
print(json.dumps(out, indent=1))
