import re
import pymupdf4llm
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer
import pymupdf
import os

try:
    from ..config import EMBEDDING_MODEL
except ImportError:
    from config import EMBEDDING_MODEL


def normalize_text(text):
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def convert_to_markdown(file_path):
    return pymupdf4llm.to_markdown(file_path, page_chunks=True)

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def token_length(text):
    return len(_get_embedding_model().tokenizer.encode(text))

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


def chunk_document(file_path):
    pages = convert_to_markdown(file_path)

    header_chunks = chunk_headers(pages)

    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=token_length,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    final_chunks = fallback_splitter.split_documents(header_chunks)
    return final_chunks


def embed_chunks(chunks, batch_size: int = 16):  # Safer default for CPU
    if not chunks:
        return []
    texts = [chunk.page_content for chunk in chunks]
    embeddings = _get_embedding_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,  # Keep True for MVP (visibility)
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def get_document_metadata(file_path):
    
    with pymupdf.open(file_path) as doc:
        total_pages = doc.page_count

    file_size = os.path.getsize(file_path)

    return {
        "total_pages": total_pages,
        "file_size": file_size 
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
            
    
    
    
    
    
    