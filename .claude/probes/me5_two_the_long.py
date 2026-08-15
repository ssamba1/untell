"""Isolate the too-few-openers guard: exactly 2 sentences, both 'The', >= 60 words."""
import untell.scripts.tells as T

S1 = ("The committee reviewed the annual budget report and then approved the revised "
      "spending plan for the coming fiscal year without any further discussion among "
      "the members present at the meeting. ")
S2 = ("The directors supported the new initiative after examining the projected costs "
      "and expected benefits across every department in the organisation and then "
      "recommended immediate implementation of the entire plan without delay. ")
text = S1 + S2
words = len(T._WORD.findall(text))
starts = [T._WORD.findall(s)[0].lower() for s in T._sentences(text) if T._WORD.findall(s)]
print(f"words={words} starts={starts} dupes={len(starts)-len(set(starts))}")
print(f"_duplicate_sentence_starts -> {T._duplicate_sentence_starts(text)}")
