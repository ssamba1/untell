"""substitute_once with article context: does an a/an flip when the replacement needs the other article?"""
import json
from untell.attacks.word_importance import substitute_once, _SYN

out = {}
# Cases from the module's own docstring: "an intricate system" -> must become "a complex system"
for text, word, repl in [
    ("They built an intricate system.", "intricate", "complex"),
    ("It was an innovative approach.", "innovative", "new"),
    ("The team wrote a comprehensive report.", "comprehensive", "extensive"),
]:
    out[text] = substitute_once(text, word, repl)
print(json.dumps(out, indent=1))
