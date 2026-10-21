import importlib
import os
import logging
from contextlib import contextmanager
from pathlib import Path
from time import time

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from backend.app.models import Job, SchemaVersion, Subject


class Workspace:
    def __init__(self, root=None, clock=None):
        self.root = Path(root or os.environ.get("EXAMPILOT_HOME", Path(__file__).resolve().parents[2])).resolve()
        self.clock = clock or time
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(exist_ok=True)
        self.engine = create_engine(f"sqlite:///{(self.root / 'data/exampilot.sqlite3').as_posix()}", connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        with self.engine.begin() as conn:
            # The first migration owns the schema; subsequent schema changes require a new migration.
            migration = importlib.import_module("backend.app.models.migrations.0001_initial")
            migration.upgrade(conn)
            versions = conn.execute(select(SchemaVersion.version)).scalars().all()
            if not versions:
                conn.execute(SchemaVersion.__table__.insert().values(version=1))
            elif versions != [1]:
                raise RuntimeError("Unsupported database schema. Back up before migrating.")

    @contextmanager
    def service(self, actor="user"):
        from backend.app.services.core import Service
        with Session(self.engine, expire_on_commit=False) as session:
            service = Service(session, self.root, self.clock, actor)
            try:
                # Serialize local writes across API and CLI processes; idempotency checks and effects commit together.
                session.execute(text("BEGIN IMMEDIATE"))
                yield service
                session.commit()
            except Exception as exc:
                session.rollback()
                info = getattr(service, "job_context", None)
                if info:
                    try:
                        with Session(self.engine) as failure:
                            failure.execute(text("BEGIN IMMEDIATE"))
                            audit_service = Service(failure, self.root, self.clock, actor)
                            if failure.get(Subject, info["subject_id"]):
                                jobs = audit_service.rows(Job, Job.subject_id == info["subject_id"], Job.key == info["key"])
                                if not jobs:
                                    audit_service.add(Job(subject_id=info["subject_id"], key=info["key"], digest=info["digest"], status="failed",
                                                          result={"input": info["input"], "inserted": 0, "skipped": 0, "failed": info["input"], "reason": str(exc)}, created_at=float(self.clock())))
                                audit_service.audit(info["subject_id"], info["key"], "import_failed", reason=str(exc))
                            failure.commit()
                    except Exception:
                        logging.getLogger("exampilot").exception("Failed to record import failure after rollback")
                raise
