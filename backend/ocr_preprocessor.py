"""
OCR Text Pre-processing Enhancement
Cleans OCR text before NER extraction for better accuracy
"""

import re
from typing import Dict, List


class OCRPreprocessor:
    """Clean and normalize OCR text for NER"""
    
    def __init__(self):
        # Common OCR character errors to fix
        self.char_fixes = {
            # Numbers confused with letters
            r'\b0(?=[a-z])': 'O',      # 0rganizer → Organizer
            r'\b1(?=[a-z])': 'I',       # 1nnovation → Innovation  
            r'(\w)1e': r'\1le',         # Hal1 → Hall, Tab1e → Table
            r'(\w)1(\w)': r'\1l\2',     # General word-internal 1→l
            
            # Letters confused with numbers
            r'(?<=[0-9])O(?=[0-9])': '0',  # 2O25 → 2025
            r'(?<=[0-9])l(?=[0-9])': '1',  # 20l5 → 2015
            
            # Common character substitutions
            r'rn': 'm',  # 'rn' often misread as 'm'
        }
        
        # Common word-level mistakes
        self.word_fixes = {
            'arid': 'and',
            'oi': 'of',
            '0f': 'of',
            'tne': 'the',
            'ine': 'the',
            't0': 'to',
            'tc': 'to',
            'rneet': 'meet',
            'rnachine': 'machine',
            'cornputer': 'computer',
        }
    
    def normalize_whitespace(self, text: str) -> str:
        """Fix spacing issues from OCR"""
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Replace multiple newlines with single newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces before punctuation
        text = re.sub(r'\s+([,.:;!?])', r'\1', text)
        
        # Add space after punctuation if missing
        text = re.sub(r'([,.:;])(?=[A-Za-z])', r'\1 ', text)
        
        # Fix broken words across lines (hyphenation)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def fix_character_errors(self, text: str) -> str:
        """Fix common OCR character recognition errors"""
        for pattern, replacement in self.char_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
    
    def fix_word_errors(self, text: str) -> str:
        """Fix common OCR word-level errors"""
        words = text.split()
        fixed_words = []
        
        for word in words:
            # Check lowercase version
            lower_word = word.lower()
            
            if lower_word in self.word_fixes:
                # Apply fix while preserving capitalization
                replacement = self.word_fixes[lower_word]
                
                if word.isupper():
                    replacement = replacement.upper()
                elif word[0].isupper():
                    replacement = replacement.capitalize()
                
                fixed_words.append(replacement)
            else:
                fixed_words.append(word)
        
        return ' '.join(fixed_words)
    
    def remove_artifacts(self, text: str) -> str:
        """Remove common OCR artifacts and noise"""
        # Remove page numbers (standalone numbers on lines)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove "Page N" markers
        text = re.sub(r'\b[Pp]age\s+\d+\b', '', text)
        
        # Remove excessive punctuation
        text = re.sub(r'[.,;:]{2,}', ',', text)
        
        # Remove standalone special characters
        text = re.sub(r'\s[*#@$%^&]{1,2}\s', ' ', text)
        
        # Remove excessive dashes/underscores
        text = re.sub(r'[-_]{3,}', '', text)
        
        return text
    
    def normalize_dates(self, text: str) -> str:
        """Normalize various date formats"""
        # Fix incomplete years (202 → 2024, 20 → 2024)
        # This is context-dependent, so we look for date patterns
        
        # Pattern: "20th March 202" → "20th March 2024"
        current_year_prefix = '202'  # Adjust as needed
        text = re.sub(
            r'(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+)202(?!\d)',
            lambda m: m.group(1) + '2024',  # Default to current year
            text,
            flags=re.IGNORECASE
        )
        
        # Pattern: "March 202" → "March 2024"
        text = re.sub(
            r'(\w+\s+)202(?!\d)',
            lambda m: m.group(1) + '2024',
            text,
            flags=re.IGNORECASE
        )
        
        return text
    
    def expand_common_abbreviations(self, text: str) -> str:
        """Expand common abbreviations that OCR might create"""
        # Department abbreviations
        dept_abbrev = {
            r'\bCSE\b': 'Computer Science Engineering',
            r'\bIT\b(?![\w])': 'Information Technology',  # Negative lookahead to avoid "IT'S"
            r'\bECE\b': 'Electronics and Communication Engineering',
            r'\bMCA\b': 'Computer Applications',
            r'\bMBA\b': 'Business Administration',
        }
        
        for abbrev, full_form in dept_abbrev.items():
            # Only expand if not part of larger word
            text = re.sub(abbrev, full_form, text)
        
        return text
    
    def standardize_case(self, text: str) -> str:
        """Standardize case for better entity recognition"""
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            
            # If entire line is UPPERCASE and longer than 3 words, likely a heading
            words = line.split()
            if len(words) > 3 and line.isupper():
                # Convert to Title Case for better NER
                line = line.title()
            
            processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def clean(self, text: str, aggressive: bool = False) -> str:
        """
        Apply all cleaning steps
        
        Args:
            text: Raw OCR text
            aggressive: If True, applies more aggressive cleaning (might lose info)
        
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Step 1: Normalize whitespace
        text = self.normalize_whitespace(text)
        
        # Step 2: Remove artifacts
        text = self.remove_artifacts(text)
        
        # Step 3: Fix character-level errors
        text = self.fix_character_errors(text)
        
        # Step 4: Fix word-level errors
        text = self.fix_word_errors(text)
        
        # Step 5: Normalize dates
        text = self.normalize_dates(text)
        
        # Step 6: Expand abbreviations (optional)
        if aggressive:
            text = self.expand_common_abbreviations(text)
            text = self.standardize_case(text)
        
        # Final whitespace cleanup
        text = self.normalize_whitespace(text)
        
        return text


# Example usage and testing
if __name__ == "__main__":
    preprocessor = OCRPreprocessor()
    
    # Test cases
    test_texts = [
        # Case 1: Character errors
        "0rganized by Department of Computer Science",
        
        # Case 2: Spacing issues
        "WORKSHOP  ON    MACHINE   LEARNING",
        
        # Case 3: Incomplete year
        "Date: 30th March 202",
        
        # Case 4: Word errors
        "0f the rnachine learning and Al course",
        
        # Case 5: Mixed issues
        "CODING  HACKATH0N 202\nPage 1\nVenue: lnnovation Hub",
    ]
    
    print("OCR PREPROCESSING EXAMPLES")
    print("=" * 60)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\nTest {i}:")
        print(f"Original: {text}")
        print(f"Cleaned:  {preprocessor.clean(text)}")
        print(f"Aggressive: {preprocessor.clean(text, aggressive=True)}")
        print("-" * 60)
