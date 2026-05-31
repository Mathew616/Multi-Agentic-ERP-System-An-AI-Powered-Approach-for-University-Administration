"""
ocr_agent.py

OCR Agent using docTR (Document Text Recognition) as the primary OCR engine
with EasyOCR as a fallback. Includes OpenCV-based image preprocessing for
scanned/noisy documents and SymSpell-based spelling correction.

docTR uses a two-stage transformer pipeline:
  1. DBNet text detection  → locates text regions in the image
  2. CRNN/ViTSTR text recognition → reads characters from each detected region

Key improvements over the previous EasyOCR-only implementation:
  - Higher accuracy on dense text and complex layouts
  - GPU-accelerated inference via PyTorch backend
  - Better handling of multi-line paragraphs and tabular content
  - Safer character-level cleanup (context-aware, not blanket replacement)
"""

import os
import gc
import fitz
import tempfile
import cv2
import numpy as np
import re

from symspellpy import SymSpell


# ── docTR imports ────────────────────────────────────────────────────────────
try:
    from doctr.models import ocr_predictor
    from doctr.io import DocumentFile
    DOCTR_AVAILABLE = True
except ImportError:
    DOCTR_AVAILABLE = False

# ── EasyOCR fallback ────────────────────────────────────────────────────────
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


class OcrAgent:
    def __init__(self):
        # ── Primary engine: docTR ────────────────────────────────────────
        self.doctr_model = None
        if DOCTR_AVAILABLE:
            print("[OCR Agent] Initializing docTR (DBNet + CRNN)...")
            try:
                import torch
                gpu_available = torch.cuda.is_available()
                if gpu_available:
                    gpu_name = torch.cuda.get_device_name(0)
                    gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    print(f"[OCR Agent] 🖥️  GPU detected: {gpu_name} ({gpu_mem:.1f} GB)")
                else:
                    print("[OCR Agent] ℹ No CUDA GPU detected — using CPU "
                          "(install PyTorch with CUDA for GPU acceleration)")

                self.doctr_model = ocr_predictor(
                    det_arch='db_resnet50',
                    reco_arch='crnn_vgg16_bn',
                    pretrained=True,
                )
                # Move to GPU if available
                if gpu_available:
                    self.doctr_model = self.doctr_model.cuda()
                    print("[OCR Agent] ✅ docTR initialized (GPU)")
                else:
                    print("[OCR Agent] ✅ docTR initialized (CPU)")
            except Exception as e:
                print(f"[OCR Agent] ⚠ docTR init failed: {str(e)[:200]}")
                self.doctr_model = None
        else:
            print("[OCR Agent] ⚠ docTR not installed — will use EasyOCR fallback")

        # ── Fallback engine: EasyOCR ────────────────────────────────────
        self.easyocr_reader = None
        if EASYOCR_AVAILABLE:
            if self.doctr_model is None:
                # Only load EasyOCR if docTR is unavailable
                print("[OCR Agent] Initializing EasyOCR (fallback)...")
                try:
                    self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
                    print("[OCR Agent] ✅ EasyOCR initialized")
                except Exception as e:
                    print(f"[OCR Agent] ❌ EasyOCR failed: {str(e)[:200]}")
            else:
                # Lazy-load EasyOCR only when needed
                print("[OCR Agent] EasyOCR available as fallback (lazy-loaded)")

        # ── SymSpell for spelling correction ────────────────────────────
        print("[OCR Agent] Initializing SymSpell...")
        self.symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)

        dictionary_path = "frequency_dictionary_en_82_765.txt"
        if os.path.exists(dictionary_path):
            self.symspell.load_dictionary(dictionary_path, 0, 1)
            print("[OCR Agent] ✅ SymSpell loaded")
        else:
            print("[OCR Agent] ⚠ SymSpell dictionary not found")
            self.symspell = None

    # =====================================================================
    # Public Method
    # =====================================================================
    def extract_text(self, file_path):
        """Extract text from a PDF, PNG, JPG, JPEG, or TIFF document."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".png", ".jpg", ".jpeg", ".tiff"):
            return self._extract_from_image(file_path)
        elif ext == ".pdf":
            return self._extract_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # =====================================================================
    # Image OCR
    # =====================================================================
    def _extract_from_image(self, image_path):
        """OCR a single image file using docTR (primary) or EasyOCR (fallback)."""
        print(f"[OCR Agent] Processing image: {os.path.basename(image_path)}")

        # Preprocess the image for better OCR
        processed_img = self._preprocess_image(image_path)

        raw_text = ""

        # ── Try docTR first ──────────────────────────────────────────────
        if self.doctr_model is not None:
            try:
                raw_text = self._ocr_with_doctr(image_path, processed_img)
            except Exception as e:
                print(f"[OCR Agent] docTR failed: {str(e)[:150]}, falling back to EasyOCR")
                raw_text = ""

        # ── Fallback to EasyOCR ──────────────────────────────────────────
        if not raw_text.strip():
            raw_text = self._ocr_with_easyocr(processed_img)

        # ── Apply safe normalization ─────────────────────────────────────
        text = self._normalize_ocr_text(raw_text)
        title = self._extract_title_from_text(text)

        return {
            "text": text.strip(),
            "title": title,
            "source": "image"
        }

    def _ocr_with_doctr(self, image_path, processed_img=None):
        """Run docTR OCR on an image and return the extracted text."""
        # docTR works best with the original (non-binarized) image
        doc = DocumentFile.from_images(image_path)
        result = self.doctr_model(doc)

        # Extract text preserving reading order
        lines = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    words = [word.value for word in line.words]
                    lines.append(" ".join(words))
                # Add paragraph break between blocks
                lines.append("")

        text = "\n".join(lines)
        print(f"[OCR Agent] docTR extracted {len(text)} chars")
        return text

    def _ocr_with_easyocr(self, processed_img):
        """Fallback: run EasyOCR on a preprocessed image array."""
        if self.easyocr_reader is None:
            if EASYOCR_AVAILABLE:
                print("[OCR Agent] Lazy-loading EasyOCR fallback...")
                try:
                    self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
                except Exception as e:
                    print(f"[OCR Agent] ❌ EasyOCR init failed: {str(e)[:100]}")
                    return ""
            else:
                return ""

        if processed_img is None:
            return ""

        try:
            results = self.easyocr_reader.readtext(processed_img, detail=0)
            raw_text = "\n".join(results)
            print(f"[OCR Agent] EasyOCR extracted {len(raw_text)} chars")
            return raw_text
        except Exception as e:
            print(f"[OCR Agent] EasyOCR failed: {str(e)[:100]}")
            return ""

    # =====================================================================
    # PDF OCR
    # =====================================================================
    def _extract_from_pdf(self, file_path):
        """Extract text from a PDF: use embedded text layer if available,
        otherwise render pages to images and OCR them.

        Memory-safe approach:
          - Digital text pages (embedded text) are always processed (cheap).
          - Scanned / image-based pages are OCR'd up to MAX_OCR_PAGES to
            prevent OOM crashes on large PDFs.
          - Each page image is deleted immediately after OCR to free memory.
          - DPI is configurable (default 200, sufficient for most docs).
        """
        try:
            from config import Config
        except ImportError:
            from backend.config import Config
        max_ocr_pages = getattr(Config, 'MAX_OCR_PAGES', 8)
        ocr_dpi = getattr(Config, 'OCR_DPI', 200)

        results = []
        ocr_page_count = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf = fitz.open(file_path)
            total_pages = len(pdf)
            title = self._extract_title_from_pdf(pdf)

            print(f"[OCR Agent] PDF has {total_pages} page(s), "
                  f"max OCR pages = {max_ocr_pages}, DPI = {ocr_dpi}")

            for i, page in enumerate(pdf):
                # ── Try the embedded digital text layer first (very cheap) ──
                text = page.get_text("text")

                if text and len(text.strip()) > 30:
                    # Digital PDF — no spell correction needed
                    cleaned = self._normalize_digital_text(text.strip())
                    results.append(cleaned)
                    continue

                # ── Scanned / image-based page — needs OCR ──────────────
                if ocr_page_count >= max_ocr_pages:
                    print(f"[OCR Agent] ⚠ Skipping page {i+1}/{total_pages} "
                          f"(OCR page limit {max_ocr_pages} reached)")
                    continue

                ocr_page_count += 1
                print(f"[OCR Agent] 🔍 OCR page {i+1}/{total_pages} "
                      f"(OCR page {ocr_page_count}/{max_ocr_pages})")

                try:
                    pix = page.get_pixmap(dpi=ocr_dpi)
                    img_path = os.path.join(tmpdir, f"page_{i}.png")
                    pix.save(img_path)
                    # Free the pixmap immediately
                    del pix

                    image_result = self._extract_from_image(img_path)
                    results.append(image_result["text"])

                    # Delete the temp image to free disk/memory
                    try:
                        os.remove(img_path)
                    except OSError:
                        pass

                    # Force garbage collection after each OCR page
                    gc.collect()

                except Exception as e:
                    print(f"[OCR Agent] ❌ Failed to OCR page {i+1}: {str(e)[:150]}")
                    continue

            pdf.close()

        if ocr_page_count > 0 and ocr_page_count >= max_ocr_pages and total_pages > max_ocr_pages:
            print(f"[OCR Agent] ℹ Processed {ocr_page_count} OCR pages out of "
                  f"{total_pages} total. Increase MAX_OCR_PAGES to process more.")

        return {
            "text": "\n".join(results),
            "title": title,
            "source": "pdf"
        }

    # =====================================================================
    # Text Normalization
    # =====================================================================
    def _normalize_digital_text(self, text: str) -> str:
        """Normalize digitally extracted PDF text WITHOUT spell correction.
        Preserves newline structure for downstream regex-based extraction."""
        if not text:
            return text

        # Collapse horizontal whitespace (spaces/tabs) but PRESERVE newlines
        text = re.sub(r'[^\S\n]+', ' ', text)
        # Trim spaces around newlines
        text = re.sub(r' *\n *', '\n', text)
        # Collapse 3+ consecutive newlines to double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _normalize_ocr_text(self, text: str) -> str:
        """Normalize OCR-extracted text WITH safe cleanup and spell correction."""
        if not text:
            return text

        # Step 1: Context-aware character cleanup (safe — not blanket replacement)
        text = self._safe_character_cleanup(text)

        # Step 2: SymSpell spelling correction
        if self.symspell:
            text = self._apply_spelling_correction(text)

        # Step 3: Normalize spacing
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _safe_character_cleanup(self, text: str) -> str:
        """Context-aware character fixes — only applies substitutions where
        they are clearly OCR errors, rather than blanket replacement.

        OLD behaviour (BROKEN):
            re.sub(r"0", "O", text)   → replaced ALL zeros including dates/numbers
            re.sub(r"1", "I", text)   → replaced ALL ones including dates/numbers
            re.sub(r"ll", "li", text) → corrupted valid words like 'hall' → 'hali'

        NEW behaviour: regex lookaround ensures substitutions only fire in
        the correct character context.
        """

        # Fix '0' → 'O' ONLY when surrounded by letters (not in numbers)
        text = re.sub(r'(?<=[A-Za-z])0(?=[A-Za-z])', 'O', text)
        # Fix leading '0' before lowercase letters: "0rganizer" → "Organizer"
        text = re.sub(r'\b0(?=[a-z]{2,})', 'O', text)

        # Fix '1' → 'l' ONLY when surrounded by letters (not in numbers/dates)
        text = re.sub(r'(?<=[A-Za-z])1(?=[a-z])', 'l', text)
        # Fix leading '1' before lowercase: "1nnovation" → "Innovation"
        text = re.sub(r'\b1(?=[a-z]{2,})', 'I', text)

        # Fix '|' → 'I' when it appears adjacent to letters
        text = re.sub(r'\|(?=[A-Za-z])', 'I', text)
        text = re.sub(r'(?<=[A-Za-z])\|', 'I', text)

        # Fix 'O' → '0' ONLY inside what looks like a year/number
        text = re.sub(r'(?<=[0-9])O(?=[0-9])', '0', text)
        # Fix 'l' → '1' inside numbers
        text = re.sub(r'(?<=[0-9])l(?=[0-9])', '1', text)

        # Remove stray symbols that are clearly OCR noise
        text = re.sub(r'[~`^]', '', text)

        # Fix broken hyphenation across lines
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

        return text

    def _apply_spelling_correction(self, text: str) -> str:
        """Apply SymSpell spelling correction selectively."""
        corrected_words = []

        for word in text.split():
            # Skip ALL-CAPS words (likely names, departments, acronyms)
            if word.isupper() and len(word) > 2:
                corrected_words.append(word)
                continue

            # Skip numbers and dates
            if re.match(r'^[\d.,:/-]+$', word):
                corrected_words.append(word)
                continue

            # Skip words that look like entity identifiers
            if '_' in word or word.startswith(('B-', 'I-', 'O-')):
                corrected_words.append(word)
                continue

            # Skip very short words (likely correct)
            if len(word) <= 2:
                corrected_words.append(word)
                continue

            suggestions = self.symspell.lookup(
                word, verbosity=0, max_edit_distance=2
            )

            if suggestions:
                corrected_words.append(suggestions[0].term)
            else:
                corrected_words.append(word)

        return " ".join(corrected_words)

    # =====================================================================
    # Image Preprocessing (OpenCV)
    # =====================================================================
    def _preprocess_image(self, image_path):
        """Preprocess a scanned/noisy image for better OCR accuracy.

        Pipeline: Upscale → Grayscale → CLAHE → Denoise → Sharpen →
                  Adaptive Threshold → Morphological Close
        """
        img = cv2.imread(image_path)

        if img is None:
            return None

        # Upscale small images
        height, width = img.shape[:2]
        if width < 1000:
            scale = 1000 / width
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Non-local means denoising
        gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)

        # Sharpen
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]])
        gray = cv2.filter2D(gray, -1, kernel)

        # Adaptive Gaussian thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 2
        )

        # Morphological close to fill small gaps
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return thresh

    # =====================================================================
    # Title Detection
    # =====================================================================
    def _extract_title_from_text(self, text):
        """Extract the first meaningful line as the document title."""
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 5]
        if lines:
            return lines[0]
        return "Untitled"

    def _extract_title_from_pdf(self, pdf):
        """Extract title from PDF metadata or largest font on first page."""
        try:
            page = pdf[0]
            d = page.get_text("dict")
            best_text = ""
            best_size = 0
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["size"] > best_size:
                            best_size = span["size"]
                            best_text = span["text"]
            return best_text.strip() if best_text.strip() else "Untitled"
        except Exception:
            return "Untitled"
