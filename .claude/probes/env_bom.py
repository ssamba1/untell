import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell._env import load_env

out = {}
# BOM-stripped file
with open("/tmp/_env_bom_test.env", "wb") as f:
    f.write(b"\xef\xbb\xbfUNTELL_BOM_KEY=value123\n")
os.environ.pop("UNTELL_BOM_KEY", None)
load_env("/tmp/_env_bom_test.env")
out["bom_stripped"] = os.environ.get("UNTELL_BOM_KEY") == "value123"
# quoted value with # inside quotes
with open("/tmp/_env_quote_test.env", "w", encoding="utf-8") as f:
    f.write('UNTELL_Q_KEY="value with # hash"\nUNTELL_Q2=\'single # quote\'\n')
os.environ.pop("UNTELL_Q_KEY", None)
os.environ.pop("UNTELL_Q2", None)
load_env("/tmp/_env_quote_test.env")
out["hash_in_quotes_kept"] = os.environ.get("UNTELL_Q_KEY") == "value with # hash"
out["single_quote"] = os.environ.get("UNTELL_Q2") == "single # quote"
# real env wins over file
with open("/tmp/_env_win_test.env", "w", encoding="utf-8") as f:
    f.write("UNTELL_WIN_KEY=from_file\n")
os.environ["UNTELL_WIN_KEY"] = "from_env"
load_env("/tmp/_env_win_test.env")
out["env_wins"] = os.environ.get("UNTELL_WIN_KEY") == "from_env"
del os.environ["UNTELL_WIN_KEY"]
print(json.dumps(out, indent=1))
