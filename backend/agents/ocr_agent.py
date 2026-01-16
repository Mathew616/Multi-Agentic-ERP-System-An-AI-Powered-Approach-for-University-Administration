import os
import fitz  # PyMuPDF
import tempfile

class OcrAgent:
    def __init__(self):
        print("[OCR Agent] Initializing hybrid OCR (Text + Image + Title Detection)")
        self.ocr = None
        try:
            # Try PaddleOCR but don't fail if it has compatibility issues
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(
                use_angle_cls=False,
                lang="en"
            )
            print("[OCR Agent] OK: PaddleOCR initialized")
        except Exception as e:
            print(f"[OCR Agent] WARNING: PaddleOCR failed ({str(e)[:50]}...), using PyMuPDF only")
            self.ocr = None

    def extract_text(self, file_path):
        """Extracts text and title from PDFs or images intelligently."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        results = []

        # Case 1: Image file input (png, jpg, jpeg)
        if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
            if not self.ocr:
                raise ValueError("PaddleOCR not available for image processing")
            ocr_result = self.ocr.ocr(file_path)
            text = self._parse_ocr_result(ocr_result)
            title = self._extract_title_from_text(text)
            return {"text": text, "title": title, "source": "image"}

        # Case 2: PDF input
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf = fitz.open(file_path)
            title = self._extract_title_from_pdf(pdf)

            for i, page in enumerate(pdf):
                # Try direct text extraction first
                text = page.get_text("text")

                # If text layer exists -> skip OCR
                if text and len(text.strip()) > 30:
                    results.append({
                        "page": i + 1,
                        "text": text.strip(),
                        "source": "digital"
                    })
                    continue

                # Otherwise -> fallback to OCR if available
                if not self.ocr:
                    # No OCR available, just use empty text
                    results.append({
                        "page": i + 1,
                        "text": "",
                        "source": "skipped"
                    })
                    continue
                    
                pix = page.get_pixmap(dpi=150)
                img_path = os.path.join(tmpdir, f"page_{i+1}.png")
                pix.save(img_path)

                try:
                    ocr_result = self.ocr.ocr(img_path)
                    ocr_text = self._parse_ocr_result(ocr_result)
                except Exception as e:
                    print(f"[OCR Agent] WARNING: OCR failed on page {i+1}: {str(e)[:50]}")
                    ocr_text = ""

                results.append({
                    "page": i + 1,
                    "text": ocr_text,
                    "source": "ocr"
                })

        # Combine all pages
        full_text = "\n".join([r["text"] for r in results])
        print(f"[OCR Agent] Extracted text from {len(results)} pages.")
        return {"text": full_text, "title": title, "source": "pdf"}

    # -----------------------------
    # 🔹 Parse PaddleOCR output
    # -----------------------------
    def _parse_ocr_result(self, ocr_result):
        """Convert PaddleOCR output to plain text."""
        if not ocr_result or not ocr_result[0]:
            return ""
        lines = []
        for line in ocr_result[0]:
            if line and len(line) > 1:
                lines.append(line[1][0].strip())
        return "\n".join(lines)

    # -----------------------------
    # 🔹 Extract probable title from text
    # -----------------------------
    def _extract_title_from_text(self, text):
        """Find the most probable title line based on length and formatting."""
        if not text:
            return ""
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 5]
        for line in lines[:5]:
            if len(line.split()) >= 3 and len(line.split()) <= 12:
                return line.title()
        return lines[0].title() if lines else ""

    # -----------------------------
    # 🔹 Extract title from PDF layout
    # -----------------------------
    def _extract_title_from_pdf(self, pdf):
        """Use font size and layout to detect title (fast heuristic)."""
        try:
            page = pdf[0]
            d = page.get_text("dict")
            best_span = None
            best_size = 0
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 0)
                        if not text or len(text) < 3:
                            continue
                        if size > best_size and len(text.split()) <= 12:
                            best_span = text
                            best_size = size
            if best_span:
                title = " ".join(best_span.split())
                print(f"[OCR Agent] 📘 Detected title: {title}")
                return title
        except Exception as e:
            print(f"[OCR Agent] ⚠️ Title detection failed: {e}")

        # Fallback: first non-empty line from text layer
        text = pdf[0].get_text("text")
        for line in text.split("\n"):
            if len(line.strip()) > 5:
                return line.strip().title()
        return "Untitled Document"

    # -----------------------------
    # 🔹 Debug preview (optional)
    # -----------------------------
    def summarize_extracted_text(self, text):
        """Preview of the first few lines for quick debug."""
        preview = "\n".join(text.split("\n")[:10])
        print(f"[OCR Agent] 📄 Preview:\n{preview}")
        return preview
