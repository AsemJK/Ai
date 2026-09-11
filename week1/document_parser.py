import io
import pandas as pd
from docx import Document
from pypdf import PdfReader

def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n\n"
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

def parse_document(filename: str, file_bytes: bytes) -> str:
    """Dispatcher function based on file extension."""
    filename = filename.lower()
    if filename.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return parse_docx(file_bytes)
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        return parse_excel(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {filename}")