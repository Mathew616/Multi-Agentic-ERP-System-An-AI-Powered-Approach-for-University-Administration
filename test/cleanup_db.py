#!/usr/bin/env python
"""Clear old events from database so reprocessing shows correct data"""

import os
import sys

os.chdir(r'E:\Projects\MAJOR PROJECT\backend')
sys.path.insert(0, r'E:\Projects\MAJOR PROJECT\backend')

from flask import Flask
from flask_migrate import Migrate
from config import Config
from models import db, Event, Document, ExtractedEntity

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    print("="*70)
    print("[DATABASE CLEANUP]")
    print("="*70)
    
    # Find the FOSS_REPORT document
    doc = Document.query.filter_by(filename='FOSS_REPORT_Template_1V.pdf').first()
    
    if doc:
        print(f"\nFound document: {doc.filename} (ID: {doc.id})")
        
        # Delete related events
        events = Event.query.filter_by(document_id=doc.id).all()
        for event in events:
            print(f"  Deleting Event: {event.name} (ID: {event.id})")
            db.session.delete(event)
        
        # Delete related entities
        entities = ExtractedEntity.query.filter_by(document_id=doc.id).all()
        for entity in entities:
            print(f"  Deleting Entity: {entity.entity_type}")
            db.session.delete(entity)
        
        db.session.commit()
        print(f"\n✓ Cleaned up document and related data")
    else:
        print("\n❌ Document not found")
    
    # Show remaining events
    all_events = Event.query.all()
    print(f"\nRemaining events in database: {len(all_events)}")
