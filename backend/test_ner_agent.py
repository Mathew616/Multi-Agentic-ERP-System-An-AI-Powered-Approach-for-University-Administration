"""
test_ner_agent.py

Comprehensive testing suite for the enhanced NER Agent.
Tests both entity extraction and document categorization capabilities.

Usage:
    # Test with default models
    python test_ner_agent.py
    
    # Test with custom model paths
    python test_ner_agent.py --ner-model backend/ml_models/ner_model \
                             --cat-model backend/ml_models/category_model
    
    # Test specific document types
    python test_ner_agent.py --test-certificates
    python test_ner_agent.py --test-reports
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from agents.ner_agent import NerAgent


# -------------------------
# Test Data
# -------------------------
TEST_CERTIFICATE = """
Dr. Jayavrinda Vrindavanam
Professor & Chairperson DEPARTMENT OF CSE(AI & ML) SOE, DSU

Dr. Udaya Kumar Reddy K.R.
Dean SCHOOL OF ENGINEERING DSU

CERTIFICATE OF APPRECIATION

THIS CERTIFICATE IS PRESENTED TO

is recognized as the Best Class Representative (CR) of the batch 2021–2025. 
This recognition is awarded in appreciation of her exemplary leadership, 
effective communication, and unwavering dedication to representing the interests of the class.

DAYANANDA SAGAR UNIVERSITY
Deverakaggalahalli, Harohalli, Kanakapura Rd, Dist. Ramanagara, Karnataka-562112

DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING
(ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING)

SHRUSTI VEERABASAYYA GOUDAR
"""

TEST_REPORT = """
Bachelor of Technology in
COMPUTER SCIENCE AND ENGINEERING (ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING)

22AM2407 - SKILL ENHANCEMENT COURSE - II
(UNIX AND SHELL SCRIPTING)

FOSS REPORT

On
LaTex Fundamentals: Crafting Research Articles

7th April 2025 to 9th April 2025

DR. RAJESH T.M
Associate Professor CSE, DSU

DR. GIRISHA G.S
Professor & Chairperson Dept. of CSE, DSU

Submitted By
Arshanapally NVS Srikanth (ENG22AM0168)

UNDER THE SUPERVISION
Dr. Kousalya Govardhanan
Professor
Dept. Of CSE(AIML)

DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING (AIML)
SCHOOL OF ENGINEERING
DAYANANDA SAGAR UNIVERSITY

Workshop Overview:
This three-day workshop focused on teaching students the fundamentals of LaTeX 
for academic writing. Participants learned to create research articles, format 
bibliographies, insert figures and tables, and structure complex mathematical equations.

The workshop included hands-on sessions where students created their own research 
article templates and practiced collaborative writing using Overleaf.
"""

TEST_HACKATHON_REPORT = """
Bachelor of Technology in
COMPUTER SCIENCE AND ENGINEERING (DATA SCIENCE)

FOSS REPORT

On
Data Science HackFest

1 OCT 2025

Innovation Lab – Block B

Submitted By
Suresh Verma (ENG23DS0133)

UNDER THE SUPERVISION
Dr. Kousalya Govardhanan
Professor
Dept. Of CSE(AIML)

DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING (Data Science)
SCHOOL OF ENGINEERING
DAYANANDA SAGAR UNIVERSITY

Event Overview:
The Data Science HackFest was a competitive coding event where students worked 
in teams to solve real-world data science challenges. Teams analyzed datasets, 
built machine learning models, and presented their findings to a panel of judges.

Organizer: Team Data Warriors

The event attracted over 50 participants from various departments and featured 
mentorship from industry experts in data science and machine learning.
"""


# -------------------------
# Test Functions
# -------------------------
def print_separator(title: str = ""):
    """Print a visual separator"""
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}\n")
    else:
        print(f"{'─' * 70}")


def print_field(label: str, value: str, color: str = ""):
    """Print a field with formatting"""
    colors = {
        'green': '\033[92m',
        'blue': '\033[94m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'end': '\033[0m'
    }
    
    color_code = colors.get(color, '')
    end_code = colors['end'] if color else ''
    
    print(f"{color_code}  {label:15}: {value}{end_code}")


def test_prediction(agent: NerAgent, text: str, expected_type: str = None):
    """Test prediction on a single document"""
    print_separator(f"Testing {expected_type or 'Document'}")
    
    # Preview text
    preview = text[:200].replace('\n', ' ').strip()
    print(f"  Text Preview: {preview}...")
    print()
    
    # Run prediction
    print("  ðŸ„ Running prediction...")
    try:
        result = agent.predict(text)
        
        # Display results
        print_separator()
        print_field("Document Type", result.get('doc_type', 'Unknown'), 'blue')
        print_field("Category", result.get('category', 'Unknown'), 'green')
        print_field("Confidence", f"{result.get('confidence', 0):.2%}", 'yellow')
        print()
        
        print_field("Event Name", result.get('event_name', 'Not extracted'))
        print_field("Date", result.get('date', 'Not extracted'))
        print_field("Department", result.get('department', 'Not extracted'))
        print_field("Venue", result.get('venue', 'Not extracted'))
        print_field("Organizer", result.get('organizer', 'Not extracted'))
        
        # Show abstract for reports
        if result.get('doc_type') == 'Report' and result.get('abstract'):
            abstract = result['abstract'][:150] + "..." if len(result['abstract']) > 150 else result['abstract']
            print()
            print_field("Abstract", abstract)
        
        # Show extracted entities
        entities = result.get('entities', [])
        if entities:
            print(f"\n  ðŸ·ï¸  Extracted Entities ({len(entities)}):")
            entity_types = {}
            for ent in entities:
                ent_type = ent.get('entity_type', 'Unknown')
                entity_types[ent_type] = entity_types.get(ent_type, 0) + 1
            
            for ent_type, count in sorted(entity_types.items()):
                print(f"     - {ent_type}: {count}")
        
        # Validation
        print()
        if expected_type:
            if result.get('doc_type') == expected_type:
                print_field("âœ… Validation", f"Document type correctly identified as {expected_type}", 'green')
            else:
                print_field("âŒ Validation", f"Expected {expected_type}, got {result.get('doc_type')}", 'red')
        
        return result
        
    except Exception as e:
        print_field("âŒ Error", str(e), 'red')
        import traceback
        traceback.print_exc()
        return None


def run_comprehensive_tests(agent: NerAgent):
    """Run comprehensive test suite"""
    print_separator("NER Agent Comprehensive Test Suite")
    
    results = []
    
    # Test 1: Certificate
    print("\nðŸœ Test 1: Certificate Document")
    print("─" * 70)
    result1 = test_prediction(agent, TEST_CERTIFICATE, "Certificate")
    results.append(('Certificate', result1))
    
    # Test 2: Workshop Report
    print("\nðŸ„ Test 2: Workshop Report")
    print("─" * 70)
    result2 = test_prediction(agent, TEST_REPORT, "Report")
    results.append(('Workshop Report', result2))
    
    # Test 3: Hackathon Report
    print("\nðŸ† Test 3: Hackathon Report")
    print("─" * 70)
    result3 = test_prediction(agent, TEST_HACKATHON_REPORT, "Report")
    results.append(('Hackathon Report', result3))
    
    # Summary
    print_separator("Test Summary")
    
    success_count = sum(1 for _, r in results if r is not None)
    total_count = len(results)
    
    print(f"  Tests Run: {total_count}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {total_count - success_count}")
    print()
    
    # Detailed summary
    print("  Results by Test:")
    for name, result in results:
        if result:
            doc_type = result.get('doc_type', 'Unknown')
            category = result.get('category', 'Unknown')
            confidence = result.get('confidence', 0)
            print(f"    âœ… {name}: {doc_type} | {category} | {confidence:.2%}")
        else:
            print(f"    âŒ {name}: Failed")
    
    print()
    
    # Check for required fields
    print("  Field Extraction Rate:")
    field_stats = {
        'event_name': 0,
        'date': 0,
        'department': 0,
        'venue': 0,
        'organizer': 0
    }
    
    for _, result in results:
        if result:
            for field in field_stats:
                if result.get(field) and result.get(field) != 'Not extracted':
                    field_stats[field] += 1
    
    for field, count in field_stats.items():
        rate = (count / total_count) * 100
        color = 'green' if rate >= 66 else 'yellow' if rate >= 33 else 'red'
        print_field(field.replace('_', ' ').title(), f"{count}/{total_count} ({rate:.0f}%)", color)


def test_edge_cases(agent: NerAgent):
    """Test edge cases and error handling"""
    print_separator("Edge Case Testing")
    
    # Empty text
    print("  Test: Empty text")
    result = agent.predict("")
    print(f"    Result: {result.get('doc_type', 'No result')}")
    print()
    
    # Very short text
    print("  Test: Very short text")
    result = agent.predict("Hello World")
    print(f"    Result: {result.get('doc_type', 'No result')}")
    print()
    
    # Only whitespace
    print("  Test: Only whitespace")
    result = agent.predict("   \n   \t   ")
    print(f"    Result: {result.get('doc_type', 'No result')}")
    print()
    
    # Special characters
    print("  Test: Special characters")
    result = agent.predict("!@#$%^&*()")
    print(f"    Result: {result.get('doc_type', 'No result')}")
    print()


def test_model_info(agent: NerAgent):
    """Display model information"""
    print_separator("Model Information")
    
    # NER Model
    if agent.ner_model:
        print("  NER Model:")
        print(f"    Config: {agent.ner_model.config.model_type}")
        print(f"    Labels: {len(agent.ner_model.config.id2label)}")
        print()
    
    # Categorizer
    if agent.categorizer:
        print("  Categorizer:")
        print(f"    Config: {agent.cat_model.config.model_type}")
        print(f"    Classes: {agent.cat_model.config.num_labels}")
        print()
    else:
        print("  Categorizer: Using heuristics (no model loaded)")
        print()


# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description='Test NER Agent')
    parser.add_argument('--ner-model', type=str, default=None,
                       help='Path to NER model directory')
    parser.add_argument('--cat-model', type=str, default=None,
                       help='Path to categorizer model directory')
    parser.add_argument('--test-certificates', action='store_true',
                       help='Test only certificate documents')
    parser.add_argument('--test-reports', action='store_true',
                       help='Test only report documents')
    parser.add_argument('--test-edge-cases', action='store_true',
                       help='Test edge cases')
    parser.add_argument('--model-info', action='store_true',
                       help='Display model information')
    
    args = parser.parse_args()
    
    # Initialize agent
    print_separator("Initializing NER Agent")
    
    try:
        if args.ner_model and args.cat_model:
            print(f"  NER Model: {args.ner_model}")
            print(f"  Cat Model: {args.cat_model}")
            agent = NerAgent(
                ner_model_dir=args.ner_model,
                cat_model_dir=args.cat_model
            )
        else:
            print("  Using default models")
            agent = NerAgent()
        
        print("  âœ… Agent initialized successfully")
    except Exception as e:
        print(f"  âŒ Failed to initialize agent: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Run tests based on arguments
    if args.model_info:
        test_model_info(agent)
    
    if args.test_edge_cases:
        test_edge_cases(agent)
    
    if args.test_certificates:
        test_prediction(agent, TEST_CERTIFICATE, "Certificate")
    elif args.test_reports:
        test_prediction(agent, TEST_REPORT, "Report")
        test_prediction(agent, TEST_HACKATHON_REPORT, "Report")
    else:
        # Run comprehensive tests by default
        run_comprehensive_tests(agent)
    
    print_separator("Testing Complete")


if __name__ == '__main__':
    main()
