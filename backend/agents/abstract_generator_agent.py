# abstract_generator_agent.py
"""
Abstract Generator Agent - generates summaries/abstracts from event reports
Uses Google Gemini API for intelligent abstract generation
"""

import re
import os
from typing import Optional
import google.generativeai as genai


class AbstractGeneratorAgent:
    def __init__(self, method: str = 'gemini'):
        """
        Initialize Abstract Generator
        
        Args:
            method: 'gemini' (default), 'extractive', or 'fallback'
        """
        self.method = method
        print(f"[AbstractGenerator] Initialized with method: {method}")
        
        # Initialize Gemini API
        if method == 'gemini':
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                # Use gemini-3-flash (more capable)
                self.model = genai.GenerativeModel('gemini-3-flash-preview')
                print("[AbstractGenerator] Gemini API configured successfully (gemini-3-flash-preview)")
            else:
                print("[AbstractGenerator] Warning: GEMINI_API_KEY not found, falling back to extractive method")
                self.method = 'extractive'
                self.model = None
        else:
            self.model = None
        
    def generate(self, text: str, max_length: int = 300) -> str:
        """
        Generate abstract from text using Gemini API
        
        Args:
            text: Full document text (report/certificate)
            max_length: Maximum length of generated abstract
            
        Returns:
            Generated abstract (string)
        """
        if not text or len(text.strip()) < 100:
            return "Insufficient content for abstract generation."
        
        # Try Gemini API first
        if self.method == 'gemini' and self.model:
            try:
                abstract = self._gemini_summary(text, max_length)
                print(f"[AbstractGenerator] Generated {len(abstract)} character abstract using Gemini")
                return abstract
            except Exception as e:
                print(f"[AbstractGenerator] Gemini API failed: {e}, falling back to extractive")
                abstract = self._extractive_summary(text, max_length)
        else:
            # Fallback to extractive method
            abstract = self._extractive_summary(text, max_length)
        
        print(f"[AbstractGenerator] Generated {len(abstract)} character abstract")
        return abstract
    
    def _gemini_summary(self, text: str, max_length: int) -> str:
        """
        Generate abstract using Google Gemini API
        
        Args:
            text: Full document text
            max_length: Maximum length of abstract
            
        Returns:
            Generated abstract
        """
        # Truncate text if too long (Gemini has token limits)
        max_input_length = 10000
        if len(text) > max_input_length:
            text = text[:max_input_length] + "..."
        
        prompt = f"""Analyze the following event report or certificate document and generate a concise, informative abstract.

The abstract should:
- Be approximately {max_length} characters long
- Capture the key information: event name, date, purpose, participants, and outcomes
- Be written in professional, clear language
- Focus on the most important details
- Be suitable for quick reference and documentation

Document text:
{text}

Generate the abstract:"""
        
        try:
            response = self.model.generate_content(prompt)
            abstract = response.text.strip()
            
            # Ensure length constraint
            if len(abstract) > max_length + 100:
                abstract = abstract[:max_length] + "..."
            
            return abstract
        
        except Exception as e:
            print(f"[AbstractGenerator] Gemini API error: {e}")
            raise
    
    def _extractive_summary(self, text: str, max_length: int) -> str:
        """
        Simple extractive summarization (placeholder)
        Takes first few sentences that look informative
        """
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Filter out common non-content sentences
        filtered = []
        skip_patterns = [
            r'^(date|venue|time|organized by)',
            r'^(certificate|report|document)',
            r'^\d+[\./\-]\d+',  # Dates
        ]
        
        for sent in sentences:
            sent_lower = sent.lower()
            if any(re.search(p, sent_lower) for p in skip_patterns):
                continue
            if len(sent.split()) >= 5:  # At least 5 words
                filtered.append(sent)
        
        # Take first few informative sentences
        result = []
        current_length = 0
        
        for sent in filtered[:5]:  # Max 5 sentences
            if current_length + len(sent) > max_length:
                break
            result.append(sent)
            current_length += len(sent)
        
        if not result:
            # Fallback: take first paragraph
            paragraphs = text.split('\n\n')
            for para in paragraphs:
                if len(para.strip()) > 50:
                    return para.strip()[:max_length]
        
        return '. '.join(result) + '.'
    
    def enhance_abstract(self, existing_abstract: str, full_text: str) -> str:
        """
        Enhance or expand an existing abstract using Gemini
        
        Args:
            existing_abstract: Current abstract (may be incomplete)
            full_text: Full document text
            
        Returns:
            Enhanced abstract
        """
        if not existing_abstract or len(existing_abstract.strip()) < 50:
            return self.generate(full_text)
        
        # If existing abstract is good enough, return it
        if len(existing_abstract) >= 200:
            return existing_abstract
        
        # Use Gemini to enhance if available
        if self.method == 'gemini' and self.model:
            try:
                prompt = f"""The following is an incomplete or brief abstract for a document:

{existing_abstract}

Full document text:
{full_text[:5000]}

Please enhance this abstract to make it more comprehensive and informative (300-400 characters), while preserving the key information."""
                
                response = self.model.generate_content(prompt)
                enhanced = response.text.strip()
                print(f"[AbstractGenerator] Enhanced abstract using Gemini")
                return enhanced
            except Exception as e:
                print(f"[AbstractGenerator] Enhancement failed: {e}, generating fresh abstract")
        
        # Otherwise, generate fresh one
        return self.generate(full_text)