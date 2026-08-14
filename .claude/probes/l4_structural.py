"""L4 liveness: every compiled pattern in structural.py must fire on its known positive."""
import re, json
import untell.rewriter.structural as S

# name -> (pattern, known-positive string)
CASES = {
    "_INTERNAL_CAPS_RE": (S._INTERNAL_CAPS_RE, "aLtErNaTiNg"),
    "_LEADING_MARKER_RE": (S._LEADING_MARKER_RE, "Nevertheless, the result was clear."),
    "_LEADING_SUBORDINATOR_RE": (S._LEADING_SUBORDINATOR_RE, "Although the data was sparse, the trend held."),
    "_ANY_LEADING_MARKER_RE": (S._ANY_LEADING_MARKER_RE, "However, the team agreed."),
    "_TRANSITIONS_RE": (S._TRANSITIONS_RE, "the framework not only improves speed but also accuracy"),
    "_PARTICIPIAL_RE": (S._PARTICIPIAL_RE, "Showing great promise, the method converged."),
    "_NEGATED_CONTRAST_RE": (S._NEGATED_CONTRAST_RE, "it is not X, it is Y"),
    "_INFLATED_COPULA_RE": (S._INFLATED_COPULA_RE, "serves as a testament"),
    "_BOASTS_RE": (S._BOASTS_RE, "the paper boasts"),
    "_VAGUE_ATTR_RE": (S._VAGUE_ATTR_RE, "studies show"),
    "_SEMICOLON_RE": (S._SEMICOLON_RE, "robust; it scales"),
    "_FILLER_OPENER_RE": (S._FILLER_OPENER_RE, "It is important to note that the system works."),
    "_HEDGE_RE": (S._HEDGE_RE, "arguably the best"),
    "_LEADING_SENTINEL_RE": (S._LEADING_SENTINEL_RE, "\u27e6HZ0000\u27e7 text after"),
    "_TERMINATED_RE": (S._TERMINATED_RE, "sentence ends here."),
    "_WORD_RE": (S._WORD_RE, "words"),
    "_CONTRACTED_RE": (S._CONTRACTED_RE, "don't"),
    "_AFTER_SENTENCE_START": (S._AFTER_SENTENCE_START, ". this is lower"),
    "_NOT_A_PROSE_WORD": (S._NOT_A_PROSE_WORD, "abc123"),
    "_LIST_CONTINUES_RE": (S._LIST_CONTINUES_RE, "apples, pears, and oranges"),
}
# contraction table entries
dead = []
alive = {}
for name, (pat, pos) in CASES.items():
    m = pat.search(pos) if hasattr(pat, "search") else None
    alive[name] = bool(m)
    if not m:
        dead.append(name)
# contraction table
n_contr = 0
for item in dir(S):
    if "CONTRACT" in item.upper() or "CONTRACTION" in item.upper():
        n_contr += 1
print(json.dumps({"dead_patterns": dead, "alive": sum(alive.values()), "total": len(alive), "contraction_tables": n_contr}, indent=1))
