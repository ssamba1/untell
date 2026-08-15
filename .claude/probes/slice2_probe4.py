"""Probe NER single-token PERSON over-locks on common words."""
import sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
import importlib.util
if importlib.util.find_spec("en_core_web_sm") is None:
    print("NO NER MODEL")
    sys.exit(0)
import spacy
nlp = spacy.load("en_core_web_sm")

# Common words in sentence contexts (capitalized at sentence start, like the probe found)
words = """lunch dinner breakfast coffee meeting work home school office city state country company team
result results study data figure table section paper research analysis report email article
comments feedback status update support contact security terms privacy search settings
may will mark bill rose lily holly hunter harper mason logan carter chase clay cole drake
grant reed stone wolf fox crow robin wren jade amber ivy joy hope faith grace summer autumn
winter june march april august jack max sam pat rob tom sue call open start stop check test
run build deploy release review approve submit cancel login logout view edit save delete
create update insert remove add list map show find give take make use need want know think
time day week month year hour minute second value number group class type order level part
way thing place point line page note book list name form plan job task item file code mode
state case hand head eye heart mind body life world water air sun moon star earth fire""".split()

tagged = []
for w in words:
    doc = nlp(f"{w.capitalize()} is a good thing to consider here.")
    for e in doc.ents:
        if e.label_ == "PERSON" and len(e.text.split()) == 1:
            tagged.append((w, e.text))

print("single-token PERSON over-locks:", tagged)
