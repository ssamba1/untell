"""_env fallback parser: comments, quotes, CRLF, unicode, malformed lines."""
import json, os, tempfile
os.environ["UNTELL_LITE_NO_TORCH"] = "1"

content = """# comment line
SECRET_KEY=abc123
UNTELL_API_KEY="quoted value"
UNTELL_HOST = spaced value
EMPTY=
QUOTED_SINGLE='single quoted'
CRLF_KEY=value\r
# another comment
MALFORMED_NO_EQUALS
UNICODE_KEY=café
"""
with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
    f.write(content)
    path = f.name

from untell._env import load_env
loaded = load_env(path)
print(json.dumps(loaded, indent=1))
