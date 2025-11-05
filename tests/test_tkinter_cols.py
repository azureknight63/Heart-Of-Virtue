"""Test actual tkinter column positions for unicode"""

import tkinter as tk

root = tk.Tk()
text = tk.Text(root)
text.pack()

# Insert the exact text
text_content = "#    J↑    #"
text.insert(1.0, text_content)

print(f"Inserted text: {repr(text_content)}")
print(f"Python string length: {len(text_content)}")
print(f"Text widget content: {repr(text.get('1.0', '1.end'))}")

# Get the actual end position
end_pos = text.index('1.end')
print(f"Text widget '1.end': {end_pos}")

# Try to find J by searching
search_result = text.search('J', '1.0')
print(f"Search for 'J': {search_result}")

search_result = text.search('↑', '1.0')
print(f"Search for '↑': {search_result}")

# Get character by character using search
line_num = 1
for i in range(1, 20):
    char = text.get(f'{line_num}.{i}', f'{line_num}.{i+1}')
    if not char:
        break
    print(f"  Column {i}: {repr(char)}")

text.destroy()
root.destroy()
