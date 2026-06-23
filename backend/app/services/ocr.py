"""OCR service — extracts text from PDFs and images.

Uses pdfplumber for digital PDFs and Tesseract for scanned images, with a
plain-text passthrough. An AWS Textract adapter is stubbed for production.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OcrResult:
    text: str
    confidence: float
    backend: str


def run_ocr(content: bytes, content_type: str | None, filename: str) -> OcrResult:
    """Dispatch to the right extractor based on file type."""
    ctype = (content_type or "").lower()
    name = (filename or "").lower()

    if ctype == "application/pdf" or name.endswith(".pdf"):
        return _ocr_pdf(content)
    if ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".tiff")):
        return _ocr_image(content)
    # Plain text / form submission.
    return OcrResult(text=content.decode("utf-8", errors="ignore"), confidence=1.0, backend="text")


def _ocr_pdf(content: bytes) -> OcrResult:
    try:
        import pdfplumber

        chunks: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                chunks.append(page.extract_text() or "")
        text = "\n".join(chunks).strip()
        if text:
            return OcrResult(text=text, confidence=0.95, backend="pdfplumber")
        # No embedded text → scanned PDF; fall back to image OCR of rendered pages.
        logger.info("PDF has no embedded text; treating as scanned")
        return _ocr_image(content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber failed: %s", exc)
        return OcrResult(text="", confidence=0.0, backend="pdfplumber")


def _ocr_image(content: bytes) -> OcrResult:
    if settings.ocr_backend == "textract":
        return _ocr_textract(content)
    try:
        import pytesseract
        from PIL import Image

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        image = Image.open(io.BytesIO(content))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words = [w for w in data["text"] if w.strip()]
        confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) >= 0]
        text = " ".join(words)
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return OcrResult(text=text, confidence=round(confidence, 3), backend="tesseract")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract OCR unavailable/failed: %s", exc)
        return OcrResult(text="", confidence=0.0, backend="tesseract")


def _ocr_textract(content: bytes) -> OcrResult:
    """AWS Textract adapter — wire up boto3 client('textract') in production."""
    raise NotImplementedError(
        "Textract backend not configured. Set OCR_BACKEND=tesseract or "
        "implement the boto3 Textract call here."
    )
