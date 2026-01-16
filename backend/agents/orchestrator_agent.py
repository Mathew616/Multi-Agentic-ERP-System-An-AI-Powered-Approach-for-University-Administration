"""
backend/agents/orchestrator_agent.py

Orchestrator coordinates the complete document processing pipeline.
Pipeline: OCR → Field Extraction → Database Persistence
"""

from agents.ocr_agent import OcrAgent
from agents.field_extractor import RobustFieldExtractor
from models import db, Document, Event, ExtractedEntity
import os
from datetime import datetime, date
from config import Config


class OrchestratorAgent:
    def __init__(self):
        try:
            self.ocr_agent = OcrAgent()
            print("[Orchestrator] ✅ OCR Agent initialized")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ OCR init failed: {e}")
            self.ocr_agent = None
        
        try:
            self.field_extractor = RobustFieldExtractor()
            print("[Orchestrator] ✅ Field Extractor initialized")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ Field Extractor init failed: {e}")
            self.field_extractor = None
        
        print("[Orchestrator] ✅ Ready to process documents")

    def process_document(self, doc_id, file_path=None):
        """
        Complete document processing pipeline:
        1. OCR - Extract text from PDF/image
        2. Field Extraction - Extract all structured fields
        3. Database Persistence - Save document, event, and entities
        
        Args:
            doc_id (int): Document ID from database
            file_path (str, optional): Path to uploaded file
        """
        print(f"\n{'='*70}")
        print(f"[Orchestrator] 🚀 STARTING PROCESSING - Document ID: {doc_id}")
        print(f"{'='*70}\n")

        # Retrieve document from database
        doc = Document.query.get(doc_id)
        if not doc:
            print(f"[Orchestrator] ❌ ERROR: Document ID {doc_id} not found in database")
            return

        # Update status to processing
        doc.status = "processing"
        db.session.commit()
        print(f"[Orchestrator] 📝 Document status set to 'processing'")

        # Resolve file path
        upload_folder = getattr(Config, "UPLOAD_FOLDER", "static/uploads")
        file_path = file_path or os.path.join(upload_folder, doc.filename)
        
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            print(f"[Orchestrator] ❌ ERROR: {error_msg}")
            doc.status = "failed"
            doc.last_error = error_msg
            db.session.commit()
            return

        print(f"[Orchestrator] 📂 File path: {file_path}")

        try:
            # ========================================
            # STEP 1: OCR - Extract Raw Text
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 📄 STEP 1: Running OCR...")
            print(f"{'─'*70}")
            
            ocr = self.ocr_agent or OcrAgent()
            ocr_output = ocr.extract_text(file_path)

            # Handle both dict and string output
            if isinstance(ocr_output, dict):
                raw_text = ocr_output.get("text", "")
                ocr_title = ocr_output.get("title", "")
                ocr_source = ocr_output.get("source", "unknown")
            else:
                raw_text = ocr_output
                ocr_title = ""
                ocr_source = "legacy"

            if not raw_text or len(raw_text.strip()) < 50:
                raise ValueError(f"OCR extracted insufficient text (only {len(raw_text)} chars)")

            print(f"[Orchestrator] ✅ OCR Complete:")
            print(f"   - Extracted: {len(raw_text)} characters")
            print(f"   - OCR Title: {ocr_title or 'None detected'}")
            print(f"   - Source: {ocr_source}")

            # ========================================
            # STEP 2: Field Extraction
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 🔍 STEP 2: Running Field Extraction...")
            print(f"{'─'*70}")
            
            extractor = self.field_extractor or RobustFieldExtractor()
            
            # Single unified extraction call
            extracted = extractor.extract_all_fields(
                text=raw_text,
                filename=doc.filename
            )

            # Unpack all extracted fields
            doc_type = extracted.get("doc_type", "Report")
            event_name = extracted.get("event_name", "Untitled Event")
            event_date_str = extracted.get("date")
            department = extracted.get("department", "General")
            venue = extracted.get("venue", "Venue not specified")
            organizer = extracted.get("organizer", "Organizer not specified")
            abstract = extracted.get("abstract", "No abstract found")
            category = extracted.get("category", "General Event")
            confidence = extracted.get("confidence", 0.5)

            print(f"[Orchestrator] ✅ Extraction Complete:")
            print(f"   📄 Document Type: {doc_type}")
            print(f"   🎯 Event Name: {event_name}")
            print(f"   📅 Date: {event_date_str}")
            print(f"   🏢 Department: {department}")
            print(f"   📍 Venue: {venue}")
            print(f"   👤 Organizer: {organizer}")
            print(f"   📂 Category: {category}")
            print(f"   ✨ Confidence: {confidence}")

            # ========================================
            # STEP 3: Date Normalization
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 📅 STEP 3: Normalizing Date...")
            print(f"{'─'*70}")
            
            if isinstance(event_date_str, str):
                try:
                    event_date_obj = datetime.fromisoformat(event_date_str).date()
                    print(f"[Orchestrator] ✅ Date parsed: {event_date_obj}")
                except Exception as e:
                    print(f"[Orchestrator] ⚠️ Date parse failed ({e}), using today")
                    event_date_obj = date.today()
            elif isinstance(event_date_str, date):
                event_date_obj = event_date_str
                print(f"[Orchestrator] ✅ Date already in date format: {event_date_obj}")
            else:
                event_date_obj = date.today()
                print(f"[Orchestrator] ⚠️ Invalid date format, using today: {event_date_obj}")

            # ========================================
            # STEP 4: Save Document Record
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 💾 STEP 4: Saving Document to Database...")
            print(f"{'─'*70}")
            
            doc.raw_text = raw_text
            doc.department = department
            doc.category = category
            doc.status = "needs_review"
            doc.last_error = None
            db.session.add(doc)
            db.session.flush()
            
            print(f"[Orchestrator] ✅ Document saved (ID: {doc.id})")

            # ========================================
            # STEP 5: Create Event Record
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 🎉 STEP 5: Creating Event Record...")
            print(f"{'─'*70}")
            
            event = Event(
                document_id=doc.id,
                name=event_name.strip(),
                date=event_date_obj,
                department=department,
                category=category,
                validated=False,
                type=doc_type,
                status="pending"
            )
            db.session.add(event)
            db.session.flush()
            
            print(f"[Orchestrator] ✅ Event created:")
            print(f"   - ID: {event.id}")
            print(f"   - Name: {event.name}")
            print(f"   - Type: {event.type}")
            print(f"   - Status: {event.status}")

            # ========================================
            # STEP 6: Save Extracted Entities
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 🏷️  STEP 6: Saving Extracted Entities...")
            print(f"{'─'*70}")
            
            entities_to_save = {
                "event_name": event_name,
                "date": str(event_date_obj),
                "department": department,
                "venue": venue,
                "organizer": organizer,
                "abstract": abstract,
                "category": category,
                "doc_type": doc_type
            }

            saved_count = 0
            for entity_type, entity_value in entities_to_save.items():
                if entity_value and str(entity_value).strip():
                    entity = ExtractedEntity(
                        document_id=doc.id,
                        entity_type=entity_type,
                        entity_value=str(entity_value),
                        confidence=confidence
                    )
                    db.session.add(entity)
                    saved_count += 1

            # Commit all changes to database
            db.session.commit()
            
            print(f"[Orchestrator] ✅ Saved {saved_count} entities:")
            for key in entities_to_save.keys():
                val = entities_to_save[key]
                if val and str(val).strip():
                    display = str(val)[:60] + "..." if len(str(val)) > 60 else str(val)
                    print(f"   - {key}: {display}")

            # ========================================
            # FINAL SUCCESS MESSAGE
            # ========================================
            print(f"\n{'='*70}")
            print(f"[Orchestrator] 🎉 SUCCESS - Document Processed")
            print(f"{'='*70}")
            print(f"Document ID:  {doc.id}")
            print(f"Event ID:     {event.id}")
            print(f"Type:         {doc_type}")
            print(f"Event:        {event_name}")
            print(f"Department:   {department}")
            print(f"Category:     {category}")
            print(f"Date:         {event_date_obj}")
            print(f"Confidence:   {confidence}")
            print(f"Status:       needs_review")
            print(f"{'='*70}\n")

        except Exception as e:
            # ========================================
            # ERROR HANDLING
            # ========================================
            error_msg = str(e)
            print(f"\n{'='*70}")
            print(f"[Orchestrator] ❌ PROCESSING FAILED")
            print(f"{'='*70}")
            print(f"Document ID: {doc_id}")
            print(f"Error: {error_msg}")
            print(f"{'='*70}\n")
            
            doc.status = "failed"
            doc.last_error = error_msg
            db.session.commit()
            
            # Re-raise for debugging if needed
            import traceback
            traceback.print_exc()