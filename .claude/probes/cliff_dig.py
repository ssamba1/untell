"""Dig the 39->40 word cliff: which signal flips at 40?"""
import os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.perplexity_burstiness import lite_score, _repetition_signal, _common_ratio, _burstiness, _sentences, _WORD
for n in (5, 10, 20, 38, 39, 40, 41, 50):
    text = " ".join(f"w{i}" for i in range(n))
    s = lite_score(text)
    rep = _repetition_signal(text)
    common = _common_ratio(text)
    sents = _sentences(text)
    nonempty = [x for x in sents if _WORD.findall(x)]
    burst = _burstiness(sents) if len(nonempty) >= 2 else None
    print(f"n={n:3d} score={s if s is None else round(s,4)} rep={round(rep,4)} common={round(common,4)} burst={burst if burst is None else round(burst,4)} nsents={len(nonempty)}")
