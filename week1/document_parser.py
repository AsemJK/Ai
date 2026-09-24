import io
import pandas as pd
import numpy as np
from docx import Document
from pypdf import PdfReader
from ebooklib import epub
from PIL import Image, ImageEnhance

# --- OCR Imports ---
import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError

# --- Lazy load EasyOCR to avoid slowing down startup if not used ---
_easyocr_reader = None

def get_easyocr_reader(langs: list):
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        # gpu=False is safer for general use. Set to True if you have CUDA.
        _easyocr_reader = easyocr.Reader(langs, gpu=True) 
    return _easyocr_reader


def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """
    Enhances image quality before passing to OCR.
    Converts to grayscale and boosts contrast to make text pop.
    """
    # Convert to grayscale
    img = img.convert('L')
    # Boost contrast (helps with faded scans)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    return img


def parse_pdf(file_bytes: bytes, ocr_engine: str = "easyocr", lang: str = "ara+eng") -> str:
    """
    Extracts text from PDF. 
    Uses smart detection to fallback to OCR only if digital text is missing/insufficient.
    
    :param ocr_engine: "tesseract" or "easyocr"
    :param lang: Tesseract format (e.g., "ara+eng") or EasyOCR format (e.g., ["ar", "en"])
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = ""
    
    # 1. Try to extract digital text first
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            # Strip invalid surrogates from each page
            cleaned = extracted.encode("utf-8", "ignore").decode("utf-8")
            full_text += cleaned + "\n\n"
            
    # 2. Smart Fallback: If text is empty or just a few words (e.g., headers/footers), use OCR
    if len(full_text.strip()) < 50:
        print("🔍 No meaningful digital text found — falling back to OCR...")
        
        if ocr_engine == "easyocr":
            # EasyOCR expects a list of language codes
            easyocr_langs = ["en", "ar"] if "ara" in lang or "ar" in str(lang) else ["en"]
            full_text = ocr_pdf_bytes_easyocr(file_bytes, langs=easyocr_langs)
        else:
            full_text = ocr_pdf_bytes_tesseract(file_bytes, lang=lang)
            
    return full_text.encode("utf-8", "ignore").decode("utf-8")


def ocr_pdf_bytes_tesseract(file_bytes: bytes, lang: str = "ara+eng") -> str:
    """
    Renders PDF pages as images and extracts text via Tesseract OCR.
    Includes image preprocessing for better accuracy.
    """
    try:
        # Increased DPI to 300 for better OCR accuracy on text
        images = convert_from_bytes(file_bytes, dpi=300)
    except PDFInfoNotInstalledError:
        raise RuntimeError("Poppler is not installed. Run: sudo apt install -y poppler-utils")
        
    ocr_text = []
    for page_idx, img in enumerate(images):
        # Preprocess image for better OCR results
        img = preprocess_image_for_ocr(img)
        
        page_str = pytesseract.image_to_string(img, lang=lang)
        if page_str.strip():
            ocr_text.append(f"\n--- Page {page_idx + 1} ---\n{page_str.strip()}")
            
    return "\n\n".join(ocr_text)


def ocr_pdf_bytes_easyocr(file_bytes: bytes, langs: list = ["en", "ar"]) -> str:
    """
    Renders PDF pages as images and extracts text via EasyOCR.
    Often more accurate than Tesseract for mixed languages and complex layouts.
    """
    try:
        images = convert_from_bytes(file_bytes, dpi=300)
    except PDFInfoNotInstalledError:
        raise RuntimeError("Poppler is not installed. Run: sudo apt install -y poppler-utils")

    reader = get_easyocr_reader(langs)
    ocr_text = []
    
    for page_idx, img in enumerate(images):
        # Preprocess image
        img = preprocess_image_for_ocr(img)
        
        # EasyOCR requires a numpy array
        img_np = np.array(img)
        results = reader.readtext(img_np)
        
        # Extract the text from the results (result format: [bbox, text, confidence])
        page_str = " ".join([res[1] for res in results])
        
        if page_str.strip():
            ocr_text.append(f"\n--- Page {page_idx + 1} ---\n{page_str.strip()}")
            
    return "\n\n".join(ocr_text)


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


def parse_document(filename: str, file_bytes: bytes, ocr_engine: str = "easyocr") -> str:
    """Dispatcher function based on file extension."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return parse_pdf(file_bytes, ocr_engine=ocr_engine)
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