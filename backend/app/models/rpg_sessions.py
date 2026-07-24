import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .dbbase import Base


def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.now(timezone.utc)

class RpgSession(Base):
    __tablename__ = "rpg_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    synopsis = Column(Text, nullable=True)
    genre = Column(String, nullable=True)
    magic_rules_md = Column(Text, nullable=True)
    active_chapter_number = Column(Integer, nullable=False, default=1)
    context_token_limit = Column(Integer, nullable=True)
    avatar = Column(String, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    setup_status = Column(String, nullable=False, default="not_started")  # e.g. "not_started", "in_progress", "completed"
    setup_error = Column(Text, nullable=True)  # store any error messages during setup
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    chat_started_at = Column(DateTime(timezone=True), nullable=True)

    chapters = relationship(
        "ChronicleChapter",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChronicleChapter.number",
    )
    characters = relationship(
        "Character", back_populates="session", cascade="all, delete-orphan"
    )
    lore_entries = relationship(
        "LoreEntity", back_populates="session", cascade="all, delete-orphan"
    )
    story_beats = relationship(
        "StoryBeat", back_populates="session", cascade="all, delete-orphan"
    )
    story_events = relationship(
        "StoryEvent", back_populates="session", cascade="all, delete-orphan"
    )
    source_documents = relationship(
        "SourceDocument", back_populates="session", cascade="all, delete-orphan"
    )
    chronicle_messages = relationship(
        "ChronicleMessages", back_populates="session", cascade="all, delete-orphan"
    )
    graph_edges = relationship(
        "GraphEdge", back_populates="session", cascade="all, delete-orphan"
    )
    process_statuses = relationship(
        "ProcessStatus", back_populates="session", cascade="all, delete-orphan"
    )
    entities = relationship(
        "Entities",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RpgSession id={self.id!r} title={self.title!r}>"
    
class ProcessStatus(Base):
    __tablename__ = "process_status"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String, nullable=False)  # e.g., "document_upload", "chunking", "embedding"
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    error = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("RpgSession", back_populates="process_statuses")
    steps = relationship("ProcessStep", back_populates="process_status", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("session_id", "phase", name="uq_session_phase"),
    )


class ProcessStep(Base):
    __tablename__ = "process_steps"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String, nullable=False)
    step = Column(String, nullable=False)
    order = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    error = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    process_status_id = Column(String, ForeignKey("process_status.id", ondelete="CASCADE"), nullable=True)
    process_status = relationship("ProcessStatus", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("session_id", "phase", "step", name="uq_session_phase_step"),
    )   

class SourceDocument(Base):
    __tablename__ = "source_document"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=True)
    file_path = Column(String, nullable=True)
    
    # --- Relationships ---
    session = relationship("RpgSession", back_populates="source_documents")
    characters = relationship("Character", back_populates="source_document")
    lore_entries = relationship("LoreEntity", back_populates="source_document")
    story_beats = relationship("StoryBeat", back_populates="source_document")
    story_events = relationship("StoryEvent", back_populates="source_document")
    entities = relationship("Entities", back_populates="source_document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SourceDocument id={self.id!r} filename={self.filename!r} status={self.status!r}>"


class ChronicleChapter(Base):
    __tablename__ = "chronicle_chapters"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(
        String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False
    )
    number = Column(Integer, nullable=False)  # e.g., 1 for Chapter 1
    title = Column(Text, nullable=False)
    start_page = Column(Integer, nullable=False)  # e.g., 1
    end_page = Column(Integer, nullable=False)  # e.g., 10
    page_range = Column(String, nullable=False)  # e.g., "1-10"
    characters = Column(JSON, nullable=True)  # list of character names or IDs
    lore_entries = Column(JSON, nullable=True)  # list of lore entry IDs
    is_closed = Column(Boolean, default=False)

    session = relationship("RpgSession", back_populates="chapters")
    turns = relationship(
        "TurnLog", back_populates="chapter", cascade="all, delete-orphan"
    )
    messages = relationship(
        "ChronicleMessages", back_populates="chapter", cascade="all, delete-orphan"
    )   

    def __repr__(self) -> str:
        return (
            f"<ChronicleChapter id={self.id!r} session_id={self.session_id!r} "
            f"number={self.number} closed={self.is_closed}>"
        )

class Entities(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # e.g., "character", "lore_entry", "story_event"
    pages = Column(JSON, nullable=True)  # list of page numbers where the entity appears
    window_start_page = Column(Integer, nullable=True)
    window_end_page = Column(Integer, nullable=True)
    source_document_id = Column(String, ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True)
    description_md = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    session = relationship("RpgSession", back_populates="entities")
    source_document = relationship("SourceDocument", back_populates="entities")


class Character(Base):
    __tablename__ = "character"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    source_document_id = Column(String, ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True)
    name = Column(String)
    
    classification = Column(String, default="static")
    total_pages = Column(Integer, default=0)
    num_chapters_present = Column(Integer, default=0)
    num_spans = Column(Integer, default=0) 
    session = relationship("RpgSession", back_populates="characters")
    source_document = relationship("SourceDocument", back_populates="characters")
    spans = relationship("CharacterSpan", back_populates="character", cascade="all, delete-orphan", order_by="CharacterSpan.chapter_number")
    segments = relationship("CharacterSegment", back_populates="character", cascade="all, delete-orphan", order_by="CharacterSegment.segment_number")
    arc_states = relationship("CharacterArcState", back_populates="character", cascade="all, delete-orphan")


class CharacterSpan(Base):
    __tablename__ = "character_span"

    id = Column(String, primary_key=True, default=_uuid)
    character_name = Column(String, nullable=False)
    character_id = Column(String, ForeignKey("character.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)

    character = relationship("Character", back_populates="spans")


class CharacterSegment(Base):
    __tablename__ = "character_segment"

    id = Column(String, primary_key=True, default=_uuid)
    character_id = Column(String, ForeignKey("character.id", ondelete="CASCADE"), nullable=False)
    character_name = Column(String, nullable=False)
    segment_number = Column(Integer, nullable=False)
    chapter_start = Column(Integer, nullable=False)
    chapter_end = Column(Integer, nullable=False)

    character = relationship("Character", back_populates="segments")
    arc_state = relationship("CharacterArcState", back_populates="segment", uselist=False, cascade="all, delete-orphan")


class CharacterArcState(Base):
    __tablename__ = "character_arc_state"

    id = Column(String, primary_key=True, default=_uuid)
    character_id = Column(String, ForeignKey("character.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String, ForeignKey("character_segment.id", ondelete="CASCADE"), nullable=False)
    character_name = Column(String, nullable=False)
    segment_number = Column(Integer, nullable=False)
    personality_md = Column(Text)
    fighting_style_md = Column(Text)
    backstory_delta_md = Column(Text)  # what's newly revealed in this arc segment specifically

    character = relationship("Character", back_populates="arc_states")
    segment = relationship("CharacterSegment", back_populates="arc_state")




class LoreEntity(Base):
    __tablename__ = "lore_entity"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    source_document_id = Column(String, ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True)
    name = Column(String)
    entity_type = Column(String)  # "Location" | "Faction" | "Item" | "Concept"
    classification = Column(String, default="static")  # "static" | "evolving"
    total_pages = Column(Integer, default=0)
    num_chapters_present = Column(Integer, default=0)

    session = relationship("RpgSession", back_populates="lore_entries")
    source_document = relationship("SourceDocument", back_populates="lore_entries")
    
    spans = relationship("LoreSpan", back_populates="entity", cascade="all, delete-orphan", order_by="LoreSpan.chapter_number")
    segments = relationship("LoreSegment", back_populates="entity", cascade="all, delete-orphan", order_by="LoreSegment.segment_number")
    states = relationship("LoreState", back_populates="entity", cascade="all, delete-orphan")


class LoreSpan(Base):
    __tablename__ = "lore_span"
    id = Column(String, primary_key=True, default=_uuid)
    entity_id = Column(String, ForeignKey("lore_entity.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    entity = relationship("LoreEntity", back_populates="spans")


class LoreSegment(Base):
    __tablename__ = "lore_segment"
    id = Column(String, primary_key=True, default=_uuid)
    entity_id = Column(String, ForeignKey("lore_entity.id", ondelete="CASCADE"), nullable=False)
    segment_number = Column(Integer, nullable=False)
    chapter_start = Column(Integer, nullable=False)
    chapter_end = Column(Integer, nullable=False)
    entity = relationship("LoreEntity", back_populates="segments")
    state = relationship("LoreState", back_populates="segment", uselist=False, cascade="all, delete-orphan")


class LoreState(Base):
    __tablename__ = "lore_state"
    id = Column(String, primary_key=True, default=_uuid)
    entity_id = Column(String, ForeignKey("lore_entity.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String, ForeignKey("lore_segment.id", ondelete="CASCADE"), nullable=False)

    description_md = Column(Text)     # what it is
    significance_md = Column(Text)    # why it matters / role in plot (delta-style, like backstory)
    mechanics_md = Column(Text)       # type-specific: hazards/rules/powers/manifestations

    entity = relationship("LoreEntity", back_populates="states")
    segment = relationship("LoreSegment", back_populates="state")


class StoryBeat(Base):
    __tablename__ = "story_beat"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    beat_type = Column(String)  # e.g. "plot_point", "character_arc", "world_event"
    source_document_id = Column(String, ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True)
    source_document = relationship("SourceDocument", back_populates="story_beats")
    starting_page = Column(Integer, nullable=True)  # optional starting page number in the source document
    ending_page = Column(Integer, nullable=True)  # optional ending page number in the source document
    window_start_page = Column(Integer, nullable=True)  # optional starting page number of the window
    window_end_page = Column(Integer, nullable=True)  # optional ending page number of the window
    description = Column(Text)
    status = Column(String, default="pending")  # e.g. "candidate, "pending", "in_progress", "completed", "skipped"
    retry_count = Column(Integer, default=0)  # number of times this beat has been retried
    last_attempt = Column(Text, nullable=True) 
    beat_order = Column(Integer)  # renamed from 'order' — reserved word, avoid even quoted
    classification = Column(String)
    characters = Column(Text, nullable=True)
    introduces = Column(Text, nullable=True)  # optional reference to a new character or lore entry introduced by this beat
    requires = Column(Text, nullable=True)  # optional reference to a character or lore entry required for this beat
    key_dialogues = Column(Text, nullable=True)
    session = relationship("RpgSession", back_populates="story_beats")
    
    outgoing_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_beat_id",
        back_populates="source_beat",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_beat_id",
        back_populates="target_beat",
        cascade="all, delete-orphan",
    )
    
class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    source_beat_id = Column(String, ForeignKey("story_beat.id", ondelete="CASCADE"), nullable=False)
    target_beat_id = Column(String, ForeignKey("story_beat.id", ondelete="CASCADE"), nullable=False)
    edge_type = Column(String, nullable=False)  # "causal", "structural", "spine"
    
    # Optional: conditions for conditional edges
    condition_tag = Column(String, nullable=True)  # e.g., "has_sword"
    
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # Relationships
    session = relationship("RpgSession", back_populates="graph_edges")
    source_beat = relationship(
        "StoryBeat", foreign_keys=[source_beat_id], back_populates="outgoing_edges"
    )
    target_beat = relationship(
        "StoryBeat", foreign_keys=[target_beat_id], back_populates="incoming_edges"
    )

class StoryEvent(Base):
    __tablename__ = "story_event"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(
        String,
        ForeignKey("rpg_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    source_document_id = Column(
        String,
        ForeignKey("source_document.id", ondelete="SET NULL"),
        nullable=True
    )

    source_document = relationship(
        "SourceDocument",
        back_populates="story_events"   # fixed
    )

    chapter = Column(Integer)
    description = Column(Text)
    significance = Column(String)

    session = relationship(
        "RpgSession",
        back_populates="story_events"
    )
    

class TurnLog(Base):
    __tablename__ = "turn_log"

    id = Column(String, primary_key=True, default=_uuid)
    chapter_id = Column(String, ForeignKey("chronicle_chapters.id", ondelete="CASCADE"), nullable=False)
    player_action = Column(Text)
    dice_roll = Column(Integer)
    outcome = Column(String)
    narrative = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    chapter = relationship("ChronicleChapter", back_populates="turns")
    
class ChronicleMessages(Base):
    __tablename__ = "chronicle_messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String, ForeignKey("chronicle_chapters.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String)  # e.g., "player", "npc", "system"
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    session = relationship("RpgSession", back_populates="chronicle_messages")
    chapter = relationship("ChronicleChapter", back_populates="messages")