"""
backend/agents/orchestrator_agent.py

Orchestrator coordinates the complete document processing pipeline.
Pipeline: OCR → NER (with categorization) → Abstract Generation → Database Persistence
"""

from annotated_types import doc
from agents.ocr_agent import OcrAgent
from agents.ner_agent import NerAgent
from agents.abstract_generator_agent import AbstractGeneratorAgent
from models import db, Document, Event, ExtractedEntity
import os
from datetime import datetime, date
from config import Config


DEFAULT_DOC_TYPE = "Report"

def _safe_default_extraction(doc):
    """Return a minimal safe extraction dict used when ML fails."""
    return {
        "doc_type": DEFAULT_DOC_TYPE,
        "event_name": "Untitled Event",
        "date": None,
        "department": doc.department or "General",
        "venue": "",
        "organizer": "",
        "abstract": "",
        "category": "General / Department Activity",
        "confidence": 0.1,
        "entities": []
    }

class OrchestratorAgent:
    def __init__(self):
        try:
            self.ocr_agent = OcrAgent()
            print("[Orchestrator] ✅ OCR Agent initialized")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ OCR init failed: {e}")
            self.ocr_agent = None
        
        try:
            self.ner_agent = NerAgent()
            print("[Orchestrator] ✅ Enhanced NER Agent initialized (with categorization)")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ NER Agent init failed: {e}")
            self.ner_agent = None
        
        # Initialize Abstract Generator only if enabled in config
        if Config.USE_ABSTRACT_AGENT:
            try:
                self.abstract_generator = AbstractGeneratorAgent(method='gemini')
                print("[Orchestrator] ✅ Abstract Generator initialized (Gemini API)")
            except Exception as e:
                print(f"[Orchestrator] ⚠️ Abstract Generator init failed: {e}")
                self.abstract_generator = None
        else:
            self.abstract_generator = None
            print("[Orchestrator] ℹ️ Abstract Generator DISABLED (USE_ABSTRACT_AGENT=false)")

        print("[Orchestrator] ✅ Ready to process documents")

    def process_document(self, doc_id, file_path=None):
        """
        Complete document processing pipeline:
        1. OCR - Extract text from PDF/image
        2. NER + Categorization - Extract all structured fields
        3. Abstract Generation - Generate/enhance abstract for reports
        4. Database Persistence - Save document, event, and entities
        
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
            # STEP 2: NER + Categorization
            # ========================================
            print(f"\n{'─' * 70}")
            print("[Orchestrator] 🔍 STEP 2: Running Enhanced NER Agent...")
            print(f"{'─' * 70}")

            # Enhanced NER does both categorization and entity extraction
            if self.ner_agent:
                try:
                    ner_result = self.ner_agent.predict(raw_text) or {}
                except Exception as e:
                    # If ML prediction fails, fall back safely
                    print(f"[Orchestrator] ⚠️ NerAgent.predict failed: {e}")
                    import traceback;
                    traceback.print_exc()
                    ner_result = _safe_default_extraction(doc)
            else:
                ner_result = _safe_default_extraction(doc)

            # Defensive defaults
            doc_type = ner_result.get("doc_type") or DEFAULT_DOC_TYPE
            category = ner_result.get("category") or "General / Department Activity"
            try:
                confidence = float(ner_result.get("confidence", 0.5))
            except Exception:
                confidence = 0.5

            event_name = ner_result.get("event_name") or "Untitled Event"
            event_date_str = ner_result.get("date")
            venue = ner_result.get("venue") or "Venue not specified"
            organizer = ner_result.get("organizer") or "Organizer not specified"
            department = ner_result.get("department")
            if not department or department == "General":
                # Use the uploader's department as fallback
                department = doc.department or "General"
                print(f"[Orchestrator] Using uploader's department: {department}")
            abstract = ner_result.get("abstract") or ""

            # ========================================
            # STEP 3: Abstract Generation (Reports & Certificates)
            # ========================================
            print(f"\n{'─'*70}")
            print(f"[Orchestrator] 📝 STEP 3: Abstract Generation for {doc_type}...")
            print(f"{'─'*70}")
            
            # Generate abstracts for both Reports and Certificates since both contain event details
            # Note: Abstract generation can be disabled via USE_ABSTRACT_AGENT config flag
            if self.abstract_generator and (not abstract or len(abstract.strip()) < 100):
                try:
                    generated_abstract = self.abstract_generator.generate(raw_text, max_length=500)
                    if generated_abstract and len(generated_abstract) > len(abstract):
                        abstract = generated_abstract
                        print(f"[Orchestrator] ✅ Abstract generated ({len(abstract)} chars)")
                    else:
                        print(f"[Orchestrator] ℹ️ Using NER-extracted abstract")
                except Exception as e:
                    print(f"[Orchestrator] ⚠️ Abstract generation failed: {e}")
                    # Keep existing abstract even if generation fails
            else:
                if not self.abstract_generator:
                    print(f"[Orchestrator] ℹ️ Abstract Generator disabled (USE_ABSTRACT_AGENT=false)")
                elif abstract and len(abstract.strip()) >= 100:
                    print(f"[Orchestrator] ℹ️ Using existing abstract from NER ({len(abstract)} chars)")
                else:
                    print(f"[Orchestrator] ⚠️ No abstract available")

            # ========================================
            # STEP 4: Date Normalization
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 📅 STEP 4: Normalizing Date...")
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
            # STEP 5: Save Document Record
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 💾 STEP 5: Saving Document to Database...")
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
            # STEP 6: Create Event Record
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 🎉 STEP 6: Creating Event Record...")
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
            # STEP 7: Save Extracted Entities
            # ========================================
            print(f"\n{'─'*70}")
            print("[Orchestrator] 🏷️  STEP 7: Saving Extracted Entities...")
            print(f"{'─'*70}")
            
            # Build entities dict based on doc type
            entities_to_save = {
                "event_name": event_name,
                "date": str(event_date_obj),
                "department": department,
                "venue": venue,
                "organizer": organizer,
                "category": category,
                "doc_type": doc_type
            }
            
            # Add type-specific entities
            if doc_type != "Certificate":
                if abstract:
                    entities_to_save["abstract"] = abstract

            saved_count = 0
            for entity_type, entity_value in entities_to_save.items():
                if entity_value and str(entity_value).strip():
                    entity = ExtractedEntity(
                        document_id=doc.id,
                        entity_type=entity_type,
                        entity_value=str(entity_value),
                        confidence=float(confidence)
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
            print(f"Confidence:   {confidence:.2f}")
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