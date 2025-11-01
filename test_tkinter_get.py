"""Test tkinter text widget get() behavior"""

import tkinter as tk

root = tk.Tk()
text = tk.Text(root)
text.pack()

# Insert text
text.insert(1.0, "#    J↑    #")

# Try different get operations
print("Testing text.get() on: '#    J↑    #'")
print(f"get(1.1, 1.2) = {repr(text.get('1.1', '1.2'))}")  # Should be '#'
print(f"get(1.2, 1.3) = {repr(text.get('1.2', '1.3'))}")  # Should be ' '
print(f"get(1.6, 1.7) = {repr(text.get('1.6', '1.7'))}")  # Should be 'J'
print(f"get(1.7, 1.8) = {repr(text.get('1.7', '1.8'))}")  # Should be '↑'
print(f"get(1.6, 1.8) = {repr(text.get('1.6', '1.8'))}")  # Should be 'J↑'

text.destroy()
root.destroy()
