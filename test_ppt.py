import os
from pptx import Presentation
import lyrics_to_ppt

prs = Presentation('template.pptx')
print("Layout names:")
for idx, l in enumerate(prs.slide_layouts):
    print(f"[{idx}] {l.name}")
    for p in l.placeholders:
        print(f"  - {p.name}")

v = lyrics_to_ppt.parse_lyrics_text(open('주를 바라보며.txt', 'r', encoding='utf-8').read())
print("\nParsed Dict:")
print(v)

print("\nAppended slides output preview:")
for chunk in lyrics_to_ppt.chunk_text(v['A'], 2):
    print("CHUNK:", repr(chunk))

