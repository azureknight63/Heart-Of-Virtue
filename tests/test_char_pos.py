"""Check character positions in text"""

text = "#    J↑    #"
print(f"Text: {repr(text)}")
print(f"Length: {len(text)}")

for i, char in enumerate(text, 1):
    print(f"  Pos {i}: {repr(char)} (code {ord(char)})")
