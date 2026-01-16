#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test the fixed extraction"""

import sys
import os
sys.path.insert(0, r'E:\Projects\MAJOR PROJECT\backend')
os.chdir(r'E:\Projects\MAJOR PROJECT\backend')

from agents.field_extractor import RobustFieldExtractor
import fitz

# Extract text from PDF
pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

full_text = ""
for page in pdf:
    full_text += page.get_text()

print("="*70)
print("[TEST EXTRACTION WITH FIX]")
print("="*70)
print(f"PDF: FOSS_REPORT_Template_1V.pdf")
print(f"Text length: {len(full_text)} chars\n")

# Extract fields using the fixed extractor
extractor = RobustFieldExtractor()
extracted = extractor.extract_all_fields(full_text, "FOSS_REPORT_Template_1V.pdf")

print("\n" + "="*70)
print("[FINAL RESULT]")
print("="*70)
event_name = extracted.get('event_name')
print(f"✓ Event Name: {event_name}")
print(f"✓ Should be: FOSS Bangalore meetup -2024")
print(f"✓ Match: {event_name == 'FOSS Bangalore meetup -2024'}")
print()
print(f"Department: {extracted.get('department')}")
print(f"Date: {extracted.get('date')}")
print(f"Organizer: {extracted.get('organizer')}")
print(f"Venue: {extracted.get('venue')}")
print(f"Confidence: {extracted.get('confidence')}")
