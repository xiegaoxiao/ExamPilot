"""Persistence records; business transitions live in services, never in HTTP handlers."""
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str]
    exam_date: Mapped[str | None]
    budget_minutes: Mapped[int | None] = mapped_column(default=30)
    archived: Mapped[bool] = mapped_column(default=False)
    demo_key: Mapped[str | None] = mapped_column(unique=True)


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    name: Mapped[str]
    position: Mapped[int] = mapped_column(default=0)
    exam_focus: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("subject_id", "chapter_id", "sha256"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"))
    filename: Mapped[str]
    path: Mapped[str]
    sha256: Mapped[str]
    pages: Mapped[list] = mapped_column(JSON)
    status: Mapped[str]
    parser_version: Mapped[str]
    created_at: Mapped[float] = mapped_column(Float)


class Knowledge(Base):
    __tablename__ = "knowledge"
    __table_args__ = (UniqueConstraint("subject_id", "chapter_id", "name"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"))
    name: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"))
    current_version_id: Mapped[str | None]


class Version(Base):
    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"))
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default="draft")
    issues: Mapped[list] = mapped_column(JSON, default=list)
    semantic_change: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[float] = mapped_column(Float)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("subject_id", "request_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    request_id: Mapped[str]
    request_digest: Mapped[str]
    answer: Mapped[Any] = mapped_column(JSON)
    initial_result: Mapped[str]
    elapsed_seconds: Mapped[int]
    created_at: Mapped[float] = mapped_column(Float)


class Resolution(Base):
    __tablename__ = "attempt_resolutions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), unique=True)
    correct: Mapped[bool]
    reason: Mapped[str]
    add_equivalent: Mapped[bool] = mapped_column(default=False)
    proposed_version_id: Mapped[str | None]
    created_at: Mapped[float] = mapped_column(Float)


class Card(Base):
    __tablename__ = "review_cards"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    state: Mapped[str] = mapped_column(default="new")
    due_at: Mapped[float | None] = mapped_column(Float)
    stage: Mapped[int] = mapped_column(default=0)
    previous_state: Mapped[str | None]


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), unique=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float)


class Plan(Base):
    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("subject_id", "day"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    day: Mapped[str]
    timezone: Mapped[str]
    budget_minutes: Mapped[int | None]
    items: Mapped[list] = mapped_column(JSON, default=list)
    skipped: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(default=1)
    generated_at: Mapped[float] = mapped_column(Float)


class Deferral(Base):
    __tablename__ = "plan_deferrals"
    __table_args__ = (UniqueConstraint("subject_id", "question_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    until: Mapped[str]


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), index=True)
    target_id: Mapped[str]
    actor: Mapped[str]
    action: Mapped[str]
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)


class Job(Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (UniqueConstraint("subject_id", "key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    key: Mapped[str]
    digest: Mapped[str]
    status: Mapped[str]
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
