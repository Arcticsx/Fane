import sys
try:
    from ..config import CHROMA_PERSIST_DIR
except ImportError:
    from config import CHROMA_PERSIST_DIR
import chromadb
import uuid
from typing import List, Dict, Any, Optional

 # NOTE: directory must exist before the PersistentClient is created against it,
 # and Path.mkdir() takes `exist_ok`, not `exist`.
try:
    CHROMA_PERSIST_DIR.mkdir(exist_ok=True)
    _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
except Exception as e:
    print(f"[vectorstore] Failed to initialize chromadb client at {CHROMA_PERSIST_DIR}: {e}", file=sys.stderr)
    _client = None


def get_or_create_collection(session_id: str, collection_type: str):

    if collection_type not in ("docs", "lore"):
        raise ValueError(f"Invalid collection_type: {collection_type}. Must be 'docs' or 'lore'")

    client = _client
    collection_name = f"session_{session_id}_{collection_type}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"session_id": session_id, "type": collection_type},
    )


def _infer_category(metadata: dict) -> str:
    """Best-effort category from header metadata, for optional where-filtering later."""
    header = metadata.get("subsection") or metadata.get("section") or ""
    return header.strip().lower() if header else "general"


def save_chunks_to_chromadb(
    chunks,
    embeddings,
    session_id: str,
    source_pdf: str,
    collection_type: str = "docs",
):

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Mismatch between chunks ({len(chunks)}) and embeddings ({len(embeddings)})"
        )

    if not chunks:
        return {"chunks_saved": 0}

    collection = get_or_create_collection(session_id, collection_type)

    documents = [chunk.page_content for chunk in chunks]
    metadatas = [
        {
            **{k: v for k, v in chunk.metadata.items() if v is not None},
            "category": _infer_category(chunk.metadata),
            "source_pdf": source_pdf,
            "session_id": session_id,
        }
        for chunk in chunks
    ]
    ids = [f"{session_id}_{uuid.uuid4()}" for _ in chunks]

    try:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
            ids=ids,
        )
    except Exception as e:
        print(f"[vectorstore.save_chunks_to_chromadb] Failed to add chunks for session {session_id}: {e}", file=sys.stderr)
        raise

    return {
        "chunks_saved": len(chunks),
        "collection": collection.name,
    }


# ============================================================
# QUERY FUNCTIONS FOR GAMEPLAY
# ============================================================

def query_chroma_by_page_range(
    session_id: str,
    start_page: int,
    end_page: int,
    n_results: int = 100,
    collection_type: str = "docs",
) -> List[Dict[str, Any]]:
    """
    Returns every chunk whose page falls within [start_page, end_page],
    ordered by page then start_index. Uses collection.get() (a metadata
    filter) rather than collection.query() (a similarity search), since
    there is no meaningful query text here -- we want everything in the
    range, not the top-k nearest to an empty/default embedding.

    Returns a list of dicts: {"text": str, "page": int, "start_index": int,
    "section": str, "subsection": str}
    """
    try:
        collection = get_or_create_collection(session_id, collection_type)
    except ValueError:
        return []  # Collection doesn't exist yet

    results = collection.get(
        where={
            "page": {"$gte": start_page, "$lte": end_page}
        },
        limit=n_results,
        include=["documents", "metadatas"],
    )

    docs = results.get("documents") or []
    metas = results.get("metadatas") or []

    formatted = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        formatted.append({
            "text": doc,
            "page": meta.get("page"),
            "start_index": meta.get("start_index"),
            "section": meta.get("section"),
            "subsection": meta.get("subsection"),
        })

    formatted.sort(key=lambda x: (x.get("page") or 0, x.get("start_index") or 0))
    return formatted


def query_chroma_for_lore(
    session_id: str,
    query_text: str,
    n_results: int = 5,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:

    try:
        collection = get_or_create_collection(session_id, "docs")
    except ValueError:
        return []  # Collection doesn't exist

    # Build where filter
    where_filter = {}
    if category:
        where_filter["category"] = category

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_filter if where_filter else None,
        include=["documents", "metadatas"]
    )

    # Format results
    formatted = []
    if results and results.get("documents"):
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else []

        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            formatted.append({
                "text": doc,
                "page": meta.get("page"),
                "source_pdf": meta.get("source_pdf"),
                "category": meta.get("category"),
                "section": meta.get("section"),
                "subsection": meta.get("subsection"),
            })

    return formatted


def get_all_chunks_by_page(
    session_id: str,
    start_page: int,
    end_page: int,
    collection_type: str = "docs",
) -> List[Dict[str, Any]]:

    try:
        collection = get_or_create_collection(session_id, collection_type)
    except ValueError:
        return []

    # Metadata filter via collection.get() -- no similarity search needed.
    results = collection.get(
        where={"page": {"$gte": start_page, "$lte": end_page}},
        include=["documents", "metadatas"],
    )

    docs = results.get("documents") or []
    metas = results.get("metadatas") or []

    formatted = []
    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        formatted.append({
            "text": doc,
            "page": meta.get("page"),
            # NOTE: chunking (documents.py) sets "start_index" via
            # RecursiveCharacterTextSplitter(add_start_index=True), not
            # "chunk_index" -- that key never existed, so sorting by it
            # was always a no-op.
            "start_index": meta.get("start_index"),
            "section": meta.get("section"),
        })

    formatted.sort(key=lambda x: (x.get("page") or 0, x.get("start_index") or 0))
    return formatted


def delete_session_collections(session_id: str) -> Dict[str, bool]:

    client = _client
    results = {}

    for collection_type in ["docs", "lore"]:
        collection_name = f"session_{session_id}_{collection_type}"
        try:
            client.delete_collection(collection_name)
            results[collection_type] = True
        except ValueError:
            # Collection doesn't exist
            results[collection_type] = False

    return results


def get_collection_stats(session_id: str) -> Dict[str, Any]:

    stats = {}

    for collection_type in ["docs", "lore"]:
        try:
            collection = get_or_create_collection(session_id, collection_type)
            stats[collection_type] = collection.count()
        except ValueError:
            stats[collection_type] = 0

    return stats