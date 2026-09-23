import io
import pandas as pd
from docx import Document
from pypdf import PdfReader
from ebooklib import epub
# --- New OCR Imports ---
import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError

def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n\n"
    # --- FALLBACK TO OCR IF DIGITAL TEXT IS EMPTY ---
    if not text.strip():
        print("🔍 No digital text found — falling back to OCR...")
        text = ocr_pdf_bytes(file_bytes, lang="ara+eng")
    return text

def parse_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    text = "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
    return text

def parse_excel(file_bytes: bytes) -> str:
    """
    Excel files are tricky for RAG. We convert rows into natural language 
    sentences so the embedding model understands the context.
    """
    df = pd.read_excel(io.BytesIO(file_bytes))
    text = ""
    for index, row in df.iterrows():
        # Format: "Record 1: Name is John, Role is Engineer, Location is Austin"
        row_data = ", ".join([f"{col} is {val}" for col, val in row.items() if pd.notna(val)])
        text += f"Record {index + 1}: {row_data}\n\n"
    return text

def parse_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")

def parse_epub(file_bytes: bytes) -> str:    
    book = epub.read_epub(io.BytesIO(file_bytes))
    text = ""
    for item in book.get_items():
        if item.get_type() == epub.FILE_TYPE_DOCUMENT:
            text += item.get_content().decode("utf-8", errors="ignore") + "\n\n"
    return text

def parse_document(filename: str, file_bytes: bytes) -> str:
    """Dispatcher function based on file extension."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return parse_docx(file_bytes)
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        return parse_excel(file_bytes)
    elif filename.endswith(".txt"):
        return parse_txt(file_bytes)
    elif filename.endswith(".epub"):
        return parse_epub(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {filename}")

def ocr_pdf_bytes(file_bytes: bytes, lang: str = "ara+eng") -> str:
    """
    Renders PDF pages as images in-memory and extracts text via Tesseract OCR.
    Supports dual languages (Arabic + English).
    """
    try:
        # dpi=200 is the sweet spot between OCR accuracy and processing speed/memory
        images = convert_from_bytes(file_bytes, dpi=200)
    except PDFInfoNotInstalledError:
        raise RuntimeError("Poppler is not installed. Run: sudo apt install -y poppler-utils")
    ocr_text = []
    for page_idx, img in enumerate(images):
        page_str = pytesseract.image_to_string(img, lang=lang)
        if page_str.strip():
            ocr_text.append(f"\n--- Page {page_idx + 1} ---\n{page_str.strip()}")
    return "\n\n".join(ocr_text)