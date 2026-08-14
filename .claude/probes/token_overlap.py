import json
from untell.scripts.quality import token_overlap

out = {}
out["identical"] = token_overlap("the cat sat on the mat", "the cat sat on the mat") == 1.0
out["disjoint"] = token_overlap("the cat sat", "a dog ran fast") == 0.0
out["partial"] = round(token_overlap("the cat sat on the mat", "the cat lay on the mat"), 4)
out["empty_both"] = token_overlap("", "")
out["empty_one"] = token_overlap("the cat", "")
out["cjk_chars"] = round(token_overlap("系统读取文件", "系统读取文件"), 4)
out["cjk_diff"] = round(token_overlap("系统读取文件", "处理记录顺序"), 4)
out["punct_only"] = token_overlap("!!! ???", "!!! ???")
out["punct_vs_words"] = token_overlap("!!!", "hello world")
print(json.dumps(out, indent=1))
