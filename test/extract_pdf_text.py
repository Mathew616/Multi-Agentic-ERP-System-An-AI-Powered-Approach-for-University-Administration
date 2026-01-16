#!/usr/bin/env python
"""Extract text from the PDF to debug"""

import fitz

pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

# Get first 3 pages of text
for i in range(min(3, len(pdf))):
    page = pdf[i]
    text = page.get_text()
    print(f"--- PAGE {i+1} ({len(text)} chars) ---")
    print(text[:1500])
    print("\n" + "="*70 + "\n")
