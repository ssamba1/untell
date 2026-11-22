# One trailing space decides `hc3_roberta`'s verdict on short text

**Measured 2026-11-22** with `python -m untell.bench.trailing_space` on the Liang et al. (2023)
corpus ([data, MIT](https://github.com/Weixin-Liang/ChatGPT-Detector-Bias)). Each document was
scored twice with the model's input unnormalised (`raw:<detector>`): once as written, once with a
single space appended. The words and every visible character are identical. Flagged = score ≥ 0.5.
Per-document scores: [`trailing-space/liang-2023.json`](trailing-space/liang-2023.json).

## `hc3_roberta` (Hello-SimpleAI/chatgpt-detector-roberta)

| group | label | n | flagged as written | flagged with a trailing space | verdict flips |
|---|---|---:|---:|---:|---:|
| TOEFL essays, non-native writers | human | 91 | 36 | **0** | 36 |
| US 8th-grade essays | human | 88 | 7 | 7 | 0 |
| US college admissions essays | human | 70 | 12 | 12 | 0 |
| GPT-3 CS224N abstracts | AI | 145 | 88 | **0** | 88 |
| GPT-3 college essays | AI | 31 | 29 | 16 | 13 |

AUROC (AI vs human) falls from **0.784** to **0.326** when every text carries the space — below
chance.

**Every flagged text that fits in one scoring window flips.** The TOEFL essays (median 104 words)
and GPT-3 abstracts (median 120) fit in one window, and all 36 + 88 flagged verdicts reverse. The
US essays are longer (median 378 and 632 words), are scored as several windows with the maximum
taken, and an earlier window keeps the flag. So on short text — most essays, forum answers,
abstracts and admissions responses — this model's verdict is decided by an invisible character.
A trailing newline does not have the effect (0.9098 → 0.8133 on the first essay) and a leading
space does not either (→ 0.9498).

## `roberta_openai` (openai-community/roberta-base-openai-detector)

| group | label | n | flagged as written | flagged with a trailing space | verdict flips |
|---|---|---:|---:|---:|---:|
| TOEFL essays, non-native writers | human | 91 | 53 | 45 | 10 |
| US 8th-grade essays | human | 88 | 25 | 26 | 1 |
| US college admissions essays | human | 70 | 17 | 17 | 0 |
| GPT-3 CS224N abstracts | AI | 145 | 60 | 55 | 5 |
| GPT-3 college essays | AI | 31 | 20 | 20 | 0 |

Smaller but real: 9 of the 53 flagged TOEFL essays (17%) are cleared by the space, and one
unflagged essay becomes flagged.

**A cross-check.** Run locally today, `roberta_openai` flags 53 of 91 TOEFL essays — exactly the
53 of 91 Liang et al. recorded for the same Hugging Face-hosted model in early 2023
([report card](liang-2023/cards/openai-roberta-2023.md)). Same model, same essays, same verdicts
three years apart, which is evidence that both pipelines read the essays the same way.

## What it means

- **For untell:** its own scoring path normalised spaces before a newline but not at the very end
  of a text, so it carried this reversal until the fix in the same commit as this note. The
  normalised path now scores the essay 0.9098 with or without the space.
- **For anyone deploying these models without normalisation** — demos, plugins, research code —
  a verdict on short text can be reversed by how the text was copied.
- **For commercial detectors:** unknown, because none has been measured live here. The stability
  test now includes this edit (N12), so a brief against any detector, including one scored by hand
  in a web interface, will show it if the detector shares the shortcut.

This is a property of these two open models and this corpus. It does not show that a trailing space
makes AI text pass a commercial detector, and it was not looked for in one.
