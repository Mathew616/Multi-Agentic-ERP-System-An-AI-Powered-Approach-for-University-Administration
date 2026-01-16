#!/usr/bin/env python
"""Comprehensive test of the fix in actual production scenario"""

import os
import sys

os.chdir(r'E:\Projects\MAJOR PROJECT\backend')
sys.path.insert(0, r'E:\Projects\MAJOR PROJECT\backend')

from flask import Flask
from flask_migrate import Migrate
from config import Config
from models import db, Event, Document, ExtractedEntity
from agents.orchestrator_agent import OrchestratorAgent

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    print("\n" + "="*70)
    print("[COMPREHENSIVE PRODUCTION TEST]")
    print("="*70)
    
    # Step 1: Copy fresh PDF to uploads folder
    print("\n[STEP 1] Setting up test PDF...")
    src_pdf = r'E:\Projects\MAJOR PROJECT\backend\static\uploads\FOSS_REPORT_Template_1V.pdf'
    if not os.path.exists(src_pdf):
        print(f"Err: PDF not found: {src_pdf}")
        sys.exit(1)
    print(f"OK: PDF found")
    
    # Step 2: Create a fresh document in database
    print("\n[STEP 2] Creating fresh document record...")
    doc = Document(
        filename='FOSS_REPORT_Template_1V.pdf',
        uploaded_by='testuser',
        status='processing',
        department='AIML'
    )
    db.session.add(doc)
    db.session.commit()
    print(f"OK: Document created (ID: {doc.id})")
    
    # Step 3: Process with orchestrator
    print("\n[STEP 3] Processing with Orchestrator...")
    orchestrator = OrchestratorAgent()
    orchestrator.process_document(doc.id, file_path=src_pdf)
    
    # Step 4: Refresh and check
    print("\n[STEP 4] Validating extracted data...")
    db.session.refresh(doc)
    
    # Get event
    event = Event.query.filter_by(document_id=doc.id).first()
    if not event:
        print("Err: No event created!")
        sys.exit(1)
    
    print(f"\nEvent Details:")
    print(f"  Name: {event.name}")
    print(f"  Date: {event.date}")
    print(f"  Department: {event.department}")
    print(f"  Category: {event.category}")
    
    # Get entities
    entities = ExtractedEntity.query.filter_by(document_id=doc.id).all()
    print(f"\nExtracted Entities ({len(entities)} total):")
    entity_dict = {}
    for ent in entities:
        entity_dict[ent.entity_type] = ent.entity_value
        val = ent.entity_value[:50] + "..." if len(str(ent.entity_value)) > 50 else ent.entity_value
        print(f"  {ent.entity_type}: {val}")
    
    # Step 5: Validate
    print("\n" + "="*70)
    print("[VALIDATION RESULTS]")
    print("="*70)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Event name NOT "Mr Biju K Nair"
    if event.name == "Mr Biju K Nair":
        print("FAIL - Event name still 'Mr Biju K Nair'")
        tests_failed += 1
    else:
        print("PASS - Event name is NOT 'Mr Biju K Nair'")
        tests_passed += 1
    
    # Test 2: Event name is the correct FOSS meetup
    if "FOSS" in event.name and "meetup" in event.name.lower():
        print("PASS - Event name contains 'FOSS' and 'meetup'")
        tests_passed += 1
    else:
        print(f"FAIL - Event name doesn't match: {event.name}")
        tests_failed += 1
    
    # Test 3: Date is correct
    if str(event.date) == "2024-03-30":
        print("PASS - Date is 2024-03-30")
        tests_passed += 1
    else:
        print(f"FAIL - Date is {event.date}")
        tests_failed += 1
    
    # Test 4: Department is AIML
    if event.department == "AIML":
        print("PASS - Department is AIML")
        tests_passed += 1
    else:
        print(f"FAIL - Department is {event.department}")
        tests_failed += 1
    
    # Test 5: Organizer correct
    organizer = entity_dict.get('organizer', '')
    if "FOSS" in organizer:
        print("PASS - Organizer contains 'FOSS'")
        tests_passed += 1
    else:
        print(f"FAIL - Organizer not correct: {organizer}")
        tests_failed += 1
    
    # Test 6: Venue correct
    venue = entity_dict.get('venue', '')
    if "Navi" in venue:
        print("PASS - Venue is 'Navi Technologies'")
        tests_passed += 1
    else:
        print(f"FAIL - Venue not correct: {venue}")
        tests_failed += 1
    
    # Test 7: Confidence high
    conf_ent = ExtractedEntity.query.filter_by(document_id=doc.id, entity_type='event_name').first()
    if conf_ent and conf_ent.confidence >= 0.8:
        print(f"PASS - Confidence is high ({conf_ent.confidence})")
        tests_passed += 1
    else:
        conf = conf_ent.confidence if conf_ent else 0
        print(f"FAIL - Confidence too low ({conf})")
        tests_failed += 1
    
    print("\n" + "="*70)
    print(f"RESULT: {tests_passed} PASSED, {tests_failed} FAILED")
    print("="*70 + "\n")
    
    if tests_failed == 0:
        print("SUCCESS - All tests passed!\n")
