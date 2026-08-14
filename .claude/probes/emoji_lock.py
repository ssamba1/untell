"""preserve.lock with emoji/ZWJ/regional-indicator sequences: no corruption, round-trip exact."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.preserve import lock, restore

out = {}
cases = {
    "family_emoji": "The team 👨‍👩‍👧‍👦 works well here. Done.",
    "flags": "Support 🇺🇸 and 🇬🇧 users. Done.",
    "zwj_seq": "The 🧑‍💻 developer committed. Done.",
    "skin_tones": "👍🏽 and 👍🏻 are different. Done.",
    "vs16": "The ❤️ is red. Done.",
}
for name, t in cases.items():
    masked, mapping = lock(t)
    restored = restore(masked, mapping)
    out[name] = {
        "roundtrip_exact": restored == t,
        "emoji_preserved": "👨" in restored or "🇺" in restored or "🧑" in restored or "👍" in restored or "❤" in restored,
        "sentinel_count": sum(1 for k in mapping if k.startswith("⟦")),
    }
print(json.dumps(out, indent=1))
