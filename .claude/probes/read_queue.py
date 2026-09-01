"""Read the census read queue: clone, extract what a reader needs, delete."""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path("/home/user/untell")
WORK = Path(sys.argv[1]); WORK.mkdir(parents=True, exist_ok=True)
OUT = Path(sys.argv[2])
SKIP = {"suraj-ranganath/StealthRL","xuange520/unmark","pablocaeg/sloptotal",
        "kinit-sk/multisocial","heyongxin233/DETree","lynote-ai/humanize-text",
        "stef41/lmscan","Jroo1053/MGTMark","satyamshivam13/AI_Text_Detector"}
rows = json.loads((ROOT/".claude/probes/census-2026-09-01-multiangle.inspected.json").read_text())
q = [r for r in rows if r.get("needs_read") and r.get("evidence")=="source"
     and r["name"] not in SKIP and r["name"].count("/")==1]
def rank(r):
    s = r["tree"]["signals"]
    return (len(s["detector_in_loop"])*2 + len(s["meaning_verification"])*2
            + len(s["trains_a_model"]) + len(s["subgroup_fairness"]), r.get("stars") or 0)
q.sort(key=rank, reverse=True)
start, n = int(sys.argv[3]), int(sys.argv[4])
done = json.loads(OUT.read_text()) if OUT.exists() else []
seen = {d["name"] for d in done}
for r in q[start:start+n]:
    name = r["name"]
    if name in seen: continue
    d = WORK / name.replace("/", "__")
    shutil.rmtree(d, ignore_errors=True)
    p = subprocess.run(["git","clone","--depth","1","--quiet",
                        f"https://github.com/{name}", str(d)], capture_output=True, timeout=240)
    rec = {"name": name, "stars": r.get("stars"), "category_prior": r["category"],
           "signals": {k: v for k, v in r["tree"]["signals"].items() if v}}
    if p.returncode != 0:
        rec["error"] = (p.stderr.decode()[-120:] or "clone failed").strip()
    else:
        rd = next((f for f in d.iterdir() if f.is_file() and f.name.lower().startswith("readme")), None)
        txt = rd.read_text(encoding="utf-8", errors="replace")[:2500] if rd else ""
        txt = re.sub(r"<[^>]+>|\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)|!\[[^\]]*\]\([^)]*\)", " ", txt)
        rec["readme"] = " ".join(txt.split())[:700]
        rec["top"] = sorted(x.name for x in d.iterdir() if not x.name.startswith("."))[:14]
        low = " ".join(rec["readme"].lower().split())
        rec["is_detector"] = any(w in low for w in
            ("detector", "detection", "detect ai", "classifier", "benchmark"))
        rec["fairness_words"] = [w for w in ("subgroup","non-native","esl ","demographic","dialect",
                                             "bias","fairness","false positive")
                                 if w in low]
        shutil.rmtree(d, ignore_errors=True)
    done.append(rec)
    OUT.write_text(json.dumps(done, indent=2, ensure_ascii=False))
    print(f"  {len(done):3} {name}", file=sys.stderr)
print(f"wrote {len(done)} records to {OUT}")
