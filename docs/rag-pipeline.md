# RAG Pipeline

The RAG (Retrieval-Augmented Generation) pipeline processes uploaded PDFs into a structured knowledge base used for chronicle chat. It runs as a background task after document upload.

## Pipeline Overview

```
PDF Upload
  │
  ▼
Phase 1: Document Processing
  ├── metadata_extraction    → page count, file size
  ├── chapter_extraction     → PDF ToC → ChronicleChapter rows
  └── vector_storage         → chunk (500 tokens, 50 overlap) → embed → ChromaDB
  │
  ▼
Phase 2: Story Beats
  ├── beats_extract          → windowed LLM extraction (5-page windows, 1-page overlap)
  ├── beats_reduce           → chunk candidates → LLM deduplication → merge clusters
  ├── beats_save_reduced     → replace candidates with final beats
  └── beats_graph            → build causal/structural/spine edges
  │
  ▼
Phase 3: Entity Processing
  ├── entities_extract       → windowed LLM extraction
  ├── entities_merge         → exact-match + fuzzy-match canonicalization
  ├── entities_separate      → split into characters vs lore
  ├── characters_classify    → rank and classify (static vs arc-based)
  ├── characters_persist     → save characters, spans, chapter associations
  ├── characters_segment     → segment by chapter gaps
  ├── characters_arc         → LLM personality/backstory/fighting_style per segment
  ├── lore_classify          → classify lore entities
  ├── lore_persist           → save lore entities and chapter associations
  ├── lore_segment           → segment lore entities
  └── lore_arc               → LLM description/significance/mechanics (stub)
```

## Phase 1: Document Processing

### Metadata Extraction

Extracts basic file properties using PyMuPDF:
- Total page count
- File size in bytes

### Chapter Extraction

Parses the PDF's embedded table of contents (bookmarks/outline) using PyMuPDF. Each entry becomes a `ChronicleChapter` row with:
- Chapter number and title
- Start/end page range
- Page range string (e.g., "1-10")

If no ToC is found, a single chapter spanning the entire document is created.

### Vector Storage

**Chunking Strategy:**

1. Convert PDF to Markdown using `pymupdf4llm` with page-level chunks
2. Split by Markdown headers (`#`, `##`, `###`) using `MarkdownHeaderTextSplitter`
3. Further split into 500-token chunks with 50-token overlap using `RecursiveCharacterTextSplitter`

Each chunk retains metadata: page number, start index, section header, category, source PDF filename.

**Embedding:**

Uses `SentenceTransformer` (default: `thenlper/gte-small`) to generate embeddings in batches of 64.

**ChromaDB Storage:**

Chunks are stored in a persistent ChromaDB collection named `session_{id}_docs`. Each document entry contains:
- `text`: chunk content
- `page`: page number
- `start_index`: character offset in original page
- `section`: Markdown header path
- `category`: content category
- `source_pdf`: original filename

## Phase 2: Story Beats

### Extraction

Uses a sliding window approach:
- **Window size:** 5 pages
- **Overlap:** 1 page
- **Cooldown:** 3 seconds between LLM calls
- **Abort condition:** 3 consecutive failures

For each window, the system:
1. Queries ChromaDB for chunks in the page range
2. Assembles text with page markers
3. Calls the LLM with a structured output schema (`BEAT_SCHEMA`)

Each extracted beat includes:
- `classification`: `mandatory` or `scene`
- `beat_type`: one of 9 types (e.g., `plot_point`, `character_arc`, `world_event`)
- `description`: what happens in the beat
- `starting_page` / `ending_page`: page range
- `requires` / `introduces`: dependency tags
- `characters`: characters involved
- `key_dialogues`: important dialogue snippets

### Reduction

Candidate beats are reduced through a multi-step process:

1. **Chunk by budget:** Pack candidates into 4000-token chunks with overlap
2. **LLM reduction:** Each chunk is sent to the LLM for deduplication and tag unification
3. **Merge clusters:** Sliding-window merge of reduced clusters
4. **Tag canonicalization:** Post-processes all `requires`/`introduces` tags and character names using fuzzy matching (`difflib.get_close_matches`, cutoff=0.85)

### Graph Construction

Builds a directed graph of beat relationships:

- **Spine edges:** Sequential connections between mandatory beats (sorted by page)
- **Attachment edges:** Scene beats attach to the nearest preceding mandatory beat
- **Return edges:** Bidirectional attachment (mandatory → scene → mandatory)
- **Sequential edges:** Ordering within scene groups

Edge types: `causal`, `structural`, `spine`.

## Phase 3: Entity Processing

### Extraction

Similar windowed approach to beats. Extracts named entities with:
- `name`: entity name
- `entity_type`: `character`, `location`, `faction`, `item`, or `concept`
- `pages`: list of page numbers where the entity appears

### Merge

Two-pass merge:
1. **Exact match:** Merge entities with identical (type, name) pairs, union their page lists
2. **Fuzzy match:** Use Union-Find data structure with containment checks and fuzzy ratio matching (handles "Grover" vs "Grover Underwood", "Mr. Brunner/Chiron" compound aliases)

### Separate

Split merged entities into:
- **Characters:** `character` type entities
- **Lore:** `location`, `faction`, `item`, `concept` type entities

### Character Processing

**Span Construction:**

Groups consecutive page numbers into spans with configurable gap tolerance. Each span becomes a `CharacterSpan` row.

**Classification:**

Characters are classified as `static` or `arc-based` based on:
- Size threshold: 15% of total book pages
- Frequent recurrence: >= 4 spans
- Gap threshold: 5% of total book pages between qualifying spans

**Segmentation:**

Arc-based characters are divided into segments:
- **Continuous path:** Evenly-sized blocks within the character's own chapter range
- **Clustered path:** Groups by gap threshold

**Arc Analysis:**

For each segment, the system:
1. Retrieves ChromaDB chunks for the segment's page range
2. Scores chunks using keyword-based heuristics (personality, backstory, fighting style keywords)
3. Selects top-scoring chunks per category
4. Calls the LLM with three specialized prompts:
   - `PERSONALITY_PROMPT`: Temperament, values, speech patterns, traits
   - `BACKSTORY_PROMPT`: Past history, origins, formative events
   - `FIGHTING_STYLE_PROMPT`: Weapons, techniques, tactical approach

Results are persisted as `CharacterArcState` rows.

### Lore Processing

**Classification:**

Lore entities are classified as `static` or `evolving` using the same thresholds as characters. Items and Concepts are always static.

**Persistence:**

Lore entities, spans, and segments are saved. Arc analysis for lore (`lore_arc`) is defined but not fully implemented.

## Status Tracking

The pipeline uses a two-level status system:

- **ProcessStatus:** Tracks overall phase status (`pending`, `processing`, `completed`, `failed`)
- **ProcessStep:** Tracks individual steps within a phase

Phases auto-complete when all their steps complete. A heartbeat thread runs every 5 seconds during processing to detect crashes.

## RAG During Chronicle Chat

When a user sends a message in chronicle chat:

1. The system queries ChromaDB with `query_chroma_for_lore(session_id, user_input, n_results=5)`
2. Top 5 relevant snippets are injected into the system prompt as "Relevant PDF content"
3. The system prompt also includes: title, genre, synopsis, world rules
4. The LLM generates a narrative response with this enriched context

## Configuration

| Parameter | Value | Location |
|-----------|-------|----------|
| Chunk size | 500 tokens | `documents.py` |
| Chunk overlap | 50 tokens | `documents.py` |
| Extraction window | 5 pages | `run_beats_phase.py` |
| Window overlap | 1 page | `run_beats_phase.py` |
| LLM cooldown | 3 seconds | `run_beats_phase.py` |
| Consecutive failure abort | 3-5 | Phase-dependent |
| RAG results | 5 snippets | `chronicle_router.py` |
| Token budget (reduction) | 4000 tokens | `run_beats_phase.py` |
| Fuzzy match cutoff | 0.85 | `extraction.py` |
