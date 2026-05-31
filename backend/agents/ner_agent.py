# ner_agent.py
"""
Enhanced NER Agent with Regex Fallback Extractors

This agent uses a two-tier approach:
1. Primary: Transformer-based NER model for entity extraction
2. Fallback: Regex patterns when NER model misses fields

Handles all entity types including:
- EVENT_NAME, DATE, VENUE, ORGANIZER, DEPARTMENT (core fields)
- CATEGORY, DOC_TYPE (document classification)

Note: ABSTRACT is handled separately, not by NER.
"""

from typing import List, Dict, Any
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    pipeline
)

# Import OCR preprocessor
sys.path.append(str(Path(__file__).parent.parent))
from ocr_preprocessor import OCRPreprocessor

# -------------------------
# Constants / Labels
# -------------------------
NER_MODEL_NAME = os.environ.get('NER_BASE_MODEL', 'bert-base-uncased')
NER_MODEL_DIR = os.environ.get('NER_MODEL_DIR', 'backend/ml_models/ner_model')

# Default doc type (guaranteed fallback)
DEFAULT_DOC_TYPE = 'Report'

# NER Labels (ABSTRACT removed - handled separately)
NER_LABELS = [
    'O',
    'B-EVENT_NAME', 'I-EVENT_NAME',
    'B-DATE', 'I-DATE',
    'B-VENUE', 'I-VENUE',
    'B-ORGANIZER', 'I-ORGANIZER',
    'B-DEPARTMENT', 'I-DEPARTMENT',
    'B-CATEGORY', 'I-CATEGORY',
    'B-DOC_TYPE', 'I-DOC_TYPE'
]


@dataclass
class NerPrediction:
    entity_type: str
    text: str
    start: int
    end: int
    score: float


class NerAgent:
    def __init__(
        self,
        ner_model_dir: str = NER_MODEL_DIR,
        ner_base_model: str = NER_MODEL_NAME,
        device: int = None,
        use_model: bool = None
    ):
        """Initialize NER Agent
        
        Args:
            use_model: If False, skip loading the BERT model entirely and
                       rely on regex fallback extractors only.
                       Reads USE_NER_MODEL env var / Config when None.
        """
        # Decide whether to load the transformer model
        if use_model is None:
            from config import Config
            use_model = Config.USE_NER_MODEL
        self.use_model = use_model

        # Initialize OCR preprocessor for text cleaning
        self.ocr_preprocessor = OCRPreprocessor()

        if not self.use_model:
            self.ner_pipeline = None
            print("[NerAgent] ⚡ Fallback-only mode (USE_NER_MODEL=false) — BERT model NOT loaded")
            return

        # Device selection
        if device is None:
            self.device = 0 if torch.cuda.is_available() else -1
        else:
            self.device = device

        print(f"[NerAgent] Initializing on device: {'GPU' if self.device >= 0 else 'CPU'}")

        # Load NER Model
        ner_path = ner_model_dir if os.path.exists(ner_model_dir) else ner_base_model
        print(f"[NerAgent] Loading NER model from: {ner_path}")

        self.ner_tokenizer = AutoTokenizer.from_pretrained(ner_path)
        self.ner_model = AutoModelForTokenClassification.from_pretrained(ner_path)
        self.ner_pipeline = pipeline(
            "token-classification",
            model=self.ner_model,
            tokenizer=self.ner_tokenizer,
            aggregation_strategy='simple',
            device=self.device
        )

        print("[NerAgent] ✅ NER model loaded successfully")

    # -------------------------
    # Entity extraction
    # -------------------------
    def predict_entities(self, text: str) -> List[NerPrediction]:
        """Extract entities using NER model, merging adjacent fragments."""
        if not text or len(text.strip()) < 2:
            return []

        raw = self.ner_pipeline(text)

        # Build initial predictions
        initial: List[NerPrediction] = []
        for p in raw:
            label = p.get('entity_group') or p.get('entity')
            score = float(p.get('score', 0.0))
            start = int(p.get('start', 0))
            end = int(p.get('end', 0))
            txt = text[max(0, start):min(len(text), end)]
            initial.append(NerPrediction(
                entity_type=label, text=txt,
                start=start, end=end, score=score
            ))

        # ── Merge adjacent / near-adjacent spans of the same entity type ──
        # The HF pipeline with aggregation_strategy='simple' can still
        # fragment a single real-world entity into multiple B- spans when
        # sub-word tokens sit on boundaries.  We stitch them back together
        # by walking left-to-right per entity type and merging any two
        # spans whose gap (in characters) is ≤ MAX_GAP.
        MAX_GAP = 15  # chars – covers spaces, punctuation, newlines between fragments

        # Group by entity type, preserving order
        from collections import defaultdict
        groups: Dict[str, List[NerPrediction]] = defaultdict(list)
        for pred in initial:
            groups[pred.entity_type].append(pred)

        merged: List[NerPrediction] = []
        for etype, spans in groups.items():
            # Sort by start offset
            spans.sort(key=lambda s: s.start)
            cluster = spans[0]
            for nxt in spans[1:]:
                gap = nxt.start - cluster.end
                if 0 <= gap <= MAX_GAP:
                    # Merge: extend the cluster to cover both spans using
                    # the original text so we don't lose characters in the gap
                    new_start = cluster.start
                    new_end = max(cluster.end, nxt.end)
                    new_text = text[new_start:new_end]
                    # Weighted average score by span length
                    len1 = cluster.end - cluster.start
                    len2 = nxt.end - nxt.start
                    new_score = (cluster.score * len1 + nxt.score * len2) / (len1 + len2) if (len1 + len2) else cluster.score
                    cluster = NerPrediction(
                        entity_type=etype, text=new_text,
                        start=new_start, end=new_end, score=new_score
                    )
                else:
                    merged.append(cluster)
                    cluster = nxt
            merged.append(cluster)

        # Sort final list by start offset for consistent ordering
        merged.sort(key=lambda s: s.start)
        return merged

    # -------------------------
    # Department Normalization
    # -------------------------
    def _normalize_department(self, dept_text: str) -> str:
        """
        Normalize department text to match exact dropdown values.
        
        Valid departments (matching frontend/database):
        - AIML
        - CSE(Core)
        - CSE-DS
        - CSE-CY
        - ISE
        - ECE
        - AERO
        """
        if not dept_text:
            return ''
        
        dept_upper = dept_text.upper().strip()
        dept_clean = re.sub(r'\s+', ' ', dept_upper)
        
        # Remove common prefixes
        dept_clean = re.sub(r'^DEPARTMENT\s+OF\s+', '', dept_clean)
        dept_clean = re.sub(r'^DEPT\.?\s+OF\s+', '', dept_clean)
        
        # Exact mapping to valid dropdown values
        EXACT_DEPARTMENTS = {
            # AIML variants
            'AIML': 'AIML',
            'AI & ML': 'AIML',
            'AI&ML': 'AIML',
            'AI ML': 'AIML',
            'ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING': 'AIML',
            'ARTIFICIAL INTELLIGENCE & MACHINE LEARNING': 'AIML',
            'COMPUTER SCIENCE AND ENGINEERING (ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING)': 'AIML',
            'COMPUTER SCIENCE AND ENGINEERING (AI & ML)': 'AIML',
            'COMPUTER SCIENCE AND ENGINEERING (AIML)': 'AIML',
            'CSE(AI & ML)': 'AIML',
            'CSE(AIML)': 'AIML',
            'CSE (AI&ML)': 'AIML',
            'CSE ( AIML )': 'AIML',
            'CSE-AIML': 'AIML',
            
            # Aerospace variants
            'AEROSPACE': 'AERO',
            'AERO': 'AERO',
            'AERONAUTICS': 'AERO',
            'CSE(AEROSPACE)': 'AERO',
            'CSE (AEROSPACE)': 'AERO',
            'COMPUTER SCIENCE AND ENGINEERING (AEROSPACE)': 'AERO',
            'COMPUTER SCIENCE AND ENGINEERING ( AEROSPACE )': 'AERO',
            
            # Cybersecurity variants
            'CYBERSECURITY': 'CSE-CY',
            'CYBER SECURITY': 'CSE-CY',
            'CYBER': 'CSE-CY',
            'CSE-CY': 'CSE-CY',
            'CSE(CYBERSECURITY)': 'CSE-CY',
            'CSE (CYBERSECURITY)': 'CSE-CY',
            'COMPUTER SCIENCE AND ENGINEERING (CYBERSECURITY)': 'CSE-CY',
            'COMPUTER SCIENCE AND ENGINEERING ( CYBERSECURITY )': 'CSE-CY',
            'CYBER SECURITY': 'CSE-CY',
            
            # Data Science variants
            'DATA SCIENCE': 'CSE-DS',
            'DS': 'CSE-DS',
            'CSE-DS': 'CSE-DS',
            'CSE(DATA SCIENCE)': 'CSE-DS',
            'CSE (DATA SCIENCE)': 'CSE-DS',
            'COMPUTER SCIENCE AND ENGINEERING (DATA SCIENCE)': 'CSE-DS',
            'COMPUTER SCIENCE AND ENGINEERING ( DATA SCIENCE )': 'CSE-DS',
            
            # CSE Core variants
            'CSE': 'CSE(Core)',
            'CSE CORE': 'CSE(Core)',
            'CSE-CORE': 'CSE(Core)',
            'CSE (CORE)': 'CSE(Core)',
            'CSE(CORE)': 'CSE(Core)',
            'COMPUTER SCIENCE': 'CSE(Core)',
            'COMPUTER SCIENCE AND ENGINEERING': 'CSE(Core)',
            'COMPUTER SCIENCE AND ENGINEERING (CORE)': 'CSE(Core)',
            'COMPUTER SCIENCE & ENGINEERING': 'CSE(Core)',
            'CSE - CORE': 'CSE(Core)',
            'COMPUTER SCIENCE AND ENGINEERING ( CSE - CORE )': 'CSE(Core)',
            
            # ISE variants
            'ISE': 'ISE',
            'INFORMATION SCIENCE': 'ISE',
            'INFORMATION SCIENCE AND ENGINEERING': 'ISE',
            'INFORMATION SCIENCE & ENGINEERING': 'ISE',
            
            # ECE variants
            'ECE': 'ECE',
            'ELECTRONICS': 'ECE',
            'ELECTRONICS AND COMMUNICATION': 'ECE',
            'ELECTRONICS AND COMMUNICATION ENGINEERING': 'ECE',
            'ELECTRONICS & COMMUNICATION ENGINEERING': 'ECE',
        }
        
        # Direct match
        if dept_clean in EXACT_DEPARTMENTS:
            return EXACT_DEPARTMENTS[dept_clean]
        
        # Fuzzy match - check if any key is contained in the text
        for key, value in EXACT_DEPARTMENTS.items():
            if key in dept_clean or dept_clean in key:
                return value
        
        # Keyword-based fallback
        if 'AIML' in dept_clean or 'AI' in dept_clean and 'ML' in dept_clean:
            return 'AIML'
        elif 'AEROSPACE' in dept_clean or 'AERO' in dept_clean:
            return 'AERO'
        elif 'CYBERSECURITY' in dept_clean or 'CYBER' in dept_clean:
            return 'CSE-CY'
        elif 'DATA' in dept_clean and 'SCIENCE' in dept_clean:
            return 'CSE-DS'
        elif 'ISE' in dept_clean or 'INFORMATION' in dept_clean:
            return 'ISE'
        elif 'ECE' in dept_clean or 'ELECTRONICS' in dept_clean:
            return 'ECE'
        elif 'CSE' in dept_clean or 'COMPUTER SCIENCE' in dept_clean:
            return 'CSE(Core)'
        
        # If nothing matched, return empty (orchestrator will use user's department)
        return ''
    def _extract_event_name_fallback(self, text: str) -> str:
        """Fallback regex extraction for event name with position-aware scoring"""
        
        # Extract first 1500 chars (main header section — generous for verbose cover pages)
        header_text = text[:1500] if len(text) > 1500 else text
        
        # High-priority patterns (only search header)
        # Note: Include BOTH ASCII quotes ("/') AND Unicode smart quotes (\u201c\u201d\u2018\u2019)
        _Q = r'["\'\'\u201c\u201d\u2018\u2019\u00ab\u00bb]'  # any quote character
        _NQ = r'[^"\'\u201c\u201d\u2018\u2019\u00ab\u00bb]'  # any non-quote character
        high_priority_patterns = [
            # Pattern 1: Quoted text after "On" (most reliable for FOSS reports)
            (rf'(?i)\bOn\s*{_Q}({_NQ}{{10,120}}){_Q}', 100),
            # Pattern 2: Text immediately after "On" keyword at doc start
            (r'(?i)(?:^|\n)\s*On\s*\n\s*([^\n]{10,120}?)(?=\s*\n\s*\d{1,2})', 95),
            # Pattern 3: Between quotes near top (any quote type)
            (rf'^{_NQ}{{0,300}}{_Q}({_NQ}{{10,120}}){_Q}', 90),
        ]
        
        # Try high-priority patterns in header first
        for pattern, priority in high_priority_patterns:
            match = re.search(pattern, header_text, re.MULTILINE)
            if match:
                name = match.group(1).strip()
                name = self._clean_event_name(name)
                if self._is_valid_event_name(name):
                    print(f"[NerAgent][FALLBACK] Event name (header, priority={priority}): '{name}'")
                    return name
        
        # Medium-priority patterns (search full text but score by position)
        medium_priority_patterns = [
            # Pattern 4: Report/Certificate ON + quoted text (flattened or multiline)
            rf'(?i)(?:REPORT|CERTIFICATE)\s+(?:ON|OF|FOR|on)\s*[:\-]?\s*{_Q}({_NQ}{{8,120}}){_Q}',
            # Pattern 4b: Report/Certificate ON + unquoted text until next field
            r'(?i)(?:REPORT|CERTIFICATE)\s+(?:ON|OF|FOR|on)\s*[:\-]?\s*([^\n]{8,150}?)(?=\s*(?:\n\s*\d{1,2}|\n\s*Date|\n\s*Venue|\n\n))',
            # Pattern 4c: titled "..." (common in certificate text)
            rf'(?i)\btitled\s+{_Q}({_NQ}{{8,120}}){_Q}',
            # Pattern 5: Title/Topic/Subject line
            r'(?i)(?:title|topic|subject|name of (?:the )?event)\s*[:\-]\s*([^\n]{10,150})',
            # Pattern 6: On + Capitalized (relaxed case)
            r'(?i)(?:^|\n)\s*On\s+([A-Z][^\n]{8,150}?)(?=\s*\n)',
            # Pattern 7: Event/Workshop at line start
            r'(?i)^[ \t]*(?:event|workshop|seminar|conference|training|competition)\s*(?:name)?[:\-]?\s*([A-Z][^\n]{10,120})',
        ]
        
        candidates = []
        for pattern in medium_priority_patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1).strip()
                position = match.start()
                
                # Calculate position score (prefer earlier positions)
                # Position 0-500: score 80, 500-1000: score 60, 1000+: score 40
                if position < 500:
                    pos_score = 80
                elif position < 1000:
                    pos_score = 60
                else:
                    pos_score = 40
                
                name = self._clean_event_name(name)
                if self._is_valid_event_name(name):
                    candidates.append((name, pos_score, position))
        
        # Sort by score (descending) then position (ascending)
        if candidates:
            candidates.sort(key=lambda x: (-x[1], x[2]))
            best_name = candidates[0][0]
            best_score = candidates[0][1]
            best_pos = candidates[0][2]
            print(f"[NerAgent][FALLBACK] Event name (position={best_pos}, score={best_score}): '{best_name}'")
            return best_name
        
        # Low-priority patterns (last resort, only first 2000 chars)
        low_priority_text = text[:2000] if len(text) > 2000 else text
        low_priority_patterns = [
            # Pattern 8: All caps title (first few lines)
            r'(?:^|\n)([A-Z][A-Z\s&\-]{8,100})(?=\n)',
            # Pattern 9: Organized event
            r'(?i)organized\s+(?:a|an)?\s*(?:event|workshop|seminar)\s+(?:on|about)?\s*["]?([A-Z][^\n"]{10,120})',
        ]
        
        for pattern in low_priority_patterns:
            match = re.search(pattern, low_priority_text, re.MULTILINE)
            if match:
                name = match.group(1).strip()
                name = self._clean_event_name(name)
                if self._is_valid_event_name(name):
                    print(f"[NerAgent][FALLBACK] Event name (low priority): '{name}'")
                    return name
        
        return ''
    
    def _clean_event_name(self, name: str) -> str:
        """Clean and normalize extracted event name"""
        # Normalize whitespace
        name = re.sub(r'\s+', ' ', name)
        
        # Remove articles at start
        name = re.sub(r'^(the|a|an)\s+', '', name, flags=re.IGNORECASE)
        
        # Remove trailing punctuation
        name = name.strip('.,;:!?')
        
        # Remove common suffixes that indicate incomplete extraction
        name = re.sub(r'\s+(Date|Venue|Organized|Department|Report|on|at|by).*$', '', name, flags=re.IGNORECASE)
        
        # Remove dates at end
        name = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}.*$', '', name)
        name = re.sub(r'\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}.*$', '', name, flags=re.IGNORECASE)
        
        # Remove time ranges (e.g., "1:20 PM - 2:05 PM")
        name = re.sub(r'\s+\d{1,2}:\d{2}\s*(?:AM|PM).*$', '', name, flags=re.IGNORECASE)
        
        # Clean up quotes if present (ASCII and Unicode smart quotes)
        name = name.strip('"\'\u201c\u201d\u2018\u2019\u00ab\u00bb')        
        return name.strip()
    
    def _is_valid_event_name(self, name: str) -> bool:
        """Validate if extracted text is a reasonable event name"""
        if not name:
            return False
        
        # Length check
        if len(name) < 8 or len(name) > 150:
            return False
        
        # Word count check (at least 2 words or 10+ chars for single word)
        words = name.split()
        if len(words) < 2 and len(name) < 10:
            return False
        
        # Check for noise patterns
        noise_patterns = [
            r'^(event|report|certificate|document|date|venue|organized|on|the|course)$',
            r'^\d{4}-\d{2}-\d{2}',  # ISO dates
            r'^page \d+',
            r'^\d+$',  # Just numbers
            r'^[A-Z]{1,3}$',  # Very short acronyms
            r'submitted\s+by',  # Document metadata
            r'under\s+the\s+supervision',
            r'^\s*by\s+',
        ]
        
        for pattern in noise_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return False
        
        # Reject if it's mostly numbers/punctuation
        alpha_chars = sum(c.isalpha() for c in name)
        if alpha_chars < len(name) * 0.5:
            return False
        
        return True

    def _extract_date_fallback(self, text: str) -> str:
        """Fallback regex extraction for dates"""
        patterns = [
            # DD/MM/YYYY or DD-MM-YYYY
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
            # DD.MM.YYYY (common in Indian certificates)
            r'\b(\d{1,2}\.\d{1,2}\.\d{4})\b',
            # 30th MARCH 2024, 1st January 2025
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
            # January 30, 2024
            r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',
            # 30 Mar 2024
            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
            # ISO format
            r'\b(\d{4}-\d{2}-\d{2})\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                normalized = self._normalize_date(date_str)
                if normalized:
                    return normalized
                return date_str
        return ''

    def _extract_venue_fallback(self, text: str) -> str:
        """Fallback regex extraction for venue"""
        candidates = []

        # Pattern group 1: Explicit "Location:" or "Venue:" labels (highest priority)
        label_patterns = [
            r'(?i)\b(?:venue|location)\s*[:\-]\s*([^\n.]{5,120})',
            r'(?i)\b(?:place|held at|conducted at|organized at)\s*[:\-]?\s*([^\n.]{5,120})',
        ]
        for pattern in label_patterns:
            match = re.search(pattern, text)
            if match:
                venue = match.group(1).strip()
                venue = re.sub(r'\s+', ' ', venue)
                # Truncate at next label keyword (e.g., "Organiser", "Date", "Time")
                venue = re.sub(r'\s*(?:Organis|Date|Time|Event|Speaker|Contact|Phone|Email|Submitted|Under).*$', '', venue, flags=re.IGNORECASE)
                venue = re.sub(r'[,\.;:]+$', '', venue).strip()
                if 5 <= len(venue) <= 120:
                    candidates.append((venue, 100))

        # Pattern group 2: Standalone room/hall/block references (word-boundary protected)
        room_patterns = [
            r'(?i)\b((?:Block|Auditorium|Seminar\s+Hall|Conference\s+Hall|Room)\s+[A-Z0-9][A-Z0-9\-]*(?:\s*,\s*[^\n,]{3,40})?)',
        ]
        for pattern in room_patterns:
            match = re.search(pattern, text)
            if match:
                venue = match.group(1).strip()
                venue = re.sub(r'\s+', ' ', venue)
                venue = re.sub(r'[,\.;:]+$', '', venue).strip()
                if 5 <= len(venue) <= 80:
                    candidates.append((venue, 60))

        if candidates:
            candidates.sort(key=lambda x: -x[1])
            return candidates[0][0]
        return ''

    def _extract_organizer_fallback(self, text: str) -> str:
        """Fallback regex extraction for organizer"""
        # Primary: explicit label patterns ("Organiser:", "Organized by", etc.)
        label_patterns = [
            r'(?i)(?:organiser|organizer|organized\s+by|conducted\s+by|coordinated\s+by)\s*[:\-]?\s*([^\n]{5,150})',
        ]

        organizers = []
        for pattern in label_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                org = match.group(1).strip()
                org = re.sub(r'\s+', ' ', org)
                # Truncate at sentence boundary or next field label
                org = re.sub(r'\s*(?:Event\s+list|Speaker|Date|Time|Venue|Location|Contact|Submitted|Under|Phone|Email).*$', '', org, flags=re.IGNORECASE)
                # Also truncate at first period followed by a space and capital letter (sentence end)
                period_match = re.search(r'\.\s+[A-Z]', org)
                if period_match:
                    org = org[:period_match.start()].strip()
                org = re.sub(r'[,\.;:]+$', '', org).strip()
                if 3 <= len(org) <= 100 and org not in organizers:
                    organizers.append(org)

        # Secondary: name-based patterns
        if not organizers:
            name_patterns = [
                r'(?i)(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'(?i)Team\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            ]
            for pattern in name_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    org = match.group(1).strip()
                    org = re.sub(r'\s+', ' ', org)
                    if 3 <= len(org) <= 100 and org not in organizers:
                        organizers.append(org)

        return ', '.join(organizers[:3]) if organizers else ''

    def _extract_department_fallback(self, text: str) -> str:
        """Fallback regex extraction for department"""
        patterns = [
            r'(?i)department\s+of\s+computer\s+science\s+and\s+engineering\s*\(\s*artificial\s+intelligence\s+and\s+machine\s+learning\s*\)',
            r'(?i)department\s+of\s+computer\s+science\s+and\s+engineering\s*\(\s*ai\s*&?\s*ml\s*\)',
            r'(?i)department\s+of\s+computer\s+science\s+and\s+engineering\s*\(\s*aerospace\s*\)',
            r'(?i)department\s+of\s+computer\s+science\s+and\s+engineering\s*\(\s*cybersecurity\s*\)',
            r'(?i)department\s+of\s+computer\s+science\s+and\s+engineering\s*\(\s*data\s+science\s*\)',
            r'(?i)department\s+of\s+(?:computer\s+science|cse)\s*\(?core\)?',
            r'(?i)department\s+of\s+(?:information\s+science|ise)',
            r'(?i)department\s+of\s+(?:electronics|ece)',
            r'(?i)CSE\s*\(\s*AI\s*&?\s*ML\s*\)',
            r'(?i)CSE\s*\(\s*AIML\s*\)',
            r'(?i)CSE\s*\(\s*AEROSPACE\s*\)',
            r'(?i)CSE\s*\(\s*CYBERSECURITY\s*\)',
            r'(?i)CSE\s*\(\s*DATA\s+SCIENCE\s*\)',
            r'(?i)CSE[\s\-]*CORE',
            r'(?i)\b(?:AIML|AI\s*&?\s*ML)\b',
            r'(?i)\bAERO(?:SPACE)?\b',
            r'(?i)\bCYBER(?:SECURITY)?\b',
            r'(?i)\b(?:DATA\s+SCIENCE|DS)\b',
            r'(?i)\bISE\b',
            r'(?i)\bECE\b',
        ]
        
        # Exact mapping to match your database/dropdown values
        DEPARTMENT_MAPPING = {
            'AIML': 'AIML',
            'AI & ML': 'AIML',
            'AI&ML': 'AIML',
            'ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING': 'AIML',
            'COMPUTER SCIENCE AND ENGINEERING (ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING)': 'AIML',
            'CSE(AI & ML)': 'AIML',
            'CSE(AIML)': 'AIML',
            'CSE (AI&ML)': 'AIML',
            
            'AEROSPACE': 'AERO',
            'AERO': 'AERO',
            'CSE(AEROSPACE)': 'AERO',
            'COMPUTER SCIENCE AND ENGINEERING (AEROSPACE)': 'AERO',
            
            'CYBERSECURITY': 'CSE-CY',
            'CYBER SECURITY': 'CSE-CY',
            'CYBER': 'CSE-CY',
            'CSE(CYBERSECURITY)': 'CSE-CY',
            'COMPUTER SCIENCE AND ENGINEERING (CYBERSECURITY)': 'CSE-CY',
            
            'DATA SCIENCE': 'CSE-DS',
            'DS': 'CSE-DS',
            'CSE(DATA SCIENCE)': 'CSE-DS',
            'COMPUTER SCIENCE AND ENGINEERING (DATA SCIENCE)': 'CSE-DS',
            
            'CSE': 'CSE(Core)',
            'CSE CORE': 'CSE(Core)',
            'CSE-CORE': 'CSE(Core)',
            'CSE (CORE)': 'CSE(Core)',
            'COMPUTER SCIENCE AND ENGINEERING': 'CSE(Core)',
            'CSE - CORE': 'CSE(Core)',
            
            'ISE': 'ISE',
            'INFORMATION SCIENCE': 'ISE',
            'INFORMATION SCIENCE AND ENGINEERING': 'ISE',
            
            'ECE': 'ECE',
            'ELECTRONICS': 'ECE',
            'ELECTRONICS AND COMMUNICATION': 'ECE',
            'ELECTRONICS AND COMMUNICATION ENGINEERING': 'ECE',
        }
        
        text_upper = text.upper()
        
        # Try each pattern
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Get the matched text and normalize it
                dept_raw = match.group(0).strip()
                dept_upper = dept_raw.upper()
                dept_clean = re.sub(r'\s+', ' ', dept_upper)
                dept_clean = re.sub(r'DEPARTMENT\s+OF\s+', '', dept_clean)
                dept_clean = dept_clean.strip()
                
                # Try to map to standard department
                for key, value in DEPARTMENT_MAPPING.items():
                    if key in dept_clean or dept_clean in key:
                        return value
        
        # If no pattern matched, try keyword matching in the whole text
        if 'AIML' in text_upper or 'AI & ML' in text_upper or 'AI&ML' in text_upper or 'ARTIFICIAL INTELLIGENCE' in text_upper:
            return 'AIML'
        elif 'AEROSPACE' in text_upper or 'AERO' in text_upper:
            return 'AERO'
        elif 'CYBERSECURITY' in text_upper or 'CYBER SECURITY' in text_upper:
            return 'CSE-CY'
        elif 'DATA SCIENCE' in text_upper:
            return 'CSE-DS'
        elif 'ISE' in text_upper or 'INFORMATION SCIENCE' in text_upper:
            return 'ISE'
        elif 'ECE' in text_upper or 'ELECTRONICS' in text_upper:
            return 'ECE'
        elif 'CSE' in text_upper or 'COMPUTER SCIENCE' in text_upper:
            return 'CSE(Core)'
        
        # Default fallback
        return ''

    def _extract_category_fallback(self, text: str) -> str:
        """Fallback keyword-based category detection with better pattern matching"""
        text_lower = text.lower()
        
        # More comprehensive keyword patterns
        category_keywords = {
            'Workshop / Hands-on / Training': [
                'workshop', 'hands-on', 'hands on', 'training', 'masterclass',
                'bootcamp', 'skill development', 'practical session'
            ],
            'Seminar': [
                'seminar', 'webinar', 'panel discussion'
            ],
            'Guest Lecture / Expert Talk': [
                'lecture', 'expert talk', 'guest lecture', 'talk', 'speaker',
                'guest speaker', 'invited talk', 'keynote'
            ],
            'Conference / Symposium': [
                'conference', 'symposium', 'summit', 'colloquium', 'congress'
            ],
            'Competition / Hackathon / Quiz': [
                'competition', 'hackathon', 'quiz', 'challenge', 'hackfest',
                'contest', 'coding competition', 'tech fest', 'ideathon'
            ],
            'Orientation / Induction / Welcome': [
                'orientation', 'induction', 'welcome', 'fresher',
                'inauguration', 'opening ceremony'
            ],
            'Research / Report / Paper Presentation': [
                'research', 'paper presentation', 'presentation', 'thesis',
                'project presentation', 'poster presentation'
            ],
            'General / Department Activity': [
                'activity', 'appreciation', 'participation', 'certificate',
                'event', 'program', 'function', 'celebration', 'meetup',
                'gathering', 'session'
            ],
        }
        
        scores = {}
        for category, keywords in category_keywords.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    # Give higher weight to longer, more specific keywords
                    weight = len(kw.split())  # Multi-word phrases get more weight
                    score += weight
            
            if score > 0:
                scores[category] = score
        
        if scores:
            best_category = max(scores, key=scores.get)
            print(f"[NerAgent][FALLBACK] Category detected: '{best_category}' (score={scores[best_category]})")
            return best_category
        
        return 'General / Department Activity'

    def _extract_doc_type_fallback(self, text: str) -> str:
        """Fallback keyword-based doc type detection"""
        text_lower = text.lower()
        
        cert_keywords = ['certificate', 'certification', 'appreciation', 'participation', 'awarded', 'presented to', 'recognition']
        report_keywords = ['report', 'foss', 'submitted by', 'supervision', 'overview', 'event list', 'bachelor of technology']
        
        cert_score = sum(1 for kw in cert_keywords if kw in text_lower)
        report_score = sum(1 for kw in report_keywords if kw in text_lower)
        
        if cert_score > report_score:
            return 'Certificate'
        return 'Report'

    # -------------------------
    # Field consolidation
    # -------------------------
    def _consolidate_fields(
        self,
        text: str,
        preds: List[NerPrediction]
    ) -> Dict[str, Any]:
        """Map predicted entities to final fields with regex fallback"""
        out = {
            'event_name': '',
            'date': '',
            'venue': '',
            'organizer': '',
            'department': '',
            'category': '',
            'doc_type': '',
            'entities': []
        }

        out['entities'] = [p.__dict__ for p in preds]

        # Group by entity type
        by_type: Dict[str, List[NerPrediction]] = {}
        for p in preds:
            t = p.entity_type
            by_type.setdefault(t, []).append(p)
        
        # DEBUG: Print what entity types we actually got
        print(f"[NerAgent][DEBUG] Entity types found: {list(by_type.keys())}")
        for entity_type, entities in by_type.items():
            print(f"[NerAgent][DEBUG]   {entity_type}: {len(entities)} occurrences")
            if entities:
                # Show top 3 examples
                for i, ent in enumerate(entities[:3]):
                    print(f"[NerAgent][DEBUG]     Example {i+1}: '{ent.text}' (score={ent.score:.3f})")

        def choose_best(candidates: List[NerPrediction]) -> NerPrediction:
            """
            Select best entity with quality filtering
            - Filters out low confidence predictions
            - Filters out too-short or garbage text
            - Prefers longer, more complete extractions
            """
            # Quality filtering
            MIN_CONFIDENCE = {
                'EVENT_NAME': 0.35,  # Lower threshold to capture more event names
                'DATE': 0.70,        # Dates need high confidence
                'VENUE': 0.50,
                'ORGANIZER': 0.60,
                'DEPARTMENT': 0.85,  # Departments need high confidence
                'CATEGORY': 0.60,
                'DOC_TYPE': 0.90,    # Doc type needs very high confidence
            }
            
            MIN_LENGTH = {
                'EVENT_NAME': 3,     # At least 3 characters
                'DATE': 4,           # At least "2024" or "Jan 1"
                'VENUE': 2,
                'ORGANIZER': 2,
                'DEPARTMENT': 3,
                'CATEGORY': 4,
                'DOC_TYPE': 6,       # "Report" or "Certificate"
            }
            
            # Determine field type from first candidate
            field_type = None
            for c in candidates:
                for key, variants in {
                    'EVENT_NAME': ['B-EVENT_NAME', 'I-EVENT_NAME', 'EVENT_NAME'],
                    'DATE': ['B-DATE', 'I-DATE', 'DATE'],
                    'VENUE': ['B-VENUE', 'I-VENUE', 'VENUE'],
                    'ORGANIZER': ['B-ORGANIZER', 'I-ORGANIZER', 'ORGANIZER'],
                    'DEPARTMENT': ['B-DEPARTMENT', 'I-DEPARTMENT', 'DEPARTMENT'],
                    'CATEGORY': ['B-CATEGORY', 'I-CATEGORY', 'CATEGORY'],
                    'DOC_TYPE': ['B-DOC_TYPE', 'I-DOC_TYPE', 'DOC_TYPE']
                }.items():
                    if c.entity_type in variants:
                        field_type = key
                        break
                if field_type:
                    break
            
            min_conf = MIN_CONFIDENCE.get(field_type, 0.5)
            min_len = MIN_LENGTH.get(field_type, 2)
            
            # Filter candidates by quality
            quality_candidates = []
            for c in candidates:
                text = c.text.strip()
                
                # Skip garbage patterns
                if text in ['-', 'NA', 'N/A', '—', '–', 'None', 'nil']:
                    continue
                    
                # Skip single characters (except for meaningful ones)
                if len(text) == 1 and text not in ['A', 'I']:
                    continue
                
                # Skip pure numbers for non-date fields
                if field_type != 'DATE' and text.isdigit() and len(text) < 3:
                    continue
                
                # Check minimum confidence
                if c.score < min_conf:
                    continue
                
                # Check minimum length
                if len(text) < min_len:
                    continue
                
                quality_candidates.append(c)
            
            # If no quality candidates, return None to force fallback extraction
            if not quality_candidates:
                print(f"[NerAgent][FILTER] All {field_type} candidates filtered out (low quality)")
                return None
            
            # Return best quality candidate (score and length)
            return sorted(
                quality_candidates,
                key=lambda x: (x.score, (x.end - x.start)),
                reverse=True
            )[0]

        mapping = {
            'EVENT_NAME': ['B-EVENT_NAME', 'I-EVENT_NAME', 'EVENT_NAME'],
            'DATE': ['B-DATE', 'I-DATE', 'DATE'],
            'VENUE': ['B-VENUE', 'I-VENUE', 'VENUE'],
            'ORGANIZER': ['B-ORGANIZER', 'I-ORGANIZER', 'ORGANIZER'],
            'DEPARTMENT': ['B-DEPARTMENT', 'I-DEPARTMENT', 'DEPARTMENT'],
            'CATEGORY': ['B-CATEGORY', 'I-CATEGORY', 'CATEGORY'],
            'DOC_TYPE': ['B-DOC_TYPE', 'I-DOC_TYPE', 'DOC_TYPE']
        }

        # First pass: Extract from NER predictions with quality filtering
        for field, label_variants in mapping.items():
            candidates: List[NerPrediction] = []
            for lv in label_variants:
                candidates.extend(by_type.get(lv, []))

            if not candidates:
                print(f"[NerAgent][MODEL] {field}: Not detected by model (will use fallback)")
                continue
            
            if candidates:
                chosen = choose_best(candidates)
                
                # check_best might return None if all candidates were filtered out
                if chosen is None:
                    print(f"[NerAgent][MODEL] {field}: No quality candidates (all filtered)")
                    continue
                
                out_field = chosen.text.strip()

                print(f"[NerAgent][MODEL] {field}: '{out_field}' (score={chosen.score:.3f})")

                if field == 'DATE':
                    iso = self._normalize_date(out_field)
                    out['date'] = iso or out_field
                elif field == 'DEPARTMENT':
                    normalized = self._normalize_department(out_field)
                    out['department'] = normalized if normalized else out_field
                elif field == 'CATEGORY':
                    # Validate category - must be a known full category name
                    valid_categories = [
                        'Workshop / Hands-on / Training',
                        'Seminar',
                        'Guest Lecture / Expert Talk',
                        'Conference / Symposium',
                        'Competition / Hackathon / Quiz',
                        'Orientation / Induction / Welcome',
                        'Research / Report / Paper Presentation',
                        'General / Department Activity'
                    ]
                    
                    # Check if extracted text matches any valid category
                    is_valid = any(cat.lower() == out_field.lower() for cat in valid_categories)
                    
                    if is_valid:
                        out['category'] = out_field
                    else:
                        # Partial match detected (e.g., "meet" instead of full category)
                        print(f"[NerAgent][MODEL] CATEGORY: '{out_field}' is partial/invalid (rejected)")
                        # Leave empty for fallback to handle
                elif field == 'DOC_TYPE':
                    out['doc_type'] = out_field
                elif field == 'VENUE':
                    # Clean venue - strip trailing punctuation instead of rejecting
                    out_field = out_field.rstrip(',-:;')
                    # Reject very short venues
                    if len(out_field.strip()) < 3:
                        print(f"[NerAgent][MODEL] VENUE: '{out_field}' too short (rejected)")
                    # Reject single short words
                    elif len(out_field.split()) == 1 and len(out_field) < 5:
                        print(f"[NerAgent][MODEL] VENUE: '{out_field}' too short/partial (rejected)")
                    else:
                        out['venue'] = out_field
                else:
                    out[field.lower()] = out_field


        # Second pass: Apply regex fallbacks for missing fields
        print(f"[NerAgent] 🔍 Applying fallback extraction...")

        def log_fallback(field_name, value):
            print(f"[NerAgent][FALLBACK] {field_name}: '{value}'")

        def log_missing(field_name):
            print(f"[NerAgent][MISSING] {field_name}")

        # Event Name
        if not out['event_name']:
            fallback = self._extract_event_name_fallback(text)
            if fallback:
                out['event_name'] = fallback
                log_fallback("EVENT_NAME", fallback)
            else:
                log_missing("EVENT_NAME")

        # Date
        if not out['date']:
            fallback = self._extract_date_fallback(text)
            if fallback:
                out['date'] = fallback
                log_fallback("DATE", fallback)
            else:
                log_missing("DATE")

        # Venue
        if not out['venue']:
            fallback = self._extract_venue_fallback(text)
            if fallback:
                out['venue'] = fallback
                log_fallback("VENUE", fallback)
            else:
                log_missing("VENUE")

        # Organizer
        if not out['organizer']:
            fallback = self._extract_organizer_fallback(text)
            if fallback:
                out['organizer'] = fallback
                log_fallback("ORGANIZER", fallback)
            else:
                log_missing("ORGANIZER")

        # Department
        if not out['department']:
            fallback = self._extract_department_fallback(text)
            if fallback:
                out['department'] = fallback
                log_fallback("DEPARTMENT", fallback)
            else:
                log_missing("DEPARTMENT")

        # Normalize Department if exists
        if out['department']:
            normalized_dept = self._normalize_department(out['department'])
            if normalized_dept and normalized_dept != out['department']:
                print(f"[NerAgent][NORMALIZED] DEPARTMENT → '{normalized_dept}'")
                out['department'] = normalized_dept

        # Category
        if not out['category']:
            fallback = self._extract_category_fallback(text)
            if fallback:
                out['category'] = fallback
                log_fallback("CATEGORY", fallback)
            else:
                log_missing("CATEGORY")

        # Doc Type
        if not out['doc_type']:
            fallback = self._extract_doc_type_fallback(text)
            if fallback:
                out['doc_type'] = fallback
                log_fallback("DOC_TYPE", fallback)
            else:
                log_missing("DOC_TYPE")


        # Determine doc_type if still missing
        if not out['doc_type']:
            out['doc_type'] = DEFAULT_DOC_TYPE

        return out

    # -------------------------
    # Main pipeline
    # -------------------------
    def predict(self, text: str, title: str = '') -> Dict[str, Any]:
        """Main prediction pipeline"""
        print(f"[NerAgent] Starting prediction pipeline...")

        # Extract entities (empty list when model is disabled → all fields use fallback)
        if self.use_model and self.ner_pipeline is not None:
            preds = self.predict_entities(text)
            print(f"[NerAgent] 🏷️  Extracted {len(preds)} entities from NER model")
        else:
            preds = []
            print(f"[NerAgent] ⚡ Skipping BERT model — using regex fallbacks only")

        # Consolidate fields (with fallbacks)
        fields = self._consolidate_fields(text, preds)

        print(f"[NerAgent] 📄 Document Type: {fields['doc_type']}")
        print(f"[NerAgent] 🎯 Category: {fields['category']}")

        return fields

    # -------------------------
    # Helpers
    # -------------------------
    def _normalize_date(self, text: str) -> str:
        """Normalize date string to ISO format with incomplete year fixing"""
        if not text:
            return ''
        
        try:
            # Fix incomplete years (202 -> 2024, 199 -> 1999, etc.)
            import re
            from datetime import datetime
            
            # Pattern: incomplete 3-digit year
            incomplete_year_pattern = r'\b(19|20)(\d)\b'
            match = re.search(incomplete_year_pattern, text)
            if match:
                # Get current year to guess missing digit
                current_year = datetime.now().year
                decade = match.group(1)  # "19" or "20"
                
                if decade == "20":
                    # For 2000s, guess based on current year
                    # If we're in 2026, "202" likely means 2024 or 2025
                    digit = match.group(2)  # The single digit
                    # Try 2020-2029
                    guessed_year = f"202{digit}"
                    text = re.sub(incomplete_year_pattern, guessed_year, text, count=1)
                    print(f"[NerAgent] Fixed incomplete year: 202{digit} -> {guessed_year}")
                elif decade == "19":
                    # For 1900s, likely means 1990s
                    digit = match.group(2)
                    guessed_year = f"199{digit}"
                    text = re.sub(incomplete_year_pattern, guessed_year, text, count=1)
                    print(f"[NerAgent] Fixed incomplete year: 199{digit} -> {guessed_year}")
            
            # Now parse with dateutil
            from dateutil import parser as dateparser
            dt = dateparser.parse(text, fuzzy=True)
            return dt.date().isoformat()
        except Exception as e:
            print(f"[NerAgent] Date parsing failed for '{text}': {e}")
            return ''