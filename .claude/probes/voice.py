"""voice: profile rates per 100w comparable; same text -> zero distance; thin sample warns."""
import json, os, logging
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.voice import style_profile, voice_gaps, voice_distance

out = {}
sample = ("I walked down to the corner store and bought some milk, but it started raining on the way home, "
          "so I stopped under a tree for a while. It was a pretty quiet evening and I didn't mind waiting. "
          "When the rain let up I kept going, and the street was empty by then.")
draft = ("I walked to the corner store for milk, and rain began falling on the walk home. I paused under a tree "
         "to wait, and the evening stayed quiet. When it cleared I continued, finding the street empty.")
p = style_profile(sample)
out["six_features"] = sorted(p.keys()) == ["burst", "comma_per_100w", "contractions_per_100w", "first_person_per_100w", "mean_word_len", "sent_len"]
out["rates_comparable"] = all(0 <= v for v in p.values())
out["self_distance_zero"] = voice_distance(sample, sample) == 0.0
gaps = voice_gaps(sample, draft)
out["gaps_keys"] = sorted(gaps.keys()) == sorted(p.keys())
print(json.dumps(out, indent=1))
