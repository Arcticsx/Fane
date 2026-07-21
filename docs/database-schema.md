# Database Schema

**Engine:** SQLite at `Backend/data/chatbot.db`  
**ORM:** SQLAlchemy 2.0 with `declarative_base()`  
**Session Management:** Context manager with auto-commit/rollback

---

## Chat Domain (4 tables)

### personalities

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `key` | Text | UNIQUE, NOT NULL | URL-safe slug identifier |
| `name` | Text | NOT NULL | Display name |
| `description` | Text | default="" | Short description |
| `system` | Text | | System prompt for the LLM |
| `scenario` | Text | | Scenario context |
| `opening_prompt` | Text | | First message shown to user |
| `avatar` | Text | default="" | Relative path to avatar image |

### sessions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `persona_key` | Text | FK → personalities.key, ON DELETE CASCADE, NOT NULL | |
| `persona_id` | Text | | Legacy field |
| `created_at` | Text | NOT NULL | ISO timestamp |
| `updated_at` | Text | NOT NULL | ISO timestamp |

**Relationships:** has many `messages`, has many `context_entries` (cascade delete)

### messages

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `session_id` | Integer | FK → sessions.id, ON DELETE CASCADE, NOT NULL | |
| `sender` | Text | NOT NULL | "user" or "assistant" |
| `content` | Text | NOT NULL | Message content |

### context

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `session_id` | Integer | FK → sessions.id, ON DELETE CASCADE, NOT NULL | |
| `sender` | Text | NOT NULL | "user" or "assistant" |
| `content` | Text | NOT NULL | Message content |

The `context` table mirrors `messages` but is used for the client-side display context (includes IDs for tracking).

---

## Chronicle Domain (17 tables)

### rpg_sessions

Top-level chronicle session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `title` | String | NOT NULL | Chronicle title |
| `synopsis` | Text | | Story synopsis |
| `genre` | String | | Genre (e.g., "fantasy") |
| `magic_rules_md` | Text | | World rules in Markdown |
| `active_chapter_number` | Integer | NOT NULL, default=1 | Current chapter |
| `context_token_limit` | Integer | | Token limit for context |
| `avatar` | String | | Avatar image path |
| `is_archived` | Boolean | NOT NULL, default=False | |
| `setup_status` | String | NOT NULL, default="not_started" | "not_started", "in_progress", "completed" |
| `setup_error` | Text | | Error during setup |
| `created_at` | DateTime | NOT NULL, default=now | |
| `updated_at` | DateTime | NOT NULL, default=now, onupdate=now | |
| `chat_started_at` | DateTime | | When chat began |

**Relationships:** chapters, characters, lore_entries, story_beats, story_events, source_documents, chronicle_messages, graph_edges, process_statuses

### process_status

Tracks pipeline phase status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `phase` | String | NOT NULL, UNIQUE with session_id | Phase name |
| `status` | String | NOT NULL, default="pending" | "pending", "processing", "completed", "failed" |
| `error` | String | | Error message |
| `started_at` | DateTime | | |
| `completed_at` | DateTime | | |

**Relationships:** has many `steps`

### process_steps

Individual steps within a pipeline phase.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `phase` | String | NOT NULL | Parent phase name |
| `step` | String | NOT NULL, UNIQUE with session_id+phase | Step name |
| `order` | Integer | NOT NULL, default=0 | Execution order |
| `status` | String | NOT NULL, default="pending" | |
| `error` | String | | |
| `started_at` | DateTime | | |
| `completed_at` | DateTime | | |
| `process_status_id` | String | FK → process_status.id, CASCADE | |

### source_document

Uploaded PDF metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `filename` | String | NOT NULL | Original filename |
| `status` | String | NOT NULL, default="pending" | "pending", "processing", "ready", "failed" |
| `chunk_count` | Integer | default=0 | Number of chunks in ChromaDB |
| `uploaded_at` | DateTime | NOT NULL, default=now | |
| `processing_started_at` | DateTime | | |
| `processing_completed_at` | DateTime | | |
| `error_message` | Text | | |
| `last_heartbeat` | DateTime | | Crash detection (5min timeout) |
| `file_size_bytes` | Integer | | |
| `total_pages` | Integer | | |
| `file_path` | String | | Absolute path to saved file |

**Relationships:** characters, lore_entries, story_beats, story_events

### chronicle_chapters

Chapter boundaries extracted from PDF ToC.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `number` | Integer | NOT NULL | Chapter number |
| `title` | Text | NOT NULL | Chapter title |
| `start_page` | Integer | NOT NULL | |
| `end_page` | Integer | NOT NULL | |
| `page_range` | String | NOT NULL | e.g., "1-10" |
| `characters` | JSON | | List of character names/IDs |
| `lore_entries` | JSON | | List of lore entry IDs |
| `is_closed` | Boolean | default=False | |

**Relationships:** turns, messages

### entities

Raw extracted entities (before processing).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `name` | String | NOT NULL | Entity name |
| `entity_type` | String | NOT NULL | "character", "location", "faction", "item", "concept" |
| `pages` | JSON | | List of page numbers |
| `window_start_page` | Integer | | Extraction window start |
| `window_end_page` | Integer | | Extraction window end |
| `source_document_id` | String | FK → source_document.id, SET NULL | |
| `description_md` | Text | | |
| `created_at` | DateTime | NOT NULL, default=now | |

### character

Processed characters.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `source_document_id` | String | FK → source_document.id, SET NULL | |
| `name` | String | | Character name |
| `classification` | String | default="static" | "static" or "arc-based" |
| `total_pages` | Integer | default=0 | |
| `num_chapters_present` | Integer | default=0 | |
| `num_spans` | Integer | default=0 | |

**Relationships:** spans, segments, arc_states

### character_span

Page spans per character per chapter.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `character_name` | String | NOT NULL | |
| `character_id` | String | FK → character.id, CASCADE, NOT NULL | |
| `chapter_number` | Integer | NOT NULL | |
| `start_page` | Integer | NOT NULL | |
| `end_page` | Integer | NOT NULL | |
| `page_count` | Integer | NOT NULL | |

### character_segment

Arc segments for characters.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `character_id` | String | FK → character.id, CASCADE, NOT NULL | |
| `character_name` | String | NOT NULL | |
| `segment_number` | Integer | NOT NULL | |
| `chapter_start` | Integer | NOT NULL | |
| `chapter_end` | Integer | NOT NULL | |

**Relationships:** has one `arc_state`

### character_arc_state

LLM-generated character analysis per segment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `character_id` | String | FK → character.id, CASCADE, NOT NULL | |
| `segment_id` | String | FK → character_segment.id, CASCADE, NOT NULL | |
| `character_name` | String | NOT NULL | |
| `segment_number` | Integer | NOT NULL | |
| `personality_md` | Text | | Temperament, values, speech patterns |
| `fighting_style_md` | Text | | Weapons, techniques, tactics |
| `backstory_delta_md` | Text | | What's newly revealed in this segment |

### lore_entity

Processed lore entities (locations, factions, items, concepts).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `source_document_id` | String | FK → source_document.id, SET NULL | |
| `name` | String | | |
| `entity_type` | String | | "Location", "Faction", "Item", "Concept" |
| `classification` | String | default="static" | "static" or "evolving" |
| `total_pages` | Integer | default=0 | |
| `num_chapters_present` | Integer | default=0 | |

**Relationships:** spans, segments, states

### lore_span

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `entity_id` | String | FK → lore_entity.id, CASCADE, NOT NULL | |
| `chapter_number` | Integer | NOT NULL | |
| `start_page` | Integer | NOT NULL | |
| `end_page` | Integer | NOT NULL | |
| `page_count` | Integer | NOT NULL | |

### lore_segment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `entity_id` | String | FK → lore_entity.id, CASCADE, NOT NULL | |
| `segment_number` | Integer | NOT NULL | |
| `chapter_start` | Integer | NOT NULL | |
| `chapter_end` | Integer | NOT NULL | |

**Relationships:** has one `state`

### lore_state

LLM-generated lore analysis per segment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `entity_id` | String | FK → lore_entity.id, CASCADE, NOT NULL | |
| `segment_id` | String | FK → lore_segment.id, CASCADE, NOT NULL | |
| `description_md` | Text | | What it is |
| `significance_md` | Text | | Why it matters / role in plot |
| `mechanics_md` | Text | | Type-specific: hazards/rules/powers/manifestations |

### story_beat

Extracted story beats.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `beat_type` | String | | "plot_point", "character_arc", "world_event", etc. |
| `source_document_id` | String | FK → source_document.id, SET NULL | |
| `starting_page` | Integer | | |
| `ending_page` | Integer | | |
| `window_start_page` | Integer | | |
| `window_end_page` | Integer | | |
| `description` | Text | | What happens in the beat |
| `status` | String | default="pending" | "candidate", "pending", "in_progress", "completed", "skipped" |
| `retry_count` | Integer | default=0 | |
| `last_attempt` | Text | | |
| `beat_order` | Integer | | Sequence order |
| `classification` | String | | "mandatory" or "scene" |
| `characters` | Text | | Characters involved |
| `introduces` | Text | | New entities introduced |
| `requires` | Text | | Required entities |
| `key_dialogues` | Text | | Important dialogue |

**Relationships:** outgoing_edges, incoming_edges

### graph_edges

Directed edges between story beats.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `source_beat_id` | String | FK → story_beat.id, CASCADE, NOT NULL | |
| `target_beat_id` | String | FK → story_beat.id, CASCADE, NOT NULL | |
| `edge_type` | String | NOT NULL | "causal", "structural", "spine" |
| `condition_tag` | String | | Optional condition for conditional edges |
| `created_at` | DateTime | NOT NULL, default=now | |

### story_event

Narrative events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `source_document_id` | String | FK → source_document.id, SET NULL | |
| `chapter` | Integer | | |
| `description` | Text | | |
| `significance` | String | | |

### turn_log

RPG turn logs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `chapter_id` | String | FK → chronicle_chapters.id, CASCADE, NOT NULL | |
| `player_action` | Text | | |
| `dice_roll` | Integer | | |
| `outcome` | String | | |
| `narrative` | Text | | |
| `created_at` | DateTime | NOT NULL, default=now | |

### chronicle_messages

Chronicle chat messages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | String | PK, default=uuid | |
| `session_id` | String | FK → rpg_sessions.id, CASCADE, NOT NULL | |
| `chapter_id` | String | FK → chronicle_chapters.id, CASCADE, NOT NULL | |
| `sender` | String | | "player", "narrator", "system" |
| `content` | Text | | |
| `created_at` | DateTime | NOT NULL, default=now | |

---

## Entity Relationship Diagram

```
personalities ◄──────── sessions
                          │
                    ┌─────┴─────┐
                 messages    context

rpg_sessions ◄─────────────────────────────────────────────────────────────┐
    │                                                                       │
    ├── chronicle_chapters ◄──────── turn_log                               │
    │         │                                                             │
    │         └──────────► chronicle_messages                               │
    │                                                                       │
    ├── source_document                                                     │
    │         │                                                             │
    │         ├──► character ──► character_span                             │
    │         │         │                                                   │
    │         │         ├──► character_segment ──► character_arc_state      │
    │         │                                                             │
    │         ├──► lore_entity ──► lore_span                                │
    │         │              │                                              │
    │         │              └──► lore_segment ──► lore_state               │
    │         │                                                             │
    │         ├──► story_beat ◄──► graph_edges                              │
    │         │                                                             │
    │         └──► story_event                                              │
    │                                                                       │
    ├── entities (raw)                                                      │
    │                                                                       │
    ├── process_status ──► process_steps                                    │
    │                                                                       │
    └───────────────────────────────────────────────────────────────────────┘
```

All chronicle relationships use `ON DELETE CASCADE` -- deleting an `rpg_session` removes all associated data.
