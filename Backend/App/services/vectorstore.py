try:
    from ..config import CHROMA_PERSIST_DIR
except ImportError:
    from config import CHROMA_PERSIST_DIR
import chromadb
import uuid
from typing import List, Dict, Any, Optional

_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

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

    collection.add(
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
        ids=ids,
    )

    return {
        "chunks_saved": len(chunks),
        "collection": collection.name,
    }


# ============================================================
# QUERY FUNCTIONS FOR GAMEPLAY
# ============================================================

def query_chroma_by_page_range(
    session_id: str,
    query_text: str,
    start_page: int,
    end_page: int,
    n_results: int = 8,
    collection_type: str = "docs",
) -> List[str]:
   
    try:
        collection = get_or_create_collection(session_id, collection_type)
    except ValueError:
        return []  # Collection doesn't exist yet

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where={
            "page": {"$gte": start_page, "$lte": end_page}
        }
    )
    
    # Chroma returns results as list of lists: [[doc1, doc2, ...]]
    if results and results.get("documents"):
        return results["documents"][0]  # First query's results
    
    return []


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

    # Chroma doesn't support direct get with where filters in all versions
    # So we query with a dummy text and page filter
    results = collection.query(
        query_texts=["the story continues"],
        n_results=100,  # Get many results, we'll filter further
        where={"page": {"$gte": start_page, "$lte": end_page}},
        include=["documents", "metadatas"]
    )
    
    formatted = []
    if results and results.get("documents"):
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else []
        
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            formatted.append({
                "text": doc,
                "page": meta.get("page"),
                "chunk_index": meta.get("chunk_index"),
                "section": meta.get("section"),
            })
    
    # Sort by page then chunk_index
    formatted.sort(key=lambda x: (x.get("page", 0), x.get("chunk_index", 0)))
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