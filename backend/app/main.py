import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app import schemas as dto
from backend.app.database import Workspace
from backend.app.models import Audit, Job, Source, Subject, Version
from backend.app.services.core import DomainError, digest, record

logger = logging.getLogger("exampilot")


def create_app(root=None, clock=None):
    app = FastAPI(title="ExamPilot", version="0.1.0", description="Local-first exam preparation demo")
    workspace = Workspace(root, clock)
    app.state.workspace = workspace
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    def run(method, *args, **kwargs):
        with workspace.service() as service:
            return getattr(service, method)(*args, **kwargs)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {str(request.base_url).rstrip("/"), "http://127.0.0.1:5173", "http://localhost:5173"}:
            return JSONResponse({"detail": "仅允许本机应用来源访问业务接口"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(DomainError)
    async def business_error(request, exc):
        logger.warning("%s %s: %s", request.method, request.url.path, exc.message)
        if request.method not in ("GET", "HEAD"):
            # The failed transaction has already rolled back. Failure audit is a separate transaction.
            try:
                with workspace.service() as service:
                    sid = request.path_params.get("sid")
                    if sid and not service.s.get(Subject, sid):
                        sid = None
                    service.audit(sid, request.url.path, "operation_failed", reason=exc.message)
            except Exception:
                logger.exception("Failed to persist failure audit")
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(ValidationError)
    async def schema_error(request, exc):
        return JSONResponse({"detail": "；".join(str(e["msg"]) for e in exc.errors())}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def request_error(request, exc):
        return JSONResponse({"detail": "；".join(".".join(map(str, e["loc"][1:])) + ": " + e["msg"] for e in exc.errors())}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        logger.warning("Database conflict: %s", type(exc).__name__)
        return JSONResponse({"detail": "数据状态冲突，操作已回滚，请刷新后重试"}, status_code=409)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/dashboard")
    def dashboard():
        return run("dashboard")

    @app.get("/api/settings")
    def settings():
        return run("settings")

    @app.put("/api/settings")
    def settings_update(data: dto.SettingsInput):
        return run("save_settings", data.timezone)

    @app.get("/api/subjects")
    def subjects(archived: bool = False):
        return run("subjects", archived)

    @app.post("/api/subjects", status_code=201)
    def subject_create(data: dto.SubjectInput):
        return run("create_subject", data.model_dump(mode="json"))

    @app.patch("/api/subjects/{sid}")
    def subject_update(sid: str, data: dto.SubjectPatch):
        return run("update_subject", sid, data.model_dump(mode="json", exclude_unset=True))

    @app.post("/api/subjects/{sid}/archive")
    def subject_archive(sid: str):
        return run("archive_container", sid)

    @app.get("/api/subjects/{sid}/chapters")
    def chapters(sid: str):
        return run("chapters", sid)

    @app.post("/api/subjects/{sid}/chapters", status_code=201)
    def chapter_create(sid: str, data: dto.ChapterInput):
        return run("create_chapter", sid, data.model_dump())

    @app.patch("/api/subjects/{sid}/chapters/{cid}")
    def chapter_update(sid: str, cid: str, data: dto.ChapterInput):
        return run("update_chapter", sid, cid, data.model_dump())

    @app.post("/api/subjects/{sid}/chapters/{cid}/archive")
    def chapter_archive(sid: str, cid: str):
        return run("archive_container", sid, cid)

    @app.get("/api/subjects/{sid}/sources")
    def sources(sid: str, chapter_id: str | None = None):
        return run("sources", sid, chapter_id)

    @app.post("/api/subjects/{sid}/sources", status_code=201)
    def source_upload(sid: str, chapter_id: str, file: UploadFile = File(...)):
        data = file.file.read(50 * 1024 * 1024 + 1)
        return run("upload_pdf", sid, chapter_id, file.filename or "source.pdf", data)

    @app.get("/api/subjects/{sid}/sources/{source_id}")
    def source_text(sid: str, source_id: str):
        with workspace.service() as service:
            source = service.scoped(Source, source_id, sid)
            return service.source_data(source, include_text=True)

    @app.get("/api/subjects/{sid}/sources/{source_id}/file")
    def source_file(sid: str, source_id: str):
        with workspace.service() as service:
            source = service.scoped(Source, source_id, sid)
            path, filename = service.source_path(source), source.filename
        return FileResponse(path, media_type="application/pdf", filename=filename, content_disposition_type="inline")

    @app.get("/api/subjects/{sid}/knowledge")
    def knowledge(sid: str, chapter_id: str | None = None):
        return run("knowledge", sid, chapter_id)

    @app.post("/api/subjects/{sid}/knowledge", status_code=201)
    def knowledge_import(sid: str, data: dto.KnowledgeInput):
        return run("import_knowledge", sid, data.model_dump())

    @app.get("/api/subjects/{sid}/questions")
    def questions(sid: str, chapter_id: str | None = None, kind: str | None = None, status: str | None = None, knowledge_id: str | None = None):
        return run("questions", sid, chapter_id, kind, status, knowledge_id)

    @app.get("/api/subjects/{sid}/practice")
    def practice(sid: str, chapter_id: str | None = None, kind: str | None = None, knowledge_id: str | None = None, limit: int = Query(default=20, ge=1, le=100), version_id: str | None = None):
        if version_id:
            with workspace.service() as service:
                service.scoped(Version, version_id, sid, chapter_id)
        values = run("questions", sid, chapter_id, kind, None, knowledge_id, practice=True)
        return [v for v in values if not version_id or v["id"] == version_id][:limit]

    @app.get("/api/subjects/{sid}/questions/{vid}")
    def question_detail(sid: str, vid: str):
        with workspace.service() as service:
            return service.version_data(service.scoped(Version, vid, sid))

    @app.post("/api/subjects/{sid}/questions/import")
    def questions_import(sid: str, data: dto.ImportInput):
        return run("import_questions", sid, data.model_dump())

    @app.post("/api/subjects/{sid}/questions/{vid}/revise")
    def question_revise(sid: str, vid: str, data: dto.QuestionInput):
        return run("revise", sid, vid, data.model_dump())

    @app.get("/api/subjects/{sid}/questions/{vid}/audit")
    def question_audit(sid: str, vid: str):
        with workspace.service() as service:
            service.scoped(Version, vid, sid)
            return [record(a) for a in sorted(service.rows(Audit, Audit.subject_id == sid, Audit.target_id == vid), key=lambda a: (a.created_at, a.id))]

    @app.post("/api/subjects/{sid}/review")
    def review(sid: str, data: dto.ReviewInput):
        return run("review", sid, data.model_dump())

    @app.get("/api/subjects/{sid}/attempts")
    def attempts(sid: str):
        return run("attempts", sid)

    @app.post("/api/subjects/{sid}/attempts")
    def submit(sid: str, data: dto.AttemptInput):
        return run("submit", sid, data.model_dump())

    @app.post("/api/subjects/{sid}/attempts/{aid}/resolve")
    def resolve(sid: str, aid: str, data: dto.ResolveInput):
        return run("resolve", sid, aid, data.model_dump())

    @app.get("/api/subjects/{sid}/mistakes")
    def mistakes(sid: str, view: str = "current", chapter_id: str | None = None, knowledge_id: str | None = None):
        return run("mistakes", sid, view, chapter_id, knowledge_id)

    @app.get("/api/subjects/{sid}/cards")
    def cards(sid: str):
        return run("cards", sid)

    @app.post("/api/subjects/{sid}/cards/{qid}/pause")
    def pause(sid: str, qid: str, data: dto.PauseInput):
        return run("pause", sid, qid, data.paused)

    @app.post("/api/subjects/{sid}/plan")
    def plan(sid: str, data: dto.PlanInput):
        return run("plan", sid, data.replan)

    @app.get("/api/subjects/{sid}/plans")
    def plans(sid: str):
        return run("plan_history", sid)

    @app.post("/api/subjects/{sid}/plan/items/{item_id}")
    def plan_edit(sid: str, item_id: str, data: dto.PlanEdit):
        return run("edit_plan", sid, item_id, data.model_dump(mode="json"))

    @app.get("/api/subjects/{sid}/report")
    def report(sid: str):
        return run("subject_stats", sid)

    @app.get("/api/subjects/{sid}/jobs")
    def jobs(sid: str):
        with workspace.service() as service:
            service.subject(sid, active=False)
            return [record(j) for j in service.rows(Job, Job.subject_id == sid)]

    @app.get("/api/subjects/{sid}/audit")
    def audits(sid: str):
        with workspace.service() as service:
            service.subject(sid, active=False)
            return [record(a) for a in sorted(service.rows(Audit, Audit.subject_id == sid), key=lambda a: a.created_at, reverse=True)[:100]]

    # A built frontend is served from the same origin; no CDN is needed during ordinary use.
    frontend = Path(__file__).resolve().parents[2] / "frontend/dist"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_app(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "接口不存在"}, status_code=404)
        target = (frontend / path).resolve()
        if target.is_relative_to(frontend.resolve()) and target.is_file():
            return FileResponse(target)
        if (frontend / "index.html").exists():
            return FileResponse(frontend / "index.html")
        return JSONResponse({"detail": "请先在 frontend 执行 npm run build"}, status_code=404)

    return app


app = create_app()
