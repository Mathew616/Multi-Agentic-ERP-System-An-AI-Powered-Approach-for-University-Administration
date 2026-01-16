#!/usr/bin/env python
"""Debug extraction strategies for FOSS PDF"""

import re
import fitz
import sys
sys.path.insert(0, r'E:\Projects\MAJOR PROJECT\backend')

# Extract text from PDF
pdf_path = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
pdf = fitz.open(pdf_path)

full_text = ""
for page in pdf:
    full_text += page.get_text()

lines = [l.strip() for l in full_text.split("\n") if l.strip() and len(l.strip()) > 2]

print("="*70)
print("[DEBUG EXTRACTION STRATEGIES]")
print("="*70)
print(f"\nTotal lines: {len(lines)}")
print(f"Total text: {len(full_text)} chars\n")

# STRATEGY 1: Quoted/Emphasized Titles
print("STRATEGY 1: Quoted Titles")
print("-" * 70)
quoted_patterns = [
    r'"([^"]{10,150})"',  # Double quotes
    r"'([^']{10,150})'",  # Single quotes
    r'""([^"]{10,150})""',  # Double double quotes
]

for pattern in quoted_patterns:
    matches = re.findall(pattern, full_text)
    if matches:
        print(f"  Pattern: {pattern}")
        for i, match in enumerate(matches, 1):
            title = match.strip()
            print(f"    Match {i}: {title}")

# STRATEGY 1B: Report On / Event On
print("\nSTRATEGY 1B: Report On / Event On Pattern")
print("-" * 70)
report_pattern = r'(?:report\s+on|event\s+on|activity\s+on|seminar\s+on|workshop\s+on|conference\s+on|titled|topic)\s+["\']?([^"\'\.]{8,200}?)["\']?(?:\n|$)'
match = re.search(report_pattern, full_text, re.IGNORECASE | re.MULTILINE)
if match:
    title = match.group(1).strip()
    print(f"  Match: {title}")
else:
    print("  No match")

# STRATEGY 2: Explicit Labels
print("\nSTRATEGY 2: Explicit Labels")
print("-" * 70)
label_patterns = [
    r"(?:event|title|program|activity|topic|subject)\s*[:\-]\s*(.+?)(?:\n|$)",
    r"(?:name\s+of\s+(?:the\s+)?(?:event|program|workshop|seminar|conference))\s*[:\-]\s*(.+?)(?:\n|$)",
]

for pattern in label_patterns:
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        title = title.split('\n')[0]
        title = title.rstrip(',').rstrip()
        print(f"  Pattern matched: {pattern}")
        print(f"  Match: {title}")
        
        # Check if it's a person name
        name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z])?(?:\s+[A-Z][a-z]+)?\.?,?\s*$'
        if re.match(name_pattern, title):
            print(f"  ⚠️  This looks like a PERSON NAME - should be skipped!")
        else:
            print(f"  ✓ Not a person name")

# STRATEGY 4: Event Keywords
print("\nSTRATEGY 4: Lines with Event Keywords")
print("-" * 70)
for i, line in enumerate(lines[:30]):
    words = line.split()
    if 3 <= len(words) <= 25 and len(line) > 12:
        if not any(skip in line.upper() for skip in ["UNIVERSITY", "DEPARTMENT", "SCHOOL", "SUBMITTED", "SUPERVISED"]):
            if not re.match(r'^\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}', line):
                line_upper = line.upper()
                if any(kw in line_upper for kw in ["WORKSHOP", "SEMINAR", "CONFERENCE", "TRAINING", "LECTURE", "MEETUP", "TALK", "SYMPOSIUM"]):
                    print(f"  Line {i}: {line}")

# STRATEGY 5: All-caps lines
print("\nSTRATEGY 5: All-caps Prominent Lines")
print("-" * 70)
for i, line in enumerate(lines[:30]):
    words = line.split()
    if 3 <= len(words) <= 20 and len(line) > 15:
        # Check uppercase ratio
        upper_ratio = sum(1 for c in line if c.isupper()) / len(line)
        if upper_ratio >= 0.7:
            print(f"  Line {i}: {line} (upper_ratio: {upper_ratio:.2f})")
