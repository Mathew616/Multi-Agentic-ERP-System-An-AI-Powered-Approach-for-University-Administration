import os
import fitz
import tempfile
import cv2
import easyocr
import numpy as np
import re

from symspellpy import SymSpell


class OcrAgent:
    def __init__(self):
        print("[OCR Agent] Initializing EasyOCR...")

        try:
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("[OCR Agent] ✅ EasyOCR initialized")
        except Exception as e:
            print(f"[OCR Agent] ❌ EasyOCR failed: {str(e)[:200]}")
            self.reader = None

        # 🔥 Initialize SymSpell
        print("[OCR Agent] Initializing SymSpell...")
        self.symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)

        dictionary_path = "frequency_dictionary_en_82_765.txt"

        if os.path.exists(dictionary_path):
            self.symspell.load_dictionary(dictionary_path, 0, 1)
            print("[OCR Agent] ✅ SymSpell loaded")
        else:
            print("[OCR Agent] ⚠ SymSpell dictionary not found")
            self.symspell = None


    # ------------------------------------------------
    # 🔹 Public Method
    # ------------------------------------------------
    def extract_text(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
            return self._extract_from_image(file_path)

        elif file_path.lower().endswith(".pdf"):
            return self._extract_from_pdf(file_path)

        else:
            raise ValueError("Unsupported file type")


    # ------------------------------------------------
    # 🔹 Image OCR (EasyOCR)
    # ------------------------------------------------
    def _extract_from_image(self, image_path):
        print("[OCR Agent] Processing image with EasyOCR...")

        if not self.reader:
            return {"text": "", "title": "Untitled", "source": "image"}

        processed_img = self._preprocess_image(image_path)

        try:
            results = self.reader.readtext(processed_img, detail=0)
            raw_text = "\n".join(results)
        except Exception as e:
            print(f"[OCR Agent] EasyOCR failed: {str(e)[:100]}")
            raw_text = ""

        # 🔥 Apply normalization
        text = self._normalize_ocr_text(raw_text)

        title = self._extract_title_from_text(text)

        return {
            "text": text.strip(),
            "title": title,
            "source": "image"
        }


    # ------------------------------------------------
    # 🔹 PDF OCR
    # ------------------------------------------------
    def _extract_from_pdf(self, file_path):
        results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf = fitz.open(file_path)
            title = self._extract_title_from_pdf(pdf)

            for i, page in enumerate(pdf):
                text = page.get_text("text")

                # Digital PDF - NO spell correction needed
                if text and len(text.strip()) > 30:
                    cleaned = self._normalize_digital_text(text.strip())
                    results.append(cleaned)
                    continue

                # OCR fallback - WILL use spell correction
                pix = page.get_pixmap(dpi=200)
                img_path = os.path.join(tmpdir, f"page_{i}.png")
                pix.save(img_path)

                image_result = self._extract_from_image(img_path)
                results.append(image_result["text"])

        return {
            "text": "\n".join(results),
            "title": title,
            "source": "pdf"
        }


    # ------------------------------------------------
    # 🔹 OCR Text Normalization (SymSpell Powered)
    # ------------------------------------------------
    def _normalize_digital_text(self, text: str) -> str:
        """Normalize digitally extracted PDF text WITHOUT spell correction"""
        if not text:
            return text

        # Only basic cleanup - no spell correction
        text = re.sub(r"\s+", " ", text)  # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)  # Reduce excessive newlines
        
        return text.strip()


    def _normalize_ocr_text(self, text: str) -> str:
        """Normalize OCR-extracted text WITH spell correction (for images/scanned PDFs)"""
        if not text:
            return text

        text = self._character_cleanup(text)

        if not self.symspell:
            return text

        corrected_words = []

        for word in text.split():

            # 🔹 Skip ALL CAPS words (likely names/departments)
            if word.isupper() and len(word) > 3:
                corrected_words.append(word)
                continue

            # 🔹 Skip numbers
            if word.isdigit():
                corrected_words.append(word)
                continue

            suggestions = self.symspell.lookup(
                word,
                verbosity=0,
                max_edit_distance=2
            )

            if suggestions:
                corrected_words.append(suggestions[0].term)
            else:
                corrected_words.append(word)

        text = " ".join(corrected_words)

        # Normalize spacing
        text = re.sub(r"\s+", " ", text)

        return text.strip()


    # ------------------------------------------------
    # 🔹 Character-level OCR Cleanup
    # ------------------------------------------------
    def _character_cleanup(self, text: str) -> str:

        # Fix common OCR swaps
        text = re.sub(r"0", "O", text)
        text = re.sub(r"1", "I", text)
        text = re.sub(r"\|", "I", text)

        # Fix common broken ligatures
        text = re.sub(r"ll", "li", text)
        text = re.sub(r"cl", "ci", text)

        # Remove weird symbols
        text = re.sub(r"[~`^]", "", text)

        return text


    # ------------------------------------------------
    # 🔹 Image Preprocessing
    # ------------------------------------------------
    def _preprocess_image(self, image_path):
        img = cv2.imread(image_path)

        if img is None:
            return None

        height, width = img.shape[:2]
        if width < 1000:
            scale = 1000 / width
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)

        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]])
        gray = cv2.filter2D(gray, -1, kernel)

        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            2
        )

        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return thresh


    # ------------------------------------------------
    # 🔹 Title Detection
    # ------------------------------------------------
    def _extract_title_from_text(self, text):
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 5]
        if lines:
            return lines[0]
        return "Untitled"


    def _extract_title_from_pdf(self, pdf):
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
            return best_text.strip()
        except:
            return "Untitled"
