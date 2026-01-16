#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick test script to validate improved extraction on actual PDF
"""

from backend.agents.field_extractor import RobustFieldExtractor
import fitz  # PyMuPDF (simpler text extraction)
import os

if __name__ == "__main__":
    print("=" * 70)
    print("Testing Improved Field Extraction on Actual PDF")
    print("=" * 70 + "\n")
    
    # Path to the actual PDF document
    pdf_path = r"c:\Users\amans\Downloads\Documents\FOSS_REPORT_Template_1V.pdf"
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print("ERROR: File not found at", pdf_path)
        print("Please check the path and try again.")
        exit(1)
    
    print("Processing:", pdf_path)
    print("File size:", os.path.getsize(pdf_path) / 1024, "KB\n")
    
    # ========== STEP 1: Extract text from PDF using PyMuPDF ==========
    print("=" * 70)
    print("STEP 1: Text Extraction from PDF")
    print("=" * 70)
    
    try:
        pdf = fitz.open(pdf_path)
        raw_text = ""
        
        # Extract text from all pages
        for page_num, page in enumerate(pdf):
            text = page.get_text("text")
            raw_text += text + "\n"
        
        pdf.close()
        
        print("Extracted from", page_num + 1, "pages,", len(raw_text), "characters")
        print("\nFirst 400 chars:\n", raw_text[:400], "\n...")
        
    except Exception as e:
        print("ERROR - Text extraction failed:", e)
        exit(1)
    
    # ========== STEP 2: Extract fields using Field Extractor ==========
    print("\n" + "=" * 70)
    print("STEP 2: Field Extraction")
    print("=" * 70 + "\n")
    
    extractor = RobustFieldExtractor()
    result = extractor.extract_all_fields(raw_text)
    
    print("\n" + "=" * 70)
    print("EXTRACTION RESULTS:")
    print("=" * 70)
    for key, value in result.items():
        if isinstance(value, str) and len(value) > 80:
            print(f"{key:20s}: {value[:80]}...")
        else:
            print(f"{key:20s}: {value}")
    
    print("\n" + "=" * 70)
    print("DETAILED ANALYSIS:")
    print("=" * 70)
    print("Event Name:    ", result['event_name'])
    print("Date:          ", result['date'])
    print("Department:    ", result['department'])
    print("Venue:         ", result['venue'])
    print("Organizer:     ", result['organizer'])
    print("Category:      ", result['category'])
    print("Doc Type:      ", result['doc_type'])
    print("Confidence:    ", result['confidence'])
    
    print("\n" + "=" * 70)
