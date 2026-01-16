#!/usr/bin/env python
"""Search for 'Mr Biju K Nair' in PDF"""

import fitz

pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

full_text = ""
for page in pdf:
    full_text += page.get_text() + "\n"

# Search for the phrase
if "Mr Biju K Nair" in full_text or "Biju" in full_text:
    print("FOUND 'Mr Biju K Nair' or 'Biju' in PDF!")
    # Find context
    lines = full_text.split('\n')
    for i, line in enumerate(lines):
        if 'Biju' in line or 'biju' in line.lower():
            start = max(0, i-2)
            end = min(len(lines), i+3)
            print(f"\n[Lines {start}-{end}]")
            for j in range(start, end):
                print(f"  {j}: {lines[j]}")
else:
    print("NOT FOUND in PDF")
    
# Also check for the correct event title
if '"FOSS Bangalore meetup -2024"' in full_text:
    print("\n✅ FOUND correct event title")
