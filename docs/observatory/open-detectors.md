# Open AI-text detectors, audited

Each detector run as its Hugging Face model card says (`hf:<model>`: raw text, truncated at the model's limit), flagged at its default 0.5, on human writing from before 2022 and on GPT-3 text. Every figure is read from the report cards in [`open-detectors/`](open-detectors/) by `untell/bench/leaderboard.py`.

## False positives on human writing

| detector | all human | TOEFL, non-native | US 8th grade | US college | CS224N abstracts | PERSUADE: English learners | PERSUADE: others |
|---|---:|---:|---:|---:|---:|---:|---:|
| `PirateXX/AI-Content-Detector` | 2.0% (24/1194) | 19.8% (18/91) | 0.0% (0/88) | 0.0% (0/70) | 0.0% (0/145) | 0.5% (2/400) | 1.0% (4/400) |
| `desklib/ai-text-detector-v1.01` | 15.5% (185/1194) | 52.7% (48/91) | 6.8% (6/88) | 21.4% (15/70) | 51.0% (74/145) | 5.0% (20/400) | 5.5% (22/400) |
| `fakespot-ai/roberta-base-ai-text-detection-v1` | 21.4% (255/1194) | 65.9% (60/91) | 0.0% (0/88) | 30.0% (21/70) | 100.0% (145/145) | 1.5% (6/400) | 5.8% (23/400) |
| `openai-community/roberta-large-openai-detector` | 2.8% (33/1194) | 15.4% (14/91) | 4.5% (4/88) | 0.0% (0/70) | 3.4% (5/145) | 1.0% (4/400) | 1.5% (6/400) |
| `rasbt/ai-text-detector-modernbert` | 0.6% (7/1194) | 0.0% (0/91) | 0.0% (0/88) | 0.0% (0/70) | 0.7% (1/145) | 1.2% (5/400) | 0.2% (1/400) |

## Detection, stability and one trailing space

| detector | AUROC | recall at 0.5 | recall, FPR ≤ 1% | formatting-only flips | trailing space: TOEFL flags cleared | trailing space: GPT-3 flags cleared |
|---|---:|---:|---:|---:|---:|---:|
| `PirateXX/AI-Content-Detector` | 0.759 | 8.8% (31/352) | 4.3% | 0.0% (0/59) | 3 of 19 | 4 of 13 |
| `desklib/ai-text-detector-v1.01` | 0.984 | 98.0% (345/352) | 75.6% | 8.5% (5/59) | 0 of 48 | 0 of 145 |
| `fakespot-ai/roberta-base-ai-text-detection-v1` | 0.984 | 99.7% (351/352) | 72.2% | 0.0% (0/59) | 22 of 62 | 0 of 145 |
| `openai-community/roberta-large-openai-detector` | 0.770 | 16.2% (57/352) | 4.8% | 0.0% (0/59) | 2 of 14 | 3 of 43 |
| `rasbt/ai-text-detector-modernbert` | 0.944 | 21.0% (74/352) | 26.4% | 0.0% (0/59) | — | 2 of 7 |

## By race (PERSUADE held-out half, US students)

| detector | American Indian/Alaskan Native | Asian/Pacific Islander | Black/African American | Hispanic/Latino | Two or more races/Other | White |
|---|---:|---:|---:|---:|---:|---:|
| `PirateXX/AI-Content-Detector` | 0.0% (0/3) | 1.2% (1/84) | 0.0% (0/112) | 0.9% (3/351) | 0.0% (0/17) | 0.9% (2/233) |
| `desklib/ai-text-detector-v1.01` | 33.3% (1/3) | 3.6% (3/84) | 6.2% (7/112) | 6.0% (21/351) | 5.9% (1/17) | 3.9% (9/233) |
| `fakespot-ai/roberta-base-ai-text-detection-v1` | 0.0% (0/3) | 3.6% (3/84) | 1.8% (2/112) | 1.4% (5/351) | 5.9% (1/17) | 7.7% (18/233) |
| `openai-community/roberta-large-openai-detector` | 0.0% (0/3) | 2.4% (2/84) | 0.9% (1/112) | 1.7% (6/351) | 0.0% (0/17) | 0.4% (1/233) |
| `rasbt/ai-text-detector-modernbert` | 0.0% (0/3) | 2.4% (2/84) | 0.9% (1/112) | 0.6% (2/351) | 0.0% (0/17) | 0.4% (1/233) |

## Recommended thresholds (≤ 5% false positives on the fit corpus)

Each threshold is fitted on 868 pre-2022 human documents (calibration v2's fit corpus) and evaluated, untouched, on the held-out corpora above ([`thresholds.json`](open-detectors/thresholds.json), from `untell/bench/thresholds.py`).

| detector | default 0.5 | recommended | human false positives | TOEFL | AI recall |
|---|---:|---:|---:|---:|---:|
| `fakespot-ai/roberta-base-ai-text-detection-v1` | 0.5 | 0.5381 | 21.4% (255/1194) → **20.9% (249/1194)** | 65.9% (60/91) → **63.7% (58/91)** | 99.7% (351/352) → 99.7% (351/352) |
| `openai-community/roberta-large-openai-detector` | 0.5 | 0.1372 | 2.8% (33/1194) → **6.1% (73/1194)** | 15.4% (14/91) → **26.4% (24/91)** | 16.2% (57/352) → 35.2% (124/352) |
| `PirateXX/AI-Content-Detector` | 0.5 | 0.0188 | 2.0% (24/1194) → **6.8% (81/1194)** | 19.8% (18/91) → **44.0% (40/91)** | 8.8% (31/352) → 25.6% (90/352) |
| `desklib/ai-text-detector-v1.01` | 0.5 | 0.8206 | 15.5% (185/1194) → **7.5% (89/1194)** | 52.7% (48/91) → **36.3% (33/91)** | 98.0% (345/352) → 93.5% (329/352) |
| `rasbt/ai-text-detector-modernbert` | 0.5 | 0.9979 | 0.6% (7/1194) → **0.3% (4/1194)** | 0.0% (0/91) → **0.0% (0/91)** | 21.0% (74/352) → 12.8% (45/352) |

Rates on the 'all human' column pool corpora of different sizes and registers; read the per-corpus columns. 'Flags cleared' counts texts flagged as written and not flagged once one space is appended (identical words). Card details, including 95% intervals for every rate, are in each detector's `.md` card.
