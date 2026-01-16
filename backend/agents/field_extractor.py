"""
backend/agents/field_extractor.py

Robust multi-strategy field extraction agent.
Extracts: event_name, date, department, venue, organizer, abstract, category, doc_type
"""

import re
from datetime import datetime, date
from dateutil import parser as dateparser


class RobustFieldExtractor:
    def __init__(self):
        print("[Field Extractor] [INIT] Initialized with multi-strategy extraction")
        
        # Department patterns with variations
        self.dept_patterns = {
            "AIML": [
                r"\bAIML\b",
                r"\bAI\s*&\s*ML\b",
                r"Artificial\s+Intelligence\s+(?:and|&)?\s*Machine\s+Learning",
                r"CSE[\s\-]*AIML",
                r"Computer\s+Science.*?AIML",
                r"Dept\.?\s+of\s+AIML"
            ],
            "CSE(Core)": [
                r"\bCSE\b(?!\s*[-\(])",  # CSE not followed by dash or parenthesis
                r"Computer\s+Science\s+(?:and|&)?\s*Engineering(?!\s*[-\(])",  # CSE not followed by specialization
                r"CSE\s*Core",
                r"CSE\s*-\s*Core",
                r"Department\s+of\s+Computer\s+Science\s+(?:and\s+)?Engineering$"  # Must end here
            ],
            "CSE-DS": [
                r"CSE[\s\-]*DS",
                r"CSE[\s\-]*Data\s+Science",
                r"Computer\s+Science.*?Data\s+Science",
                r"Data\s+Science\s+(?:and|&)?\s*Engineering"
            ],
            "CSE-CY": [
                r"CSE[\s\-]*CY",
                r"CSE[\s\-]*Cyber",
                r"Computer\s+Science.*?Cyber",
                r"Cyber\s+Security\s+(?:and|&)?\s*Engineering"
            ],
            "ISE": [
                r"\bISE\b",
                r"Information\s+Science\s+(?:and|&)?\s*Engineering",
                r"IS\s*&\s*E",
                r"Department\s+of\s+Information\s+Science"
            ],
            "ECE": [
                r"\bECE\b",
                r"Electronics\s+(?:and|&)?\s*Communication",
                r"E\s*&\s*C\s*E",
                r"CSE[\s\-]*EC",
                r"Computer\s+Science.*?Electronics",
                r"Department\s+of\s+Electronics"
            ],
            "AERO": [
                r"\bAERO\b",
                r"Aeronautical\s+Engineering",
                r"Aerospace\s+Engineering",
                r"Department\s+of\s+Aeronautical"
            ]
        }
        
        # Event type patterns
        self.event_patterns = {
            "Workshop": [
                r"\bworkshop\b",
                r"hands[\s-]*on\s+(?:session|training)",
                r"training\s+(?:session|program|workshop)",
                r"practical\s+session"
            ],
            "Seminar": [
                r"\bseminar\b",
                r"lecture\s+series",
                r"talk\s+on"
            ],
            "Guest Lecture": [
                r"guest\s+lecture",
                r"invited\s+(?:talk|lecture)",
                r"expert\s+(?:session|talk)",
                r"guest\s+speaker"
            ],
            "Conference": [
                r"\bconference\b",
                r"symposium",
                r"summit",
                r"proceedings"
            ],
            "Competition": [
                r"\bcompetition\b",
                r"\bcontest\b",
                r"hackathon",
                r"coding\s+challenge",
                r"\bquiz\b"
            ],
            "Orientation": [
                r"orientation",
                r"induction",
                r"welcome\s+program"
            ]
        }
        
        # Certificate detection (high priority)
        self.cert_patterns = [
            r"certificate\s+of\s+(?:achievement|completion|participation|appreciation)",
            r"this\s+is\s+to\s+certify",
            r"(?:awarded|presented)\s+to",
            r"has\s+successfully\s+completed",
            r"is\s+hereby\s+certified",
            r"certifies\s+that"
        ]

    def extract_all_fields(self, text: str, filename: str = "") -> dict:
        """
        Main extraction method - returns all fields.
        Returns dict with: doc_type, event_name, date, department, venue, 
                          organizer, abstract, category, confidence
        """
        if not text or len(text.strip()) < 20:
            return self._get_default_fields()
        
        text_upper = text.upper()
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 2]
        
        print(f"[Extractor] Processing {len(lines)} lines, {len(text)} chars")
        
        # Extract fields in sequence
        doc_type = self._detect_document_type(text, text_upper, lines)
        department = self._extract_department(text, text_upper, lines)
        event_name = self._extract_event_name(text, lines, doc_type)
        event_date = self._extract_date(text, lines)
        venue = self._extract_venue(text, lines)
        organizer = self._extract_organizer(text, lines)
        abstract = self._extract_abstract(text, lines, doc_type)
        category = self._extract_category(text, text_upper, doc_type)
        
        confidence = self._calculate_confidence(
            event_name, event_date, department, venue, organizer, abstract
        )
        
        result = {
            "doc_type": doc_type,
            "event_name": event_name,
            "date": event_date,
            "department": department,
            "venue": venue,
            "organizer": organizer,
            "abstract": abstract,
            "category": category,
            "confidence": confidence
        }
        
        # Log extraction summary
        print(f"[Extractor] ✅ Extraction Complete:")
        print(f"  📄 Type: {doc_type}")
        print(f"  🎯 Event: {event_name[:50]}..." if len(event_name) > 50 else f"  🎯 Event: {event_name}")
        print(f"  📅 Date: {event_date}")
        print(f"  🏢 Dept: {department}")
        print(f"  📍 Venue: {venue}")
        print(f"  👤 Organizer: {organizer}")
        print(f"  📂 Category: {category}")
        print(f"  ✨ Confidence: {confidence}")
        
        return result
    
    def _detect_document_type(self, text: str, text_upper: str, lines: list) -> str:
        """
        Multi-factor document type detection: Certificate vs Report
        Uses: keyword scoring, structural heuristics, layout patterns, and text statistics
        """
        cert_score = 0.0
        report_score = 0.0
        
        # ========== FACTOR 1: Explicit Keyword Matching ==========
        top_text = " ".join(lines[:30]).upper() if lines else ""
        
        # Certificate-specific patterns (high weight)
        for pattern in self.cert_patterns:
            matches = len(re.findall(pattern, text_upper))
            if matches > 0:
                cert_score += matches * 4  # Increased weight
                # Bonus if in top 30 lines (typically where certificates show purpose)
                if re.search(pattern, top_text):
                    cert_score += 3
        
        # Certificate keywords (explicit indicators)
        cert_keywords = {
            "CERTIFICATE": 5,
            "CERTIFY": 4,
            "CERTIFIES": 4,
            "AWARDED": 3,
            "PRESENTED": 3,
            "COMPLETION": 4,
            "PARTICIPATION": 3,
            "RECIPIENT": 2,
            "ACHIEVEMENT": 3,
            "APPRECIATION": 2
        }
        for kw, weight in cert_keywords.items():
            count = text_upper.count(kw)
            if count > 0:
                cert_score += count * weight
        
        # Report/Academic keywords (high weight)
        report_keywords = {
            "ABSTRACT": 5,
            "INTRODUCTION": 4,
            "CONCLUSION": 4,
            "METHODOLOGY": 5,
            "RESULTS": 4,
            "REFERENCES": 5,
            "CHAPTER": 5,
            "TABLE OF CONTENTS": 6,
            "ACKNOWLEDGEMENT": 3,
            "LITERATURE REVIEW": 5,
            "RESEARCH": 4,
            "ANALYSIS": 3,
            "FINDINGS": 3,
            "DISCUSSION": 4,
            "APPENDIX": 4,
            "BIBLIOGRAPHY": 5
        }
        for kw, weight in report_keywords.items():
            count = text_upper.count(kw)
            if count > 0:
                report_score += count * weight
        
        # ========== FACTOR 2: Structural Analysis ==========
        
        # Document length heuristic (refined)
        text_len = len(text)
        if text_len < 1000:
            cert_score += 4  # Short docs → likely certificates
        elif text_len < 3000:
            cert_score += 2
        elif text_len > 5000:
            report_score += 3  # Longer docs → likely reports
        elif text_len > 10000:
            report_score += 5
        
        # Line count analysis (certificates are typically short and sparse)
        non_empty_lines = len([l for l in lines if l.strip()])
        if non_empty_lines < 50:
            cert_score += 2
        elif non_empty_lines > 200:
            report_score += 3
        
        # Average line length (reports have longer, detailed lines)
        avg_line_len = text_len / max(non_empty_lines, 1)
        if avg_line_len < 50:
            cert_score += 1  # Short lines typical of certificates (names, dates)
        elif avg_line_len > 100:
            report_score += 2  # Longer lines typical of narrative reports
        
        # ========== FACTOR 3: Layout & Signature Patterns ==========
        
        # Signature lines (very strong certificate indicator)
        signature_patterns = [
            r"signature\s*[:\-]?\s*_+",
            r"sign\s*here",
            r"_+\s*(?:signature|sign)",
            r"authorized\s+(?:by|signature)",
            r"(?:hod|principal|director|head)\s*[:\-]?\s*_+",
            r"date\s*[:\-]?\s*_+"
        ]
        sig_count = 0
        for pattern in signature_patterns:
            sig_count += len(re.findall(pattern, text, re.IGNORECASE))
        cert_score += sig_count * 2
        
        # Formal document structure (report indicator)
        formal_sections = [
            r"(?:^|\n)(?:SECTION|CHAPTER|PART|SECTION I+)\s+[A-Z]",
            r"(?:^|\n)(?:\d+\.?\s+)?(?:INTRODUCTION|METHODOLOGY|RESULTS|CONCLUSION)",
            r"(?:^|\n)\[?\d+\]?\s+(?:[A-Z][A-Za-z0-9\s]+):",  # Numbered sections
        ]
        formal_count = 0
        for pattern in formal_sections:
            formal_count += len(re.findall(pattern, text, re.MULTILINE | re.IGNORECASE))
        report_score += formal_count * 3
        
        # ========== FACTOR 4: Content Density Analysis ==========
        
        # Paragraph analysis (reports have dense paragraphs)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paragraphs:
            avg_para_len = sum(len(p.split()) for p in paragraphs) / len(paragraphs)
            if avg_para_len < 20:
                cert_score += 2  # Short paragraphs → certificates
            elif avg_para_len > 100:
                report_score += 3  # Long paragraphs → reports
        
        # ========== FACTOR 5: Topic/Context Keywords ==========
        
        # Certificate context: personal achievement, dates, names
        personal_keywords = ["NAME", "STUDENT", "PARTICIPANT", "CANDIDATE", "DATE OF ISSUE"]
        personal_count = sum(1 for kw in personal_keywords if kw in text_upper)
        cert_score += personal_count * 1.5
        
        # Report context: technical depth
        technical_keywords = ["MODEL", "ALGORITHM", "IMPLEMENTATION", "PERFORMANCE", "EVALUATION"]
        tech_count = sum(1 for kw in technical_keywords if kw in text_upper)
        report_score += tech_count * 2
        
        # ========== FACTOR 6: Formal Language Indicators ==========
        
        # Passive voice (stronger in reports/academic writing)
        passive_patterns = [
            r"\b(?:was|were|been|is|are)\s+(?:conducted|presented|analyzed|performed|demonstrated)",
            r"\bhas\s+been\s+",
            r"\bmay\s+be\s+",
            r"\bcan\s+be\s+"
        ]
        passive_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in passive_patterns)
        report_score += passive_count * 1
        
        # ========== FACTOR 7: Recipient/Issuer Language ==========
        
        # First-person academic writing (reports)
        academic_language = [
            r"\bwe\s+(?:conducted|present|propose|demonstrate)",
            r"\b(?:this|the)\s+(?:paper|thesis|report|study|research)",
            r"\bour\s+(?:findings|results|approach|work)"
        ]
        academic_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in academic_language)
        report_score += academic_count * 2
        
        # Recipient-focused language (certificates)
        recipient_patterns = [
            r"\b(?:to|for)\s+[A-Z][A-Za-z\s]+(?:who|that)?\s+(?:has|have|successfully)",
            r"\bthis\s+certificate\s+(?:is\s+)?(?:awarded|presented|given)",
            r"\bin\s+(?:recognition|appreciation|acknowledgment)"
        ]
        recipient_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in recipient_patterns)
        cert_score += recipient_count * 2
        
        # ========== FINAL SCORING & DECISION ==========
        
        # Debug output
        print(f"[Extractor] Doc Type Analysis:")
        print(f"   Certificate Score: {cert_score:.1f}")
        print(f"   Report Score:      {report_score:.1f}")
        print(f"   Text Length:       {text_len} chars")
        print(f"   Non-empty Lines:   {non_empty_lines}")
        print(f"   Avg Line Length:   {avg_line_len:.1f}")
        print(f"   Paragraphs:        {len(paragraphs)}")
        
        # Decision logic: if scores are very close, use tie-breaker heuristics
        diff = abs(cert_score - report_score)
        if diff < 5:  # Very close call
            # Tie-breaker: if both have some keywords, favor length (more reliable)
            if text_len < 2000:
                result = "Certificate"
            else:
                result = "Report"
            print(f"   [Tie-breaker] Scores within 5 points, using length heuristic")
        else:
            result = "Certificate" if cert_score > report_score else "Report"
        
        print(f"   ✅ Detected Type: {result}\n")
        
        return result
    
    def _extract_event_name(self, text: str, lines: list, doc_type: str) -> str:
        """Extract event name using multiple strategies with improved priority"""
        
        # ========== STRATEGY 1: Quoted/Emphasized Titles (HIGHEST PRIORITY) ==========
        # Matches "Event Name" or similar highlighted titles - ANY type of event
        # Support both ASCII quotes and smart/curly quotes from PDF conversions (Unicode U+201C, U+201D)
        quoted_patterns = [
            r'[\u201c"]([^"][\u201d"]{10,150}?)[\u201d"]',  # Curly or straight double quotes, smart or ASCII
            r"[\u2018']([^'][\u2019']{10,150}?)[\u2019']",  # Curly or straight single quotes
            r'«([^«»]{10,150})»',  # French quotation marks
        ]
        
        for pattern in quoted_patterns:
            try:
                matches = re.findall(pattern, text)
                for match in matches:
                    title = match.strip()
                    # Filter out noise (dates, codes, etc.)
                    if not re.search(r'^\d{1,2}[\-/]\d{1,2}', title) and len(title) > 8:
                        # Basic validation - should have meaningful length and not be a code
                        if not re.match(r'^[A-Z]{2,10}$', title):  # Skip pure acronyms
                            # Preserve original casing for quoted titles, remove extra quotes
                            title_clean = title.strip('\'"""\'«»""')
                            print(f"[Extractor] Event name (quoted/emphasized): {title_clean}")
                            return title_clean
            except Exception as e:
                # Skip pattern if there's an issue
                pass
        
        # ========== STRATEGY 1B: Look for "Report On / Event On" pattern (common in academic documents) ==========
        # Works for any event type: workshops, seminars, conferences, competitions, etc.
        report_pattern = r'(?:report\s+on|event\s+on|activity\s+on|seminar\s+on|workshop\s+on|conference\s+on|titled|topic)\s+["\'\u201c\u201d]?([^\n\.]+?)["\'\u201c\u201d]?(?:\n|$)'
        match = re.search(report_pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up title - remove all types of quotes (ASCII and Unicode)
            title = title.strip('\'""\u201c\u201d\u2018\u2019«»')
            title = re.sub(r'\s+', ' ', title)
            if 8 < len(title) <= 200 and not re.search(r'^\d{1,2}[\-/]\d{1,2}', title):
                print(f"[Extractor] Event name (Event/Report pattern): {title}")
                return title
        
        # ========== STRATEGY 2: Explicit Labels ==========
        label_patterns = [
            r"(?:event|title|program|activity|topic|subject)\s*[:\-]\s*(.+?)(?:\n|$)",
            r"(?:name\s+of\s+(?:the\s+)?(?:event|program|workshop|seminar|conference))\s*[:\-]\s*(.+?)(?:\n|$)",
        ]
        
        for pattern in label_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                title = re.sub(r'\s+', ' ', title)
                title = title.split('\n')[0]
                # Remove trailing commas and whitespace
                title = title.rstrip(',').rstrip()
                
                # Improved person name detection - more flexible for multi-part names
                # Patterns to detect: John Smith, Mr. John K. Smith, A B C D E...
                # Also check if it starts with common prefixes like "Mr", "Dr", "Prof"
                is_person_name = False
                
                # Check if looks like a typical person name: 2-5 words, all capitalized, mostly short words
                words = title.split()
                if len(words) >= 2 and len(words) <= 5:
                    # Most words should be short (typical for names)
                    short_words = sum(1 for w in words if 1 <= len(w) <= 4)
                    if short_words >= len(words) - 1:  # At least n-1 short words
                        # Check if all words start with capital (typical for names)
                        all_caps = all(w[0].isupper() for w in words if w)
                        if all_caps:
                            # Check for person title prefixes
                            if words[0] in ["Mr", "Mrs", "Ms", "Dr", "Prof", "Sir", "Madam"]:
                                is_person_name = True
                            # Or check if it looks like FirstName MiddleInitial(s) LastName
                            elif len(words) >= 2 and all(len(w) <= 1 for w in words[1:-1]):
                                is_person_name = True  # Initials in middle
                
                if not is_person_name:
                    if 3 <= len(title.split()) <= 20 and len(title) > 10:
                        print(f"[Extractor] Event name (labeled): {title}")
                        return title.title()
        
        # ========== STRATEGY 3: Certificate-specific patterns ==========
        if doc_type == "Certificate":
            cert_patterns = [
                r"certificate\s+of\s+\w+\s+(?:for|in|on)\s+(.+?)(?:\.|held|organized|conducted|on\s+\d)",
                r"(?:workshop|seminar|conference|training|program|event)\s+(?:on|in)?\s+(.+?)(?:\.|held|organized|conducted|$)",
                r"successfully\s+completed\s+(?:the\s+)?(.+?)(?:\.|held|organized|on\s+\d)",
                r"participated\s+in\s+(?:the\s+)?(.+?)(?:\.|held|organized|on\s+\d)",
                r"(?:report\s+on|activity\s+on|event\s+on)\s+(.+?)(?:\n|$)"
            ]
            
            for pattern in cert_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    title = match.group(1).strip()
                    title = re.sub(r'\s+', ' ', title)
                    title = re.sub(r'\s+on\s+\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}.*$', '', title)
                    if 3 <= len(title.split()) <= 25 and len(title) > 10:
                        print(f"[Extractor] Event name (certificate pattern): {title}")
                        return title.title()
        
        # ========== STRATEGY 4: Lines with Event Keywords (HIGH PRIORITY) ==========
        # Look for lines mentioning workshops, seminars, conferences, etc.
        for line in lines[:30]:
            words = line.split()
            if 3 <= len(words) <= 25 and len(line) > 12:
                # Skip metadata lines
                if any(skip in line.upper() for skip in ["UNIVERSITY", "DEPARTMENT", "SCHOOL", "SUBMITTED BY", "SUPERVISED"]):
                    continue
                # Skip pure dates
                if re.match(r'^\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}', line):
                    continue
                
                line_upper = line.upper()
                if any(kw in line_upper for kw in ["WORKSHOP", "SEMINAR", "CONFERENCE", "TRAINING", "LECTURE", "MEETUP", "TALK", "SYMPOSIUM"]):
                    print(f"[Extractor] Event name (keyword line): {line}")
                    return line.title()
        
        # ========== STRATEGY 5: All-caps prominent lines ==========
        for line in lines[:30]:
            words = line.split()
            if 3 <= len(words) <= 20 and len(line) > 15:
                if line.isupper():
                    # Skip common headers
                    if any(skip in line for skip in ["UNIVERSITY", "DEPARTMENT", "CERTIFICATE", "SCHOOL", "ENGINEERING"]):
                        continue
                    print(f"[Extractor] Event name (caps line): {line}")
                    return line.title()
        
        # ========== STRATEGY 6: First substantial line ==========
        for line in lines[:20]:
            words = line.split()
            if 5 <= len(words) <= 25 and 20 < len(line) <= 200:
                # Skip dates, departments, common headers
                if re.search(r'^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', line):
                    continue
                if any(skip in line.upper() for skip in ["DEPARTMENT", "UNIVERSITY", "COLLEGE", "SCHOOL", "DAYANANDA"]):
                    continue
                # Skip if it looks like author/submission info
                if any(skip in line.upper() for skip in ["SUBMITTED BY", "UNDER THE", "SUPERVISION", "ENGINEERING"]):
                    continue
                print(f"[Extractor] Event name (first substantial): {line}")
                return line.title()
        
        print("[Extractor] Event name: Untitled (fallback)")
        return "Untitled Event"
    
    def _extract_date(self, text: str, lines: list) -> str:
        """Extract date using multiple formats"""
        
        # Comprehensive date patterns
        date_patterns = [
            # Labeled dates
            r"(?:date|on|held\s+on|conducted\s+on|dated)\s*[:\-]?\s*(\d{1,2}[\s\-/\.]\w+[\s\-/\.]\d{2,4})",
            r"(?:date|on|held\s+on|conducted\s+on|dated)\s*[:\-]?\s*(\d{1,2}[\s\-/\.]\d{1,2}[\s\-/\.]\d{2,4})",
            # Ordinal dates (15th October 2024)
            r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s,]+\d{4})",
            # Month Day, Year (October 15, 2024)
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}[\s,]+\d{4})",
            # DD/MM/YYYY or DD-MM-YYYY
            r"(\d{1,2}[\s\-/\.]\d{1,2}[\s\-/\.]\d{4})",
            # YYYY-MM-DD (ISO format)
            r"(\d{4}[\-/]\d{1,2}[\-/]\d{1,2})"
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    parsed = dateparser.parse(match, fuzzy=True)
                    if parsed and 2000 <= parsed.year <= 2030:
                        result = parsed.date().isoformat()
                        print(f"[Extractor] Date found (pattern): {result} from '{match}'")
                        return result
                except:
                    continue
        
        # Search line by line in first 30 lines
        for line in lines[:30]:
            try:
                parsed = dateparser.parse(line, fuzzy=True)
                if parsed and 2000 <= parsed.year <= 2030:
                    result = parsed.date().isoformat()
                    print(f"[Extractor] Date found (fuzzy): {result} from '{line}'")
                    return result
            except:
                continue
        
        result = date.today().isoformat()
        print(f"[Extractor] Date: {result} (default to today)")
        return result
    
    def _extract_department(self, text: str, text_upper: str, lines: list) -> str:
        """Extract department with improved matching"""
        
        # Strategy 1: Explicit "Department of X" patterns
        dept_explicit_patterns = [
            r"department\s+of\s+([\w\s&(),]+?)(?:\s+(?:hosted|organized|conducted|presents)|[,\.\n])",
            r"dept\.?\s+of\s+([\w\s&(),]+?)(?:\s+(?:hosted|organized)|[,\.\n])",
            r"organized\s+by\s+(?:the\s+)?department\s+of\s+([\w\s&(),]+?)(?:[,\.\n])"
        ]
        
        for pattern in dept_explicit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dept_text = match.group(1).strip()
                normalized = self._normalize_department(dept_text)
                print(f"[Extractor] Department (explicit): {normalized} from '{dept_text}'")
                return normalized
        
        # Strategy 2: Pattern matching for codes/keywords
        for dept_code, patterns in self.dept_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    print(f"[Extractor] Department (pattern): {dept_code}")
                    return dept_code
        
        print("[Extractor] Department: General (fallback)")
        return "General"
    
    def _normalize_department(self, dept_text: str) -> str:
        """Normalize department text to standard codes"""
        dept_upper = dept_text.upper()
        
        # Priority order matters! Check specializations BEFORE core CSE
        
        # AI/ML variations (highest priority for CSE-AIML)
        if any(kw in dept_upper for kw in ["AIML", "AI & ML", "AI&ML", "CSE-AIML", "CSE AIML"]):
            return "AIML"
        
        if "ARTIFICIAL INTELLIGENCE" in dept_upper or "MACHINE LEARNING" in dept_upper:
            return "AIML"
        
        # Data Science variations
        if any(kw in dept_upper for kw in ["CSE-DS", "CSE DS", "DATA SCIENCE"]):
            return "CSE-DS"
        
        # Cyber Security variations
        if any(kw in dept_upper for kw in ["CSE-CY", "CSE CY", "CYBER"]):
            return "CSE-CY"
        
        # Electronics/Communication (before CSE check)
        if any(kw in dept_upper for kw in ["ELECTRONICS", "COMMUNICATION", "ECE", "E&CE", "CSE-EC"]):
            return "ECE"
        
        # ISE variations (before CSE check)
        if "INFORMATION SCIENCE" in dept_upper or "IS&E" in dept_upper or "ISE" in dept_upper:
            return "ISE"
        
        # AERO variations
        if any(kw in dept_upper for kw in ["AERO", "AEROSPACE", "AERONAUTICAL"]):
            return "AERO"
        
        # CSE Core - ONLY if it's pure Computer Science Engineering with NO specialization
        # This should be last to avoid false matches
        if "COMPUTER SCIENCE" in dept_upper:
            # Check if any specialization keywords exist
            specializations = ["AIML", "DATA SCIENCE", "CYBER", "ELECTRONICS", "INFORMATION"]
            has_specialization = any(spec in dept_upper for spec in specializations)
            
            if not has_specialization:
                return "CSE(Core)"
        
        # Return truncated original if no match
        return dept_text[:30]
    
    def _extract_venue(self, text: str, lines: list) -> str:
        """Extract venue/location with improved pattern matching"""
        
        # ========== STRATEGY 1: Explicit patterns ==========
        venue_patterns = [
            r"(?:venue|location|place|held\s+at|held\s+in|location)\s*[:\-]?\s*([^\n\.]+)",
            r"(?:hall|room|auditorium|lab|center|block)\s*[:\-]\s*([^\n\.]+)",
            r"(?:held|conducted|organized)\s+at\s+([^\n\.]+?)(?:\.|,|$)",
            r"(?:at|location)\s+([\w\s]+(?:hall|auditorium|room|building|block|lab|center|technologies|tech|university|college))",
        ]
        
        for pattern in venue_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                venue = match.group(1).strip()
                venue = re.sub(r'\s+', ' ', venue)
                # Extract just the venue name (before additional details like postal code)
                venue = venue.split(',')[0].strip()
                if 2 <= len(venue.split()) <= 20 and 5 < len(venue) <= 150:
                    print(f"[Extractor] Venue (pattern): {venue}")
                    return venue
        
        # ========== STRATEGY 2: Line-by-line search for location keywords ==========
        location_keywords = ["location", "venue", "held at", "at", "navi", "tech", "bengaluru", "bangalore"]
        
        for line in lines[:50]:
            line_upper = line.upper()
            # Check if line contains location keywords
            if any(kw in line_upper for kw in location_keywords):
                # Skip generic headers
                if any(skip in line_upper for skip in ["UNIVERSITY", "DEPARTMENT", "SCHOOL", "SUBMITTED"]):
                    continue
                
                # If line has a colon, extract the value after it
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        venue = parts[1].strip()
                        venue = re.sub(r'\s+', ' ', venue)
                        venue = venue.split(',')[0].strip()
                        if 2 <= len(venue.split()) <= 20 and 5 < len(venue) <= 150:
                            print(f"[Extractor] Venue (line-based): {venue}")
                            return venue
                # Or if the line itself contains clear location info
                elif any(loc in line_upper for loc in ["TECHNOLOGIES", "TECH", "HALL", "CENTER", "AUDITORIUM"]):
                    venue = line.strip()
                    venue = re.sub(r'\s+', ' ', venue)
                    if 2 <= len(venue.split()) <= 20 and 5 < len(venue) <= 150:
                        print(f"[Extractor] Venue (inferred): {venue}")
                        return venue
        
        print("[Extractor] Venue: Not specified (fallback)")
        return "Venue not specified"
    
    def _extract_organizer(self, text: str, lines: list) -> str:
        """Extract organizer/coordinator with improved pattern matching"""
        
        # ========== STRATEGY 1: Explicit patterns with enhanced keywords ==========
        organizer_patterns = [
            # Standard patterns
            r"(?:organized|conducted|coordinated|hosted)\s+by\s*[:\-]?\s*([^\n\.]+?)(?:\.|$)",
            r"(?:organizer|coordinator|convenor)\s*[:\-]\s*([^\n\.]+?)(?:\.|$)",
            r"(?:under\s+(?:the\s+)?(?:guidance|supervision)\s+of)\s+([^\n\.]+?)(?:\.|$)",
            # Team/Group patterns (new)
            r"(?:by\s+(?:the\s+)?(?:team|group|organization|committee)\s+)?([A-Z][A-Za-z\s&]+(?:team|group|organization))\b",
            r"organiser\s*[:\-]?\s*([^\n\.]+?)(?:\.|$)",
            r"presented\s+by\s+([^\n\.]+?)(?:\.|$)",
        ]
        
        for pattern in organizer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                organizer = match.group(1).strip()
                organizer = re.sub(r'\s+', ' ', organizer)
                organizer = organizer.split(',')[0]  # Take first part before comma
                if 2 <= len(organizer.split()) <= 15 and 5 < len(organizer) <= 100:
                    # Skip generic words
                    if not re.search(r'^\d{1,2}[\-/]\d{1,2}', organizer):
                        print(f"[Extractor] Organizer (pattern): {organizer}")
                        return organizer
        
        # ========== STRATEGY 2: Line-by-line search in top 40 lines ==========
        # Look for lines containing "Organiser:", "by:", "team", etc.
        organizer_keywords = ["organis", "organiz", "by", "presented by", "conducted by", "coordinated by", "team"]
        
        for i, line in enumerate(lines[:40]):
            line_upper = line.upper()
            # Skip if it's metadata
            if any(skip in line_upper for skip in ["UNIVERSITY", "DEPARTMENT", "SCHOOL", "SUBMITTED"]):
                continue
            
            # Check if line contains organizer keywords
            if any(kw in line_upper for kw in organizer_keywords):
                # Try to extract value after colon
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        value = re.sub(r'\s+', ' ', value)
                        if 2 <= len(value.split()) <= 15 and 5 < len(value) <= 100:
                            if not re.search(r'^\d{1,2}[\-/]\d{1,2}', value):
                                print(f"[Extractor] Organizer (line-based): {value}")
                                return value
                # Or if line itself looks like organizer info
                else:
                    # Look for "FOSS UNITED Bangalore team" style
                    match = re.search(r'([A-Z][A-Za-z\s&]+(?:team|organization|group|Bangalore|Committee))\b', line)
                    if match:
                        organizer = match.group(1).strip()
                        organizer = re.sub(r'\s+', ' ', organizer)
                        if 2 <= len(organizer.split()) <= 15 and 5 < len(organizer) <= 100:
                            print(f"[Extractor] Organizer (inferred): {organizer}")
                            return organizer
        
        # ========== STRATEGY 3: Look for capitalized proper nouns near common organizer indicators ==========
        # Search for patterns like "team: XYZ" or "by XYZ" - ANY organization type
        team_patterns = [
            r"(?:by|organized\s+by)\s+([A-Z][A-Za-z\s&\.]+(?:team|organization|group|committee|institute|department|center|lab))",
            r"([A-Z][A-Za-z\s&\.]+?)\s+(?:team|organization|group|committee|institute|department)",
        ]
        
        for pattern in team_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, str):
                    organizer = match.strip()
                    # Clean up
                    organizer = re.sub(r'\s+', ' ', organizer)
                    if 2 <= len(organizer.split()) <= 15 and 5 < len(organizer) <= 100:
                        # Skip generic descriptors
                        if not re.search(r'^(the|a|an)\s+', organizer, re.IGNORECASE):
                            print(f"[Extractor] Organizer (team/org inferred): {organizer}")
                            return organizer
        
        print("[Extractor] Organizer: Not specified (fallback)")
        return "Organizer not specified"
    
    def _extract_abstract(self, text: str, lines: list, doc_type: str) -> str:
        """Extract abstract or description"""
        
        if doc_type == "Certificate":
            # For certificates, create brief description from top lines
            cert_text = " ".join(lines[:10])
            cert_text = re.sub(r'\s+', ' ', cert_text)
            result = f"Certificate document. {cert_text[:200]}..."
            print(f"[Extractor] Abstract (cert): {len(result)} chars")
            return result
        
        # Look for explicit abstract section
        abstract_patterns = [
            r"abstract\s*[:\-]?\s*\n((?:.+\n?){1,10})",
            r"summary\s*[:\-]?\s*\n((?:.+\n?){1,10})",
            r"introduction\s*[:\-]?\s*\n((?:.+\n?){1,10})"
        ]
        
        for pattern in abstract_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                abstract = match.group(1).strip()
                abstract = re.sub(r'\s+', ' ', abstract)
                if 50 <= len(abstract) <= 1000:
                    print(f"[Extractor] Abstract (labeled): {len(abstract)} chars")
                    return abstract[:500]
        
        # Fallback: Use first substantial paragraph
        paragraphs = text.split('\n\n')
        for para in paragraphs[:5]:
            para = para.strip()
            para = re.sub(r'\s+', ' ', para)
            if 50 <= len(para) <= 1000:
                print(f"[Extractor] Abstract (paragraph): {len(para)} chars")
                return para[:500]
        
        result = "Abstract not found"
        print(f"[Extractor] Abstract: {result}")
        return result
    
    def _extract_category(self, text: str, text_upper: str, doc_type: str) -> str:
        """Extract event category"""
        
        if doc_type == "Certificate":
            return "Certificate Event"
        
        # Check event type patterns
        for category, patterns in self.event_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    print(f"[Extractor] Category: {category}")
                    return category
        
        # Check for research indicators
        research_keywords = [
            "ABSTRACT", "METHODOLOGY", "RESULTS", "CONCLUSION",
            "REFERENCES", "LITERATURE REVIEW", "DATA ANALYSIS"
        ]
        research_score = sum(1 for kw in research_keywords if kw in text_upper)
        
        if research_score >= 3:
            print("[Extractor] Category: Research/Report")
            return "Research/Report"
        
        print("[Extractor] Category: General Event (fallback)")
        return "General Event"
    
    def _calculate_confidence(self, event_name, date_val, dept, venue, organizer, abstract) -> float:
        """Calculate extraction confidence score (0.0 to 1.0)"""
        score = 0.0
        
        if event_name and event_name != "Untitled Event":
            score += 0.25
        if date_val and date_val != date.today().isoformat():
            score += 0.20
        if dept and dept != "General":
            score += 0.20
        if venue and venue != "Venue not specified":
            score += 0.15
        if organizer and organizer != "Organizer not specified":
            score += 0.10
        if abstract and abstract != "Abstract not found":
            score += 0.10
        
        return round(min(score, 1.0), 2)
    
    def _get_default_fields(self) -> dict:
        """Return default values when extraction fails"""
        return {
            "doc_type": "Report",
            "event_name": "Untitled Event",
            "date": date.today().isoformat(),
            "department": "General",
            "venue": "Venue not specified",
            "organizer": "Organizer not specified",
            "abstract": "No content extracted",
            "category": "General Event",
            "confidence": 0.3
        }