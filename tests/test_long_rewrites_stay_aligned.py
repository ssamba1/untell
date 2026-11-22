"""Over 6,000 words, `aligned_chunks` must cut each side in proportion to ITS OWN length.

The large-document path cut the rewrite at the SOURCE's word positions. A rewrite that shortens
the text drifts further out of step at each cut, so the last pairs compared different paragraphs:
MEASURED on a 7,456-word document rewritten to 6,225 words, the minimum chunk similarity fell to
0.27-0.31 (whole-document 0.77) and the meaning gate rejected every rewrite of every document over
6,000 words. After the fix the same pair scores 0.703.
"""

from __future__ import annotations

from untell.text_split import aligned_chunks


def _doc(n_paras: int, drop_every: int = 0) -> str:
    paras = []
    for i in range(n_paras):
        words = [f"p{i}w{j}" for j in range(60)]
        if drop_every:
            words = [w for j, w in enumerate(words) if j % drop_every]
        paras.append(" ".join(words))
    return "\n\n".join(paras)


def test_a_shortened_rewrite_is_cut_in_step_with_its_source():
    a = _doc(120)             # 7,200 words: the proportional path
    b = _doc(120, drop_every=5)  # 20% shorter, every paragraph kept in order
    chunks = aligned_chunks(a, b)
    assert len(chunks) > 10
    ca, cb = chunks[-1]
    # The last chunk of each side must come from the same paragraphs.
    para_a = {w.split("w")[0] for w in ca.split()}
    para_b = {w.split("w")[0] for w in cb.split()}
    assert para_a & para_b, "last chunks compare different paragraphs: the cuts drifted"
    assert b.split()[-1] == cb.split()[-1] and a.split()[-1] == ca.split()[-1]
