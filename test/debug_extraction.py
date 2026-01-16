#!/usr/bin/env python
"""Debug script to test field extraction directly"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.agents.field_extractor import RobustFieldExtractor
from backend.agents.ocr_agent import OcrAgent

# Read your test PDF
test_file = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'

if os.path.exists(test_file):
    print(f'Testing with: {test_file}')
    print('='*70)
    
    # Extract text
    ocr = OcrAgent()
    ocr_output = ocr.extract_text(test_file)
    
    if isinstance(ocr_output, dict):
        text = ocr_output.get('text', '')
    else:
        text = ocr_output
    
    print(f'[OCR] Extracted {len(text)} characters')
    print()
    
    # Extract fields
    extractor = RobustFieldExtractor()
    extracted = extractor.extract_all_fields(text, test_file)
    
    print()
    print('='*70)
    print('[FINAL RESULT]')
    print('='*70)
    event_name = extracted.get('event_name')
    date_val = extracted.get('date')
    dept = extracted.get('department')
    organizer = extracted.get('organizer')
    venue = extracted.get('venue')
    confidence = extracted.get('confidence')
    
    print(f'Event Name: {event_name}')
    print(f'Date: {date_val}')
    print(f'Department: {dept}')
    print(f'Organizer: {organizer}')
    print(f'Venue: {venue}')
    print(f'Confidence: {confidence}')
else:
    print(f'File not found: {test_file}')
