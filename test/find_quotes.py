#!/usr/bin/env python
"""Find the exact quote characters used"""

import fitz

pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

full_text = ""
for page in pdf:
    full_text += page.get_text()

# Find the FOSS meetup title line
lines = full_text.split('\n')
for i, line in enumerate(lines):
    if 'FOSS Bangalore' in line or 'Bangalore meetup' in line:
        print(f"Line {i}: {line}")
        print(f"Repr: {repr(line)}")
        print()
