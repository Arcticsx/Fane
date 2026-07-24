from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from .dbbase import Base

class Personality(Base):
    __tablename__ = "personalities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, default="")
    system = Column(Text)
    scenario = Column(Text)
    opening_prompt = Column(Text)
    avatar = Column(Text, default="")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_key = Column(Text, ForeignKey("personalities.key", ondelete="CASCADE"), nullable=False)
    persona_id = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    context_entries = relationship(
        "Context",
        back_populates="session",
        cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    sender = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    session = relationship(
        "Session",
        back_populates="messages"
    )


class Context(Base):
    __tablename__ = "context"

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    sender = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    session = relationship(
        "Session",
        back_populates="context_entries"
    )