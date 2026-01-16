#!/usr/bin/env python
"""Debug why quoted pattern doesn't match"""

import re
import fitz

pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

full_text = ""
for page in pdf:
    full_text += page.get_text()

# Try the quoted pattern
patterns = [
    r'"([^"]{10,150})"',
    r"'([^']{10,150})'",
    r'""([^"]{10,150})""',
]

print("Testing quoted patterns:")
for pattern in patterns:
    matches = re.findall(pattern, full_text)
    print(f"\nPattern: {pattern}")
    print(f"Matches found: {len(matches)}")
    for m in matches[:3]:
        print(f"  - {m}")

# Let's look for the exact string
if '"FOSS Bangalore meetup -2024"' in full_text:
    print("\n✅ String exists in text")
    # Find context
    idx = full_text.find('"FOSS')
    print(f"Context: {full_text[max(0, idx-50):idx+100]}")
    print()
    print(repr(full_text[idx:idx+30]))
else:
    print("\n❌ String NOT found")
    
# Check what quotes are being used
print("\n\nSearching for all quote characters in text:")
for i, c in enumerate(full_text):
    if c in ['"', "'", '"', '"', ''', ''']:
        print(f"  Position {i}: {repr(c)} - context: {repr(full_text[max(0, i-20):i+20])}")
