import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.roles import _conditional_pair, _connectives, _load

out = {}
out["if_then"] = _conditional_pair("If the file loads, then the parser runs.")
out["if_only"] = _conditional_pair("If the file loads, the parser runs.")
out["no_cond"] = _conditional_pair("The parser runs when the file loads.")
out["unless"] = _conditional_pair("Unless the file loads, the parser waits.")
nlp = _load()
conn = _connectives(nlp("because the file loads"))
out["because"] = "because" in conn
out["conn_type"] = type(conn).__name__
conn2 = _connectives(nlp("The parser runs."))
out["plain_has_none"] = not any(c in ("because", "if", "unless") for c in conn2)
print(json.dumps(out, indent=1))
