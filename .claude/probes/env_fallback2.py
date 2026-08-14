"""Force the hand-written fallback and verify parsing of tricky lines."""
import json, os, tempfile, sys, types

# Block dotenv import to force the fallback path
class Blocker:
    def find_module(self, name, path=None):
        if name == "dotenv":
            return self
        return None
    def load_module(self, name):
        raise ImportError("blocked")
sys.meta_path.insert(0, Blocker())
for m in list(sys.modules):
    if m == "dotenv" or m.startswith("dotenv."):
        del sys.modules[m]

content = ('# comment line\nSECRET_KEY=abc123\nUNTELL_API_KEY="quoted value"\n'
           'UNTELL_HOST = spaced value\nEMPTY=\nQUOTED_SINGLE=\'single quoted\'\n'
           'CRLF_KEY=value\r\n# another\nMALFORMED_NO_EQUALS\nUNICODE_KEY=café\n')
with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
    f.write(content)
    path = f.name

from untell._env import load_env
ok = load_env(path)
out = {k: os.environ.get(k) for k in
       ["SECRET_KEY", "UNTELL_API_KEY", "UNTELL_HOST", "EMPTY", "QUOTED_SINGLE", "CRLF_KEY", "MALFORMED_NO_EQUALS", "UNICODE_KEY"]}
print(json.dumps({"loaded": ok, "env": out}, indent=1))
