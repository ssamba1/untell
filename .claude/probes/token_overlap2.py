import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.quality import token_overlap

out = {}
# Dice exactness
out["identical"] = token_overlap("The system reads the file.", "The system reads the file.")
out["disjoint"] = token_overlap("The system reads the file.", "Weather is lovely today outside.")
out["partial"] = round(token_overlap("The system reads the file.", "The system writes the file."), 4)
# both empty
out["both_empty"] = token_overlap("", "")
# one empty
out["one_empty"] = token_overlap("The system reads.", "")
# CJK char-bigram fallback (under 2 words)
out["cjk_identical"] = token_overlap("人工智能", "人工智能")
out["cjk_different"] = token_overlap("人工智能", "机器学习")
# punct-only vs words
out["punct_only"] = token_overlap("!!!", "!!!")
out["punct_vs_words"] = token_overlap("!!!", "The system reads.")
print(json.dumps(out, indent=1))
