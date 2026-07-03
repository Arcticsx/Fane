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
        "LoreEntry", back_populates="session", cascade="all, delete-orphan"
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

    def __repr__(self) -> str:
        return f"<RpgSession id={self.id!r} title={self.title!r}>"


class ChronicleChapter(Base):
    __tablename__ = "chronicle_chapters"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(
        String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False
    )
    number = Column(Integer, nullable=False)
    summary = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=False, default=0)
    is_closed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("RpgSession", back_populates="chapters")
    turns = relationship(
        "TurnLog", back_populates="chapter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ChronicleChapter id={self.id!r} session_id={self.session_id!r} "
            f"number={self.number} closed={self.is_closed}>"
        )


class Character(Base):
    __tablename__ = "character"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String)
    role = Column(String)
    personality_md = Column(Text)
    backstory_md = Column(Text)
    secret = Column(Text)

    session = relationship("RpgSession", back_populates="characters")
    relations_as_a = relationship(
        "CharacterRelation",
        foreign_keys="CharacterRelation.char_a_id",
        back_populates="char_a",
    )
    relations_as_b = relationship(
        "CharacterRelation",
        foreign_keys="CharacterRelation.char_b_id",
        back_populates="char_b",
    )


class CharacterRelation(Base):
    __tablename__ = "character_relation"

    char_a_id = Column(String, ForeignKey("character.id"), primary_key=True)
    char_b_id = Column(String, ForeignKey("character.id"), primary_key=True)
    relation_type = Column(String)
    notes = Column(Text)

    char_a = relationship("Character", foreign_keys=[char_a_id], back_populates="relations_as_a")
    char_b = relationship("Character", foreign_keys=[char_b_id], back_populates="relations_as_b")


class LoreEntry(Base):
    __tablename__ = "lore_entry"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    category = Column(String)
    title = Column(String)
    body_md = Column(Text)
    pinned = Column(Boolean, default=False)
    chroma_chunk_id = Column(String, nullable=True)  # references a Chroma vector id, not a SQL FK

    session = relationship("RpgSession", back_populates="lore_entries")


class StoryBeat(Base):
    __tablename__ = "story_beat"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    beat_type = Column(String)  # e.g. "plot_point", "character_arc", "world_event"
    source_document = Column(String, nullable=True)  # optional reference to a source document
    starting_page = Column(Integer, nullable=True)  # optional starting page number in the source document
    ending_page = Column(Integer, nullable=True)  # optional ending page number in the source document
    description = Column(Text)
    status = Column(String, default="pending")  # e.g. "pending", "in_progress", "completed"
    retry_count = Column(Integer, default=0)  # number of times this beat has been retried
    last_attempt = Column(string, nullable=True) 
    beat_order = Column(Integer)  # renamed from 'order' — reserved word, avoid even quoted
    importance = Column(Integer, default=1)  # scale of 1-5, 5 being most important
    introduces = Column(String, nullable=True)  # optional reference to a new character or lore entry introduced by this beat
    requires = Column(String, nullable=True)  # optional reference to a character or lore entry required for this beat
    session = relationship("RpgSession", back_populates="story_beats")


class StoryEvent(Base):
    __tablename__ = "story_event"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    chapter = Column(Integer)  # chapter number, not a FK
    description = Column(Text)
    significance = Column(String)

    session = relationship("RpgSession", back_populates="story_events")


class SourceDocument(Base):
    __tablename__ = "source_document"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("rpg_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String)
    status = Column(String)  # e.g. "processing", "ready", "failed"
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    session = relationship("RpgSession", back_populates="source_documents")


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