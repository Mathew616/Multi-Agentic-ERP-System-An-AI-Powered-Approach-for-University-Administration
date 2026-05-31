# labelstudio_json_to_trainable_data.py
"""
Convert Label Studio JSON export to training data for NER and Categorizer

This script processes your Label Studio annotations and creates:
1. NER training data (tokens + BIO tags)
2. Categorizer training data (text + category labels + doc_type)

Updated for unified pipeline where doc_type is treated as a regular entity.
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Any
import re
import sys

# -------------------------
# Configuration / mappings
# -------------------------
# Focused NER labels (ABSTRACT removed - handled separately)
LABEL_TO_ID = {
    'O': 0,
    'B-EVENT_NAME': 1, 'I-EVENT_NAME': 2,
    'B-DATE': 3, 'I-DATE': 4,
    'B-VENUE': 5, 'I-VENUE': 6,
    'B-ORGANIZER': 7, 'I-ORGANIZER': 8,
    'B-DEPARTMENT': 9, 'I-DEPARTMENT': 10,
    'B-CATEGORY': 11, 'I-CATEGORY': 12,
    'B-DOC_TYPE': 13, 'I-DOC_TYPE': 14
}

# Comprehensive category mapping (from Label Studio labels to standardized categories)
CATEGORY_MAPPING = {
    # Direct matches
    'Workshop': 'Workshop / Hands-on / Training',
    'Seminar': 'Seminar',
    'Guest Lecture': 'Guest Lecture / Expert Talk',
    'Expert Talk': 'Guest Lecture / Expert Talk',
    'Conference': 'Conference / Symposium',
    'Symposium': 'Conference / Symposium',
    'Competition': 'Competition / Hackathon / Quiz',
    'Hackathon': 'Competition / Hackathon / Quiz',
    'Quiz': 'Competition / Hackathon / Quiz',
    'HackFest': 'Competition / Hackathon / Quiz',
    'Challenge': 'Competition / Hackathon / Quiz',
    'Orientation': 'Orientation / Induction / Welcome',
    'Induction': 'Orientation / Induction / Welcome',
    'Welcome': 'Orientation / Induction / Welcome',
    'Research': 'Research / Report / Paper Presentation',
    'Paper Presentation': 'Research / Report / Paper Presentation',
    'Presentation': 'Research / Report / Paper Presentation',
    
    # Partial/fuzzy matches
    'APPRECIATION': 'General / Department Activity',
    'PARTICIPATION': 'General / Department Activity',
    'Activity': 'General / Department Activity',
    'Activity Day': 'General / Department Activity',
    'Department Activity': 'General / Department Activity',
    'Masterclass': 'Workshop / Hands-on / Training',
    'Talk': 'Guest Lecture / Expert Talk',
    'Lecture': 'Guest Lecture / Expert Talk',
}

EVENT_CATEGORIES_TO_ID = {
    'Workshop / Hands-on / Training': 0,
    'Seminar': 1,
    'Guest Lecture / Expert Talk': 2,
    'Conference / Symposium': 3,
    'Competition / Hackathon / Quiz': 4,
    'Orientation / Induction / Welcome': 5,
    'Research / Report / Paper Presentation': 6,
    'General / Department Activity': 7
}

# A mapping to normalize Label Studio label names into standardized entity keys
LABEL_KEY_MAP = {
    'EVENT_NAME': 'EVENT_NAME',
    'EVENT': 'EVENT_NAME',
    'EVENT NAME': 'EVENT_NAME',
    'EVENTNAME': 'EVENT_NAME',
    
    'DATE': 'DATE',
    
    'VENUE': 'VENUE',
    
    'ORGANIZER': 'ORGANIZER',
    'ORGANIZER_NAME': 'ORGANIZER',
    'ORGANISER': 'ORGANIZER',
    
    'DEPARTMENT': 'DEPARTMENT',
    'DEPT': 'DEPARTMENT',
    
    'CATEGORY': 'CATEGORY',
    
    'DOCUMENT_TYPE': 'DOC_TYPE',
    'DOCUMENTTYPE': 'DOC_TYPE',
    'DOC_TYPE': 'DOC_TYPE',
    'DOC TYPE': 'DOC_TYPE',
    'DOCTYPE': 'DOC_TYPE',
    'DOCUMENT TYPE': 'DOC_TYPE',
}


# -------------------------
# Helper Functions
# -------------------------
def _fuzzy_match_category(text: str) -> str:
    """
    Fuzzy match category text to standardized category names.
    Handles various spellings and partial matches.
    """
    text_lower = text.lower().strip()
    
    # Direct mapping lookup (case-insensitive)
    for key, value in CATEGORY_MAPPING.items():
        if key.lower() == text_lower:
            return value
    
    # Partial match with keywords
    if 'workshop' in text_lower or 'hands' in text_lower or 'training' in text_lower:
        return 'Workshop / Hands-on / Training'
    if 'seminar' in text_lower:
        return 'Seminar'
    if 'lecture' in text_lower or 'talk' in text_lower or 'expert' in text_lower:
        return 'Guest Lecture / Expert Talk'
    if 'conference' in text_lower or 'symposium' in text_lower or 'summit' in text_lower:
        return 'Conference / Symposium'
    if 'competition' in text_lower or 'hackathon' in text_lower or 'quiz' in text_lower or 'challenge' in text_lower or 'fest' in text_lower:
        return 'Competition / Hackathon / Quiz'
    if 'orientation' in text_lower or 'induction' in text_lower or 'welcome' in text_lower or 'fresher' in text_lower:
        return 'Orientation / Induction / Welcome'
    if 'research' in text_lower or 'paper' in text_lower or 'presentation' in text_lower:
        return 'Research / Report / Paper Presentation'
    if 'appreciation' in text_lower or 'participation' in text_lower or 'activity' in text_lower:
        return 'General / Department Activity'
    
    # Default fallback
    return 'General / Department Activity'


# -------------------------
# Tokenization helper
# -------------------------
def tokenize_text(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    """
    Tokenize text and return tokens with character positions

    Returns:
        tokens: List of token strings
        token_positions: List of (start, end) character positions
    """
    tokens: List[str] = []
    token_positions: List[Tuple[int, int]] = []

    # Use a simple regex tokenization: words or standalone non-space chars
    pattern = r'\b\w+\b|\S'
    for m in re.finditer(pattern, text):
        tok = m.group()
        if tok:
            tokens.append(tok)
            token_positions.append((m.start(), m.end()))

    return tokens, token_positions


# -------------------------
# BIO tag conversion
# -------------------------
def _normalize_ls_label(ls_label: str) -> str:
    """Normalize Label Studio label to uppercase underscore form."""
    return ls_label.strip().upper().replace('-', ' ').replace('/', ' ').replace('  ', ' ').strip().replace(' ', '_')


def get_bio_tags(
    tokens: List[str],
    token_positions: List[Tuple[int, int]],
    annotations: List[Dict[str, Any]]
) -> List[int]:
    """
    Convert Label Studio annotations to BIO tags

    Args:
        tokens: List of token strings
        token_positions: List of (start, end) character positions
        annotations: Label Studio annotation results

    Returns:
        List of label IDs for each token (length == len(tokens))
    """
    ner_tags = [LABEL_TO_ID['O']] * len(tokens)

    for ann in annotations:
        # Typical Label Studio span item looks like:
        # { "id":..., "type":"labels", "value": {"start": X, "end": Y, "text": "...", "labels": ["Event Name"]}, ...}
        if ann.get('type') != 'labels':
            # Skip non-span results (choices or other controls may exist)
            continue

        value = ann.get('value', {})
        if not value:
            continue

        start_char = value.get('start')
        end_char = value.get('end')
        if start_char is None or end_char is None:
            continue

        labels = value.get('labels') or []
        if not labels:
            continue

        raw_label = labels[0]
        if not raw_label:
            continue

        norm = _normalize_ls_label(raw_label)  # e.g., "DOCUMENT_TYPE" or "EVENT_NAME"
        mapped_key = LABEL_KEY_MAP.get(norm, norm)  # fallback to normalized token

        # Map to BIO tag keys
        bio_base = mapped_key

        # Mark tokens that fall entirely inside the annotated span
        is_first = True
        for i, (tok_start, tok_end) in enumerate(token_positions):
            # If token lies within annotation span (inclusive)
            if tok_start >= start_char and tok_end <= end_char:
                prefix = 'B' if is_first else 'I'
                bio_label = f"{prefix}-{bio_base}"
                if bio_label in LABEL_TO_ID:
                    ner_tags[i] = LABEL_TO_ID[bio_label]
                    is_first = False
                else:
                    # Unknown label mapping => warn once
                    print(f"⚠️  Unknown BIO label: {bio_label} (from Label Studio label='{raw_label}')")
    return ner_tags


# -------------------------
# Category & doc type extraction
# -------------------------
def extract_category_and_doctype(annotations: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Extract category and document type from Label Studio annotations.
    Uses intelligent fuzzy matching for both category and doc_type.

    Returns:
        (category_name, doc_type) where doc_type is 'Certificate' or 'Report' (default 'Report')
    """
    category = None
    doc_type = None  # Will be determined by heuristics if not explicitly labeled
    
    # First pass: look for explicit labels
    for ann in annotations:
        if ann.get('type') != 'labels':
            continue
        value = ann.get('value', {})
        labels = value.get('labels') or []
        if not labels:
            continue
        raw_label = labels[0]
        raw_text = (value.get('text') or "").strip()

        # Category label
        norm_label = raw_label.strip().lower().replace('_', ' ')
        if norm_label in ('category',):
            # Use fuzzy matching on the annotated text
            category = _fuzzy_match_category(raw_text)
            continue

        # Document Type label
        if norm_label in ('document type', 'document_type', 'doc type', 'doctype', 'doc_type'):
            txt = raw_text.lower()
            if 'cert' in txt:
                doc_type = 'Certificate'
            elif 'report' in txt:
                doc_type = 'Report'
            else:
                # Fallback: title-case the text
                doc_type = raw_text.title() if raw_text else 'Report'
            continue
    
    # Second pass: infer doc_type from content if not explicitly labeled
    if doc_type is None:
        # Check for certificate keywords in ANY annotation text
        all_text = []
        for ann in annotations:
            if ann.get('type') == 'labels':
                value = ann.get('value', {})
                txt = (value.get('text') or "").lower()
                all_text.append(txt)
        
        combined_text = ' '.join(all_text).lower()
        
        # Certificate indicators
        cert_keywords = ['certificate', 'appreciation', 'participation', 'awarded', 'recognition', 'presented to']
        report_keywords = ['report', 'foss', 'submitted', 'supervision', 'overview', 'event list']
        
        cert_score = sum(1 for kw in cert_keywords if kw in combined_text)
        report_score = sum(1 for kw in report_keywords if kw in combined_text)
        
        if cert_score > report_score:
            doc_type = 'Certificate'
        else:
            doc_type = 'Report'  # Default to Report
    
    # Ensure category has a value
    if not category:
        # Try to infer from doc_type
        if doc_type == 'Certificate':
            category = 'General / Department Activity'
        else:
            category = 'General / Department Activity'
    
    return category, doc_type


# -------------------------
# Main conversion function
# -------------------------
def convert_labelstudio_to_training(
    labelstudio_json_path: str,
    output_dir: str = 'training_data'
):
    print("=" * 70)
    print("Converting Label Studio Data to Training Format")
    print("=" * 70)

    # Load Label Studio data
    with open(labelstudio_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n✅ Loaded {len(data)} annotated documents")

    # Prepare output
    ner_training_data: List[Dict[str, Any]] = []

    skipped = 0
    processed = 0

    for item in data:
        # Text content is often under item['data']['content']
        text = ""
        if isinstance(item.get('data'), dict):
            text = item['data'].get('content') or item['data'].get('text') or item['data'].get('ocr_text') or ""
        else:
            text = item.get('content') or ""

        if not text or len(text.strip()) < 20:
            skipped += 1
            continue

        # Get annotations
        annotations_list = item.get('annotations') or []
        if not annotations_list:
            annotations_list = item.get('predictions') or item.get('results') or []

        if not annotations_list:
            skipped += 1
            continue

        # Get first annotation entry
        ann_entry = annotations_list[0] if isinstance(annotations_list, list) else annotations_list
        annotations = ann_entry.get('result') or ann_entry.get('annotations') or []

        if not annotations:
            skipped += 1
            continue

        # Tokenize
        tokens, token_positions = tokenize_text(text)

        if len(tokens) > 512:
            print(f"⚠️  Truncating document with {len(tokens)} tokens to 512")
            tokens = tokens[:512]
            token_positions = token_positions[:512]

        # BIO tags
        ner_tags = get_bio_tags(tokens, token_positions, annotations)

        # Extract category and doc_type for metadata/statistics only
        category_name, doc_type = extract_category_and_doctype(annotations)

        ner_training_data.append({
            'tokens': tokens,
            'ner_tags': ner_tags,
            'metadata': {
                'category': category_name,
                'doc_type': doc_type
            }
        })

        processed += 1

    print(f"\n✅ Processed {processed} documents")
    print(f"⚠️  Skipped {skipped} documents (empty or no annotations)")

    # -------------------------
    # Dataset statistics
    # -------------------------
    print("\n" + "=" * 70)
    print("Dataset Statistics")
    print("=" * 70)

    # NER stats
    total_tokens = sum(len(x['tokens']) for x in ner_training_data) if ner_training_data else 0
    label_counts: Dict[str, int] = {}
    for it in ner_training_data:
        for tag in it['ner_tags']:
            label_name = next((k for k, v in LABEL_TO_ID.items() if v == tag), f'UNK_{tag}')
            label_counts[label_name] = label_counts.get(label_name, 0) + 1

    print(f"\n📊 NER Dataset:")
    print(f"   - Examples: {len(ner_training_data)}")
    print(f"   - Total tokens: {total_tokens}")
    if ner_training_data:
        print(f"   - Avg tokens per example: {(total_tokens / len(ner_training_data)):.1f}")
    else:
        print(f"   - Avg tokens per example: 0")

    print(f"\n   Entity distribution:")
    non_o_labels = [(label, count) for label, count in label_counts.items() if label != 'O']
    if non_o_labels:
        for label, count in sorted(non_o_labels, key=lambda x: x[1], reverse=True):
            print(f"      {label}: {count}")
    else:
        print(f"      (No entities found)")
    
    # Show O tag count separately
    if 'O' in label_counts:
        print(f"\n   Non-entity tokens (O): {label_counts['O']}")

    # Category and doc_type statistics (from metadata)
    cat_counts: Dict[str, int] = {}
    doc_type_counts: Dict[str, int] = {}
    for it in ner_training_data:
        meta = it.get('metadata', {})
        cat = meta.get('category', 'Unknown')
        dt = meta.get('doc_type', 'Unknown')
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1

    print(f"\n📊 Document Metadata:")
    print(f"\n   Category distribution:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {cat}: {cnt}")
    print(f"\n   Document type distribution:")
    for dt, cnt in doc_type_counts.items():
        print(f"      {dt}: {cnt}")

    # -------------------------
    # Save output
    # -------------------------
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ner_path = output_path / 'ner_training_data.json'
    with ner_path.open('w', encoding='utf-8') as fo:
        json.dump(ner_training_data, fo, indent=2, ensure_ascii=False)
    print(f"\n✅ Training data saved to: {ner_path}")
    print(f"   Format: List of {{tokens, ner_tags, metadata}}")

    # -------------------------
    # Recommendations
    # -------------------------
    print("\n" + "=" * 70)
    print("💡 Recommendations")
    print("=" * 70)
    
    recommendations = []
    
    if len(ner_training_data) < 100:
        recommendations.append("⚠️  Small dataset (<100 examples). Consider adding more labeled documents.")
    
    # Check entity balance
    if non_o_labels:
        entity_counts = [count for _, count in non_o_labels]
        if max(entity_counts) > min(entity_counts) * 10:
            recommendations.append("⚠️  Imbalanced entity distribution. Some entities are much more common than others.")
    
    # Check category balance
    cat_list = list(cat_counts.values())
    if cat_list and max(cat_list) > min(cat_list) * 5:
        recommendations.append("⚠️  Imbalanced category distribution. Consider labeling more examples of rare categories.")
    
    # Check doc_type balance
    doc_list = list(doc_type_counts.values())
    if len(doc_list) == 2 and max(doc_list) > min(doc_list) * 3:
        recommendations.append("⚠️  Imbalanced document types. Try to balance Certificate and Report examples.")
    
    if recommendations:
        for rec in recommendations:
            print(f"\n{rec}")
    else:
        print("\n✅ Dataset looks well-balanced! Ready for training.")
    
    print(f"\n{'=' * 70}")
    print("Next Steps:")
    print("=" * 70)
    print("1. Review the statistics above")
    print("2. Train the NER model: python train_ner_model.py")
    print("3. Test the model: python test_ner_agent.py")
    print(f"{'=' * 70}")

    print("\n✅ Conversion Complete!")


# -------------------------
# CLI entrypoint
# -------------------------
if __name__ == "__main__":
    # Default input
    inp = 'project-2-at-2025-12-08-22-51-95d10e80.json'
    outdir = 'training_data'

    # Accept input filename as first arg and output dir as second
    if len(sys.argv) >= 2:
        inp = sys.argv[1]
    if len(sys.argv) >= 3:
        outdir = sys.argv[2]

    # Validate input file exists
    inp_path = Path(inp)
    if not inp_path.exists():
        print(f"❌ ERROR: Input file not found: {inp}")
        print("Usage: python labelstudio_json_to_trainable_data.py <input_json> [output_dir]")
        sys.exit(2)

    convert_labelstudio_to_training(labelstudio_json_path=str(inp_path), output_dir=outdir)