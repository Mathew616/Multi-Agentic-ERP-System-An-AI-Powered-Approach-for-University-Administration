#!/usr/bin/env python
"""Check database contents"""

import os
import sys

# Ensure proper path
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
    print("[DATABASE CHECK]")
    print("="*70)
    
    # Check events
    events = Event.query.all()
    print(f"\nTotal Events: {len(events)}")
    for i, e in enumerate(events[-5:], 1):
        print(f"\n{i}. Event ID: {e.id}")
        print(f"   Name: {e.name}")
        print(f"   Department: {e.department}")
        print(f"   Date: {e.date}")
        print(f"   Category: {e.category}")
        print(f"   Validated: {e.validated}")
        print(f"   Document ID: {e.document_id}")
        if e.document_id:
            doc = Document.query.get(e.document_id)
            if doc:
                print(f"   Document: {doc.filename}")
    
    # Check extracted entities
    print(f"\n\nTotal Entities: {ExtractedEntity.query.count()}")
    
    # Find entities for the last 5 documents
    docs = Document.query.order_by(Document.id.desc()).limit(5).all()
    for doc in docs:
        print(f"\n📄 Document: {doc.filename} (ID: {doc.id})")
        entities = ExtractedEntity.query.filter_by(document_id=doc.id).all()
        for ent in entities:
            val_display = ent.entity_value[:50] + "..." if len(str(ent.entity_value)) > 50 else ent.entity_value
            print(f"   - {ent.entity_type}: {val_display}")
