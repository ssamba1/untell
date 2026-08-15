import json, os, subprocess, sys
os.environ["UNTELL_LITE_NO_TORCH"] = "1"

env = {**os.environ, "PYTHONPATH": ""}
out = {}
# clean text (varied lengths, 60+ words)
clean = ("The kettle boiled while I read the mail. Outside, the rain had stopped and the street "
         "was drying in patches. My neighbor waved from across the fence, then went back to his "
         "garden. I poured the tea and sat by the window for a while, watching the clouds break. "
         "It was one of those quiet afternoons that feel longer than they are.")
r = subprocess.run([sys.executable, "-m", "untell.scripts.verify", "--tier", "lite", clean],
                   capture_output=True, text=True, env=env, timeout=180)
out["clean_rc"] = r.returncode
# AI text (uniform, formulaic)
ai = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
      "Additionally, the system facilitates seamless integration of the components. "
      "In conclusion, the results demonstrate significant improvement across the board. "
      "Furthermore, the architecture enables efficient processing of the data. "
      "Ultimately, the platform ensures optimal performance for every user.")
r2 = subprocess.run([sys.executable, "-m", "untell.scripts.verify", "--tier", "lite", ai],
                    capture_output=True, text=True, env=env, timeout=180)
out["ai_rc"] = r2.returncode
print(json.dumps(out, indent=1))
