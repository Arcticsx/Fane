import re
import shutil
import sys
import uuid
from zipfile import Path
from fastapi import UploadFile
from fastapi import UploadFile
from sqlalchemy.orm import Session
import pymupdf4llm
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer
import pymupdf
import os
from Backend.App.models.rpg_sessions import ProcessStatus, RpgSession, SourceDocument
from ..utility.config import DATA_DIR
from ..utility.config import EMBEDDING_MODEL
from ..utility.status import initialize_status, update_status


UPLOAD_DIR = Path(DATA_DIR) / "files"
ALLOWED_EXTENSIONS = {".pdf"}

def create_source_document(db: Session, session_id: str, file: UploadFile) -> SourceDocument:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    initialize_status(db=db, session_id=session_id)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{session_id[:8]}_{uuid.uuid4().hex}_{Path(file.filename or 'upload.pdf').name}"
    file_path = UPLOAD_DIR / safe_name

    source_doc = SourceDocument(
        session_id=session_id,
        filename=file.filename,
        status="processing",
        chunk_count=0,
        file_path=str(file_path),
    )
    db.add(source_doc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(source_doc)
    update_status(db=db, session_id=session_id, phase="document_upload", status="processing")

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        source_doc.status = "failed"
        db.commit()
        update_status(
            db=db, session_id=session_id, phase="document_upload",
            status="failed", error=f"Failed to save uploaded file: {e}"
        )
        file_path.unlink(missing_ok=True)  # clean up partial file
        raise

    update_status(db=db, session_id=session_id, phase="document_upload", status="completed")
    return source_doc


def normalize_text(text):
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def convert_to_markdown(file_path):
    try:
        return pymupdf4llm.to_markdown(file_path, page_chunks=True)
    except Exception as e:
        print(f"[documents.convert_to_markdown] primary conversion failed for {file_path}: {e}", file=sys.stderr)
        # Fallback: if PDF-to-markdown fails (missing libs or corrupt PDF),
        # try a minimal text extraction to keep processing moving.
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", errors="ignore")
        except Exception as e2:
            print(f"[documents.convert_to_markdown] fallback text extraction failed for {file_path}: {e2}", file=sys.stderr)
            text = ""

        # Return a single-page-like structure compatible with the rest of the pipeline
        return [{"text": text or ""}]

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            if not EMBEDDING_MODEL:
                _embedding_model = None
            else:
                _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        except Exception:
            print(f"[documents._get_embedding_model] failed to load embedding model: {EMBEDDING_MODEL}", file=sys.stderr)
            _embedding_model = None
    return _embedding_model


def token_length(text):
    model = _get_embedding_model()
    if model is None:
        # Fallback: approximate token count by word count
        return max(1, len(text.split()))
    try:
        return len(model.tokenizer.encode(text))
    except Exception:
        print("[documents.token_length] tokenizer.encode failed, falling back to word count", file=sys.stderr)
        return max(1, len(text.split()))

def extract_chapters_from_toc(file_path, total_pages, min_level=1, max_level=1):
    """
    Extract chapter boundaries from a PDF's embedded outline/bookmarks.

    Returns a list of dicts: [{"number": 1, "title": ..., "start_page": ..., "end_page": ...}, ...]
    Returns an empty list if the PDF has no embedded outline (caller should fall back
    to heading-detection in that case).

    min_level/max_level: PDF outlines are hierarchical (level 1 = top-level chapters,
    level 2+ = sub-sections within a chapter). Default keeps only top-level entries.
    Widen the range if a book's "chapters" are nested one level deeper.
    """
    doc = pymupdf.open(file_path)
    toc = doc.get_toc()  # returns [[level, title, page_number], ...], 1-indexed pages
    doc.close()

    
    if not toc:
        return []

    # Filter to the level(s) that represent actual chapters
    entries = [(level, title.strip(), page) for level, title, page in toc
               if min_level <= level <= max_level]

    if not entries:
        return []

    # Build boundaries: each chapter runs until the next entry's start page - 1
    chapters = []
    for i, (level, title, start_page) in enumerate(entries):
        if i + 1 < len(entries):
            end_page = entries[i + 1][2] - 1
        else:
            end_page = total_pages

        # Guard against malformed/duplicate ToC entries producing inverted ranges
        if end_page < start_page:
            end_page = start_page

        print(f"[extract_chapters_from_toc] Chapter {i + 1}: '{title}' pages {start_page}-{end_page}")
        
        chapters.append({
            "number": i + 1,
            "title": title,
            "start_page": start_page,
            "end_page": end_page,
            "page_range": f"{start_page}-{end_page}"
        })

    return chapters


def get_chapters(file_path, total_pages):
    print(f"[get_chapters] Attempting to extract chapters from ToC for {file_path}")
    chapters = extract_chapters_from_toc(file_path, total_pages)
    if chapters:
        return chapters
    return []



def chunk_headers(pages):
    
    headers_to_split_on = [
        ("#", "section"),
        ("##", "subsection"),
        ("###", "subsubsection"),
    ]
    
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False
    )

    header_chunks = []
    
    for page_num, page in enumerate(pages, start=1):
        text = normalize_text(page["text"])
        splits = md_splitter.split_text(text)
        for split in splits:
            split.metadata["page"] = page_num
            header_chunks.append(split)
    
    return header_chunks


def chunk_document(file_path, chunksize, overlap):
    pages = convert_to_markdown(file_path)

    header_chunks = chunk_headers(pages)

    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunksize,
        chunk_overlap=overlap,
        length_function=token_length,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    final_chunks = fallback_splitter.split_documents(header_chunks)
    return final_chunks


def embed_chunks(chunks, batch_size: int = 16):  # Safer default for CPU
    if not chunks:
        return []
    model = _get_embedding_model()
    texts = [chunk.page_content for chunk in chunks]
    if model is None:
        raise RuntimeError("Embedding model not configured")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def get_document_metadata(file_path):
    try:
        with pymupdf.open(file_path) as doc:
            total_pages = doc.page_count
    except Exception:
        total_pages = None

    file_size = os.path.getsize(file_path)

    return {
        "total_pages": total_pages,
        "file_size": file_size,
    }
    
def generate_page_windows(total_pages, window_size=5, overlap=1):
    windows = []
    start = 1
    step = window_size - overlap

    while True:
        end = min(start + window_size - 1, total_pages)
        windows.append((start, end))

        if end >= total_pages:
            break

        start += step

    return windows
            
    
    
    
    
    
    