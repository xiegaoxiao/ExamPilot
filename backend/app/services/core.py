"""Shared transactional business service used by HTTP, CLI and demo initialization."""
import copy
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pypdf import PdfReader, __version__ as pdf_parser_version
from sqlalchemy import func, select

from backend.app import schemas as dto
from backend.app.models import (Attempt, Audit, Card, Chapter, Deferral, Job, Knowledge,
                                Plan, Question, Resolution, ReviewEvent, Setting, Source, Subject, Version, uid)

ESTIMATES = {"single": 2, "multiple": 3, "boolean": 1, "fill": 2}


class DomainError(Exception):
    def __init__(self, message, status=422, **context):
        super().__init__(message)
        self.message, self.status, self.context = message, status, context


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def record(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def normalize_quote(value):
    return "".join(value.split())


class Service:
    def __init__(self, session, root, clock, actor="user"):
        self.s, self.root, self.clock, self.actor = session, root, clock, actor

    @property
    def now(self):
        return float(self.clock())

    def rows(self, cls, *conditions):
        return list(self.s.scalars(select(cls).where(*conditions)))

    def add(self, obj):
        self.s.add(obj)
        self.s.flush()
        return obj

    def audit(self, sid, target, action, **details):
        # Append order is explicit even when a deterministic test clock gives several actions the same time.
        sequence = self.s.scalar(select(func.count()).select_from(Audit))
        return self.add(Audit(id=f"{sequence:020d}", subject_id=sid, target_id=target, actor=self.actor, action=action, details=details, created_at=self.now))

    def subject(self, sid, active=True):
        subject = self.s.get(Subject, sid)
        if not subject:
            raise DomainError("科目不存在", 404)
        if active and subject.archived:
            raise DomainError("科目已归档，仅可查询历史", 409)
        return subject

    def scoped(self, cls, obj_id, sid, chapter_id=None):
        self.subject(sid, active=False)
        obj = self.s.get(cls, obj_id)
        if not obj or obj.subject_id != sid or (chapter_id and getattr(obj, "chapter_id", obj.id) != chapter_id):
            raise DomainError("对象不存在或不属于当前科目/章节", 404)
        return obj

    def active_chapter(self, sid, cid):
        self.subject(sid)
        chapter = self.scoped(Chapter, cid, sid)
        if chapter.archived:
            raise DomainError("章节已归档", 409)
        return chapter

    def settings(self):
        zone = self.s.get(Setting, "timezone")
        return {"timezone": zone.value if zone else "Asia/Shanghai", "data_path": str(self.root / "data"),
                "workspace_path": str(self.root / "workspace"), "schema_version": 1,
                "demo_policies": {"weakness": "临时规则：近30天至少3次已判作答且正确率低于70%；不代表正式D-23决策", "limits": "Demo：名称80字符，PDF 50MiB/500页，预算0–240分钟，单次练习100题"}}

    def save_settings(self, timezone_name):
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise DomainError("请输入有效 IANA 时区，例如 Asia/Shanghai")
        item = self.s.get(Setting, "timezone")
        if item:
            item.value = timezone_name
        else:
            self.add(Setting(key="timezone", value=timezone_name))
        self.audit(None, "settings", "timezone", value=timezone_name)
        return self.settings()

    def local_day(self, timestamp=None):
        return datetime.fromtimestamp(timestamp if timestamp is not None else self.now, ZoneInfo(self.settings()["timezone"])).date().isoformat()

    def create_subject(self, data):
        data = dto.SubjectInput.model_validate(data).model_dump(mode="json")
        subject = self.add(Subject(**data))
        self.audit(subject.id, subject.id, "create_subject")
        return record(subject)

    def update_subject(self, sid, data):
        subject = self.subject(sid)
        values = dto.SubjectPatch.model_validate(data).model_dump(mode="json", exclude_unset=True)
        if "name" in values:
            if not values["name"] or not values["name"].strip():
                raise DomainError("名称不能为空")
            values["name"] = values["name"].strip()
        for key, value in values.items():
            setattr(subject, key, value)
        self.audit(sid, sid, "update_subject", changes=values)
        return record(subject)

    def subjects(self, archived=False):
        return [self.subject_stats(s.id) for s in self.rows(Subject, Subject.archived == archived)]

    def chapters(self, sid):
        self.subject(sid, active=False)
        return [record(c) for c in sorted(self.rows(Chapter, Chapter.subject_id == sid), key=lambda c: (c.position, c.id))]

    def create_chapter(self, sid, data):
        self.subject(sid)
        values = dto.ChapterInput.model_validate(data).model_dump()
        if not values["name"].strip():
            raise DomainError("章节名称不能为空")
        values["name"] = values["name"].strip()
        c = self.add(Chapter(subject_id=sid, position=len(self.chapters(sid)), **values))
        self.audit(sid, c.id, "create_chapter")
        return record(c)

    def update_chapter(self, sid, cid, data):
        c = self.active_chapter(sid, cid)
        values = dto.ChapterInput.model_validate(data).model_dump()
        if not values["name"].strip():
            raise DomainError("章节名称不能为空")
        c.name, c.exam_focus = values["name"].strip(), values["exam_focus"]
        self.audit(sid, cid, "update_chapter", changes=values)
        return record(c)

    def archive_container(self, sid, cid=None):
        subject = self.subject(sid)
        target = self.scoped(Chapter, cid, sid) if cid else subject
        target.archived = True
        self.audit(sid, target.id, "archive_chapter" if cid else "archive_subject")
        return record(target)

    def source_path(self, source):
        path = (self.root / source.path).resolve()
        allowed = (self.root / "workspace/subjects" / source.subject_id / "sources").resolve()
        if not path.is_relative_to(allowed) or not path.is_file():
            raise DomainError("原 PDF 缺失或文件路径越出科目资料目录", 409)
        return path

    def upload_pdf(self, sid, cid, filename, content):
        self.active_chapter(sid, cid)
        if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF-"):
            raise DomainError("仅支持有效 PDF 文件")
        if len(content) > 50 * 1024 * 1024:
            raise DomainError("PDF 超过 Demo 的50MiB限制", 413)
        sha = hashlib.sha256(content).hexdigest()
        old = self.rows(Source, Source.subject_id == sid, Source.chapter_id == cid, Source.sha256 == sha)
        if old:
            return self.source_data(old[0])
        try:
            with PdfReader(io.BytesIO(content)) as document:
                if document.is_encrypted:
                    raise DomainError("加密 PDF 暂不支持，请先提供可读取版本")
                if not 0 < len(document.pages) <= 500:
                    raise DomainError("PDF 页数须为1–500（Demo限制）")
                pages = [page.extract_text() or "" for page in document.pages]
        except DomainError:
            raise
        except Exception as error:
            raise DomainError("PDF 损坏或无法解析") from error
        if not any(p.strip() for p in pages):
            raise DomainError("未提取到文本，扫描 PDF 需 OCR，Demo 不支持")
        relative = Path("workspace/subjects") / sid / "sources" / (sha + ".pdf")
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise DomainError("同路径已有不同内容，拒绝覆盖原件", 409)
        if not path.exists():
            path.write_bytes(content)
        source = self.add(Source(subject_id=sid, chapter_id=cid, filename=Path(filename.replace("\\", "/")).name,
                                 sha256=sha, path=relative.as_posix(), pages=pages,
                                 status="ready" if all(p.strip() for p in pages) else "partial",
                                 parser_version=f"pypdf-{pdf_parser_version}", created_at=self.now))
        self.audit(sid, source.id, "import_pdf", sha256=sha, pages=len(pages))
        return self.source_data(source)

    def source_data(self, source, include_text=False):
        data = record(source)
        data["page_count"] = len(source.pages)
        data["unavailable_pages"] = [i + 1 for i, p in enumerate(source.pages) if not p.strip()]
        if not include_text:
            data.pop("pages")
        data.pop("path")
        return data

    def sources(self, sid, chapter_id=None):
        self.subject(sid, active=False)
        if chapter_id:
            self.scoped(Chapter, chapter_id, sid)
        return [self.source_data(s) for s in self.rows(Source, Source.subject_id == sid) if not chapter_id or s.chapter_id == chapter_id]

    def evidence_issues(self, sid, cid, evidence):
        errors = []
        if not evidence:
            return ["缺少可核验 PDF 来源证据"]
        for e in evidence:
            try:
                source = self.scoped(Source, e["source_id"], sid, cid)
            except DomainError as error:
                raise DomainError("来源不属于目标科目/章节，整批拒绝") from error
            if not 1 <= e["page"] <= len(source.pages) or not source.pages[e["page"] - 1].strip():
                errors.append("PDF 物理页码无效或该页无可提取文本")
                continue
            if normalize_quote(e["quote"]) not in normalize_quote(source.pages[e["page"] - 1]):
                errors.append("证据片段无法在指定 PDF 页核验")
            try:
                if hashlib.sha256(self.source_path(source).read_bytes()).hexdigest() != source.sha256:
                    errors.append("原 PDF 内容摘要不一致")
            except DomainError:
                errors.append("原 PDF 文件缺失")
        return errors

    def import_knowledge(self, sid, data):
        value = dto.KnowledgeInput.model_validate(data).model_dump()
        self.active_chapter(sid, value["chapter_id"])
        evidence = {k: value[k] for k in ("source_id", "page", "quote")}
        issues = self.evidence_issues(sid, value["chapter_id"], [evidence])
        if issues:
            raise DomainError("；".join(issues))
        name = value["name"].strip()
        if not name:
            raise DomainError("知识点名称不能为空")
        existing = self.rows(Knowledge, Knowledge.subject_id == sid, Knowledge.chapter_id == value["chapter_id"], Knowledge.name == name)
        if existing:
            return record(existing[0])
        knowledge = self.add(Knowledge(subject_id=sid, chapter_id=value["chapter_id"], name=name, evidence=evidence))
        self.audit(sid, knowledge.id, "import_knowledge")
        return record(knowledge)

    def knowledge(self, sid, chapter_id=None):
        self.subject(sid, active=False)
        if chapter_id:
            self.scoped(Chapter, chapter_id, sid)
        return [record(k) for k in self.rows(Knowledge, Knowledge.subject_id == sid) if not chapter_id or k.chapter_id == chapter_id]

    def validate_content(self, sid, content):
        cid = content["chapter_id"]
        self.active_chapter(sid, cid)
        for kid in content["knowledge_ids"]:
            try:
                self.scoped(Knowledge, kid, sid, cid)
            except DomainError as error:
                raise DomainError("知识点不属于目标科目/章节，整批拒绝") from error
        issues = self.evidence_issues(sid, cid, content["evidence"])
        if not content["knowledge_ids"]:
            issues.append("至少关联一个本科目章节知识点")
        if not content["explanation"].strip():
            issues.append("缺少可核验解析")
        if content["uncertain"]:
            issues.append("答案或解析存在歧义，请修订后重审")
        return issues

    def import_questions(self, sid, data):
        batch = dto.ImportInput.model_validate(data).model_dump()
        self.job_context = {"subject_id": sid, "key": batch["key"],
                            "digest": digest(batch["questions"]), "input": len(batch["questions"])}
        return self._import_questions(sid, batch)

    def _import_questions(self, sid, data):
        self.subject(sid)
        batch = dto.ImportInput.model_validate(data).model_dump()
        fingerprint = digest(batch["questions"])
        existing_job = self.rows(Job, Job.subject_id == sid, Job.key == batch["key"])
        if existing_job:
            if existing_job[0].digest != fingerprint:
                raise DomainError("相同幂等键对应不同内容", 409)
            if existing_job[0].status == "completed":
                return existing_job[0].result
        # Validate all references before adding anything. A bad reference invalidates the whole batch.
        checks = [self.validate_content(sid, q) for q in batch["questions"]]
        results, skipped, pending = [], 0, 0
        for content, issues in zip(batch["questions"], checks):
            fp = digest(content)
            duplicate = self.rows(Version, Version.subject_id == sid, Version.fingerprint == fp)
            if duplicate:
                results.append(self.version_data(duplicate[0]))
                skipped += 1
                continue
            candidates = self.rows(Version, Version.subject_id == sid, Version.chapter_id == content["chapter_id"])
            if any(SequenceMatcher(None, content["stem"], v.content["stem"]).ratio() >= .94 for v in candidates):
                issues = issues + ["疑似近似重题，请人工核对并修订题干"]
            question = self.add(Question(subject_id=sid, chapter_id=content["chapter_id"]))
            v = self.add(Version(question_id=question.id, subject_id=sid, chapter_id=content["chapter_id"],
                                 content=content, fingerprint=fp, status="draft", issues=[], created_at=self.now))
            self.audit(sid, v.id, "import_draft")
            v.status = "validating"
            self.audit(sid, v.id, "validate", issues=issues)
            # Even a clean automated check needs a real human approval.
            v.status, v.issues = "needs_review", issues
            results.append(self.version_data(v))
            pending += 1
        result = {"input": len(batch["questions"]), "inserted": len(batch["questions"]) - skipped,
                  "skipped": skipped, "needs_review": pending, "failed": 0, "questions": results}
        if existing_job:
            existing_job[0].status, existing_job[0].result = "completed", result
        else:
            self.add(Job(subject_id=sid, key=batch["key"], digest=fingerprint, status="completed", result=result, created_at=self.now))
        self.audit(sid, batch["key"], "import_batch", input=result["input"], inserted=result["inserted"], skipped=skipped)
        return result

    def version_data(self, version, reveal=True):
        data = {**record(version), **copy.deepcopy(version.content)}
        data.pop("content")
        data.pop("fingerprint")
        question = self.s.get(Question, version.question_id)
        chapter = self.s.get(Chapter, version.chapter_id)
        subject = self.s.get(Subject, version.subject_id)
        data["active"] = version.status == "published" and question.current_version_id == version.id and not chapter.archived and not subject.archived
        data["chapter_name"] = chapter.name
        data["knowledge"] = [record(k) for k in (self.s.get(Knowledge, kid) for kid in version.content["knowledge_ids"]) if k]
        for e in data["evidence"]:
            source = self.s.get(Source, e["source_id"])
            e["filename"] = source.filename if source else "来源缺失"
        if not reveal:
            for key in ("answer", "explanation", "issues", "uncertain", "evidence"):
                data.pop(key, None)
        return data

    def questions(self, sid, chapter_id=None, kind=None, status=None, knowledge_id=None, practice=False):
        self.subject(sid, active=practice)
        if chapter_id:
            self.scoped(Chapter, chapter_id, sid)
        if knowledge_id:
            self.scoped(Knowledge, knowledge_id, sid)
        versions = self.rows(Version, Version.subject_id == sid)
        values = []
        for v in versions:
            if chapter_id and v.chapter_id != chapter_id or kind and v.content["kind"] != kind or status and v.status != status or knowledge_id and knowledge_id not in v.content["knowledge_ids"]:
                continue
            data = self.version_data(v, reveal=not practice)
            if practice and not data["active"]:
                continue
            values.append(data)
        return sorted(values, key=lambda q: (q["created_at"], q["id"]))

    def review(self, sid, data):
        value = dto.ReviewInput.model_validate(data)
        self.subject(sid)
        versions = [self.scoped(Version, vid, sid) for vid in dict.fromkeys(value.ids)]
        if self.actor != "user" and value.action in ("approve", "publish"):
            raise DomainError("批准和发布必须由用户明确执行；Codex 只能提交校验建议", 403)
        for v in versions:
            self.active_chapter(sid, v.chapter_id)
            if value.action in ("validate", "approve", "publish"):
                issues = self.validate_content(sid, v.content)
                # Near-duplicate warnings remain blocking until revised, rather than disappearing on revalidation.
                issues += [i for i in v.issues if "重题" in i]
                if issues and value.action != "validate":
                    raise DomainError("硬性校验未通过：" + "；".join(issues), 409)
            if value.action == "approve" and v.status != "needs_review":
                raise DomainError("仅待审核题可批准", 409)
            if value.action == "publish" and v.status != "approved":
                raise DomainError("必须先人工批准，再独立发布", 409)
            if value.action == "reject" and v.status not in ("draft", "needs_review", "approved"):
                raise DomainError("当前状态不能拒绝", 409)
            if value.action == "validate" and v.status not in ("draft", "needs_review", "rejected"):
                raise DomainError("当前状态不可重新校验，请创建修订版本", 409)
        for v in versions:
            before = v.status
            if value.action == "validate":
                v.issues = self.validate_content(sid, v.content) + [i for i in v.issues if "重题" in i]
                v.status = "needs_review"
            elif value.action == "publish":
                question = self.s.get(Question, v.question_id)
                if question.current_version_id and question.current_version_id != v.id:
                    old = self.s.get(Version, question.current_version_id)
                    old.status = "archived"
                    self.audit(sid, old.id, "superseded", by=v.id)
                    card = self.s.get(Card, question.id)
                    if card and v.semantic_change:
                        prior = record(card)
                        if card.state == "suspended":
                            card.previous_state, card.stage = "relearning", 0
                        else:
                            card.state, card.stage = "relearning", 0
                        card.due_at = self.now + 600
                        self.audit(sid, question.id, "card_version_migration", before=prior, after=record(card))
                question.current_version_id = v.id
                v.status = "published"
            else:
                v.status = {"approve": "approved", "reject": "rejected", "archive": "archived"}[value.action]
            self.audit(sid, v.id, value.action, version=v.version, before=before, after=v.status, reason=value.reason)
        return [self.version_data(v) for v in versions]

    def revise(self, sid, vid, content, semantic_change=True):
        old = self.scoped(Version, vid, sid)
        data = dto.QuestionInput.model_validate(content).model_dump()
        if data["chapter_id"] != old.chapter_id:
            raise DomainError("修订不可迁移章节或科目")
        issues = self.validate_content(sid, data)
        number = max(v.version for v in self.rows(Version, Version.question_id == old.question_id)) + 1
        v = self.add(Version(question_id=old.question_id, subject_id=sid, chapter_id=old.chapter_id, version=number,
                             content=data, fingerprint=digest(data), status="needs_review", issues=issues,
                             semantic_change=semantic_change, created_at=self.now))
        self.audit(sid, v.id, "revise", previous=old.id, semantic_change=semantic_change)
        return self.version_data(v)

    def result(self, attempt):
        resolution = self.rows(Resolution, Resolution.attempt_id == attempt.id)
        return ("correct" if resolution[0].correct else "incorrect") if resolution else attempt.initial_result

    def attempt_data(self, attempt):
        v = self.s.get(Version, attempt.version_id)
        data = record(attempt)
        data.update(result=self.result(attempt), standard_answer=v.content["answer"], question=self.version_data(v),
                    stem=v.content["stem"], kind=v.content["kind"])
        resolutions = self.rows(Resolution, Resolution.attempt_id == attempt.id)
        data["resolution"] = record(resolutions[0]) if resolutions else None
        return data

    def attempts(self, sid):
        self.subject(sid, active=False)
        return [self.attempt_data(a) for a in sorted(self.rows(Attempt, Attempt.subject_id == sid), key=lambda a: a.created_at, reverse=True)]

    def grade(self, content, answer):
        kind = content["kind"]
        ids = {o["id"] for o in content["options"]}
        if kind == "single":
            if not isinstance(answer, str) or answer not in ids:
                raise DomainError("请选择一个有效选项")
            correct = answer == content["answer"]
        elif kind == "multiple":
            if not isinstance(answer, list) or not answer or not all(isinstance(a, str) for a in answer) or len(set(answer)) != len(answer) or not set(answer) <= ids:
                raise DomainError("多选提交须为非空、无重复的有效选项集合")
            correct = set(answer) == set(content["answer"])
        elif kind == "boolean":
            if type(answer) is not bool:
                raise DomainError("判断题必须提交布尔值")
            correct = answer == content["answer"]
        else:
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 200:
                raise DomainError("填空需1–200字符的短文本")
            return "correct" if answer.strip() in {a.strip() for a in content["answer"]} else "pending_review"
        return "correct" if correct else "incorrect"

    def submit(self, sid, data):
        self.subject(sid)
        value = dto.AttemptInput.model_validate(data).model_dump()
        fp = digest(value)
        previous = self.rows(Attempt, Attempt.subject_id == sid, Attempt.request_id == value["request_id"])
        if previous:
            if previous[0].request_digest != fp:
                raise DomainError("同一作答幂等标识不能用于不同答案", 409)
            return self.attempt_data(previous[0])
        v = self.scoped(Version, value["version_id"], sid)
        if not self.version_data(v)["active"]:
            raise DomainError("该版本未发布或已失效，请换题", 409)
        result = self.grade(v.content, value["answer"])
        attempt = self.add(Attempt(subject_id=sid, version_id=v.id, question_id=v.question_id,
                                   request_id=value["request_id"], request_digest=fp, answer=value["answer"],
                                   initial_result=result, elapsed_seconds=value["elapsed_seconds"], created_at=self.now))
        if result != "pending_review":
            self.settle(attempt, result == "correct")
        self.audit(sid, attempt.id, "attempt", result=result, version_id=v.id)
        return self.attempt_data(attempt)

    def settle(self, attempt, correct):
        if self.rows(ReviewEvent, ReviewEvent.attempt_id == attempt.id):
            return
        v = self.s.get(Version, attempt.version_id)
        if not self.version_data(v)["active"]:
            self.audit(attempt.subject_id, attempt.id, "settlement_history_only", reason="版本已失效，仅确认历史，不推进当前卡片")
            return
        card = self.s.get(Card, attempt.question_id)
        if not card:
            card = self.add(Card(question_id=attempt.question_id, subject_id=attempt.subject_id))
        before = record(card)
        if card.state != "suspended":
            if not correct:
                card.state, card.stage, interval = "relearning", 0, 600
            elif card.state in ("new", "relearning"):
                card.state, card.stage, interval = "learning", 0, 86400
            elif card.state == "learning":
                card.state, card.stage, interval = "review", 0, 259200
            else:
                interval = 604800 if card.stage == 0 else 1209600
                card.stage = min(card.stage + 1, 2)
            card.due_at = self.now + interval
        self.add(ReviewEvent(attempt_id=attempt.id, subject_id=attempt.subject_id, before=before, after=record(card), created_at=self.now))
        plans = self.rows(Plan, Plan.subject_id == attempt.subject_id, Plan.day == self.local_day())
        for plan in plans:
            items = copy.deepcopy(plan.items)
            changed = False
            for item in items:
                if item["version_id"] == attempt.version_id and item["status"] == "pending":
                    item.update(status="completed", attempt_id=attempt.id, completed_at=self.now)
                    changed = True
            if changed:
                plan.items = items
                self.audit(attempt.subject_id, plan.id, "plan_complete", attempt_id=attempt.id)

    def resolve(self, sid, aid, data):
        self.subject(sid, active=False)
        value = dto.ResolveInput.model_validate(data)
        if self.actor != "user":
            raise DomainError("填空复核结论须由用户确认", 403)
        attempt = self.scoped(Attempt, aid, sid)
        previous = self.rows(Resolution, Resolution.attempt_id == aid)
        if previous:
            if (previous[0].correct, previous[0].reason, previous[0].add_equivalent) != (value.correct, value.reason, value.add_equivalent):
                raise DomainError("该作答已复核，禁止覆盖既有结论", 409)
            return self.attempt_data(attempt)
        if attempt.initial_result != "pending_review":
            raise DomainError("仅待复核填空可复核", 409)
        proposed = None
        if value.add_equivalent:
            if not value.correct:
                raise DomainError("仅确认正确时可提议添加等价答案")
            v = self.s.get(Version, attempt.version_id)
            content = copy.deepcopy(v.content)
            content["answer"] = list(dict.fromkeys(content["answer"] + [attempt.answer.strip()]))
            proposed = self.revise(sid, v.id, content, semantic_change=False)["id"]
        self.add(Resolution(attempt_id=aid, correct=value.correct, reason=value.reason, add_equivalent=value.add_equivalent,
                            proposed_version_id=proposed, created_at=self.now))
        self.settle(attempt, value.correct)
        self.audit(sid, aid, "resolve", correct=value.correct, reason=value.reason, proposed_version_id=proposed)
        return self.attempt_data(attempt)

    def cards(self, sid):
        self.subject(sid, active=False)
        return [record(c) for c in self.rows(Card, Card.subject_id == sid)]

    def pause(self, sid, qid, paused):
        self.scoped(Question, qid, sid)
        card = self.s.get(Card, qid)
        if not card:
            card = self.add(Card(subject_id=sid, question_id=qid))
        if paused and card.state != "suspended":
            card.previous_state, card.state = card.state, "suspended"
        elif not paused and card.state == "suspended":
            card.state, card.previous_state = card.previous_state or "new", None
        self.audit(sid, qid, "pause" if paused else "resume", card=record(card))
        return record(card)

    def mistakes(self, sid, view="current", chapter_id=None, knowledge_id=None):
        self.subject(sid, active=False)
        if chapter_id:
            self.scoped(Chapter, chapter_id, sid)
        if knowledge_id:
            self.scoped(Knowledge, knowledge_id, sid)
        if view in ("history", "pending", "attempts"):
            return [a for a in self.attempts(sid) if (view == "attempts" or a["result"] == ("incorrect" if view == "history" else "pending_review"))
                    and (not chapter_id or a["question"]["chapter_id"] == chapter_id)
                    and (not knowledge_id or knowledge_id in a["question"]["knowledge_ids"])]
        if view not in ("current", "future", "suspended"):
            raise DomainError("未知错题视图")
        out = []
        for card in self.rows(Card, Card.subject_id == sid):
            question = self.s.get(Question, card.question_id)
            if not question.current_version_id:
                continue
            v = self.s.get(Version, question.current_version_id)
            data = self.version_data(v)
            if not data["active"] or chapter_id and v.chapter_id != chapter_id or knowledge_id and knowledge_id not in v.content["knowledge_ids"]:
                continue
            due = card.due_at is not None and card.due_at <= self.now
            if view == "suspended" and card.state == "suspended" or view == "current" and card.state != "suspended" and due or view == "future" and card.state not in ("new", "suspended") and not due:
                out.append({**data, "card": record(card)})
        return out

    def weak_knowledge(self, sid):
        # Demo-only D-23 policy: explicit in Settings and docs, never written as a product approval.
        stats = {}
        for a in self.rows(Attempt, Attempt.subject_id == sid, Attempt.created_at >= self.now - 30 * 86400):
            result = self.result(a)
            if result == "pending_review":
                continue
            for kid in self.s.get(Version, a.version_id).content["knowledge_ids"]:
                counts = stats.setdefault(kid, [0, 0])
                counts[0] += 1
                counts[1] += result == "correct"
        return {kid for kid, (total, correct) in stats.items() if total >= 3 and correct / total < .7}

    def plan_data(self, plan):
        data = record(plan)
        data["items"] = copy.deepcopy(plan.items)
        for item in data["items"]:
            v = self.s.get(Version, item["version_id"])
            item["active"] = bool(v and self.version_data(v)["active"])
        data["minutes"] = sum(i["minutes"] for i in data["items"] if i["status"] in ("pending", "completed"))
        return data

    def plan(self, sid, replan=False):
        subject = self.subject(sid)
        day = self.local_day()
        existing = self.rows(Plan, Plan.subject_id == sid, Plan.day == day)
        plan = existing[0] if existing else None
        if plan and not replan:
            return self.plan_data(plan)
        retained = [copy.deepcopy(i) for i in plan.items if i["status"] in ("completed", "deferred", "removed")] if plan else []
        # A completed task remains history. A later due event may legitimately add a second task that day.
        used_ids = {i["question_id"] for i in retained if i["status"] != "completed"}
        used = sum(i["minutes"] for i in retained if i["status"] == "completed")
        weak = self.weak_knowledge(sid)
        cards = {c.question_id: c for c in self.rows(Card, Card.subject_id == sid)}
        deferrals = {d.question_id: d.until for d in self.rows(Deferral, Deferral.subject_id == sid)}
        pending = {a.question_id for a in self.rows(Attempt, Attempt.subject_id == sid) if self.result(a) == "pending_review"}
        chapters = {c.id: c for c in self.rows(Chapter, Chapter.subject_id == sid)}
        days = (date.fromisoformat(subject.exam_date) - date.fromisoformat(day)).days if subject.exam_date else None
        sprint = days is not None and 0 <= days <= 7
        candidates, skipped = [], []
        for v in self.rows(Version, Version.subject_id == sid):
            if not self.version_data(v)["active"] or v.question_id in used_ids:
                continue
            card = cards.get(v.question_id)
            if card and card.state == "suspended":
                continue
            if v.question_id in pending:
                skipped.append({"version_id": v.id, "stem": v.content["stem"], "reason": "pending_review"})
                continue
            if v.question_id in deferrals and deferrals[v.question_id] > day:
                skipped.append({"version_id": v.id, "stem": v.content["stem"], "reason": "deferred", "until": deferrals[v.question_id]})
                continue
            if card and card.state != "new":
                if card.due_at is None or card.due_at > self.now:
                    continue
                tier, due = 0, card.due_at
            else:
                tier, due = (1 if weak.intersection(v.content["knowledge_ids"]) else 2), 0
            chapter = chapters[v.chapter_id]
            # Exact due time remains the first tie-break for due items. Focus never promotes a lower tier.
            focus = 0 if sprint and chapter.exam_focus else 1
            candidates.append(((tier, due, focus, chapter.position, v.created_at, v.id), v))
        for order, v in sorted(candidates, key=lambda row: row[0]):
            minutes = ESTIMATES[v.content["kind"]]
            if not subject.budget_minutes or used + minutes > subject.budget_minutes:
                skipped.append({"version_id": v.id, "stem": v.content["stem"], "reason": "budget" if subject.budget_minutes is not None else "budget_not_set", "minutes": minutes})
                continue
            retained.append({"id": uid(), "question_id": v.question_id, "version_id": v.id, "stem": v.content["stem"],
                             "kind": v.content["kind"], "minutes": minutes, "priority": ["due", "weak_new", "new"][order[0]], "status": "pending"})
            used += minutes
        if plan:
            self.audit(sid, plan.id, "replan", before=record(plan))
            plan.items, plan.skipped, plan.budget_minutes = retained, skipped, subject.budget_minutes
            plan.revision += 1
            plan.generated_at = self.now
        else:
            plan = self.add(Plan(subject_id=sid, day=day, timezone=self.settings()["timezone"], budget_minutes=subject.budget_minutes,
                                 items=retained, skipped=skipped, generated_at=self.now))
            self.audit(sid, plan.id, "generate_plan", sprint=sprint, rule="fixed-v1")
        return self.plan_data(plan)

    def edit_plan(self, sid, item_id, data):
        value = dto.PlanEdit.model_validate(data)
        plans = self.rows(Plan, Plan.subject_id == sid, Plan.day == self.local_day())
        if not plans:
            raise DomainError("今日计划不存在", 404)
        plan = plans[0]
        items = copy.deepcopy(plan.items)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            raise DomainError("计划项不存在或不属于当前科目", 404)
        if item["status"] == "completed":
            raise DomainError("已完成项保留作答历史，不可移除", 409)
        old = self.rows(Deferral, Deferral.subject_id == sid, Deferral.question_id == item["question_id"])
        if value.action == "restore":
            if not self.version_data(self.s.get(Version, item["version_id"]))["active"]:
                raise DomainError("题目版本已失效", 409)
            current_minutes = sum(i["minutes"] for i in items if i["status"] in ("pending", "completed") and i["id"] != item_id)
            if current_minutes + item["minutes"] > (plan.budget_minutes or 0):
                raise DomainError("恢复会超过当日预算，请先明确调整预算并重新规划", 409)
            item["status"] = "pending"
            if old:
                self.s.delete(old[0])
        else:
            until = value.until.isoformat() if value.until else (date.fromisoformat(plan.day) + timedelta(days=1)).isoformat()
            if until <= plan.day:
                raise DomainError("延期日期必须晚于今日")
            item.update(status="deferred" if value.action == "defer" else "removed", until=until)
            if old:
                old[0].until = until
            else:
                self.add(Deferral(subject_id=sid, question_id=item["question_id"], until=until))
        plan.items = items
        self.audit(sid, plan.id, "edit_plan", item_id=item_id, edit_action=value.action, until=item.get("until"))
        return self.plan_data(plan)

    def plan_history(self, sid):
        self.subject(sid, active=False)
        return [self.plan_data(p) for p in sorted(self.rows(Plan, Plan.subject_id == sid), key=lambda p: p.day, reverse=True)]

    def subject_stats(self, sid):
        subject = self.subject(sid, active=False)
        data = record(subject)
        versions = self.rows(Version, Version.subject_id == sid)
        active = [v for v in versions if self.version_data(v)["active"]]
        attempts = self.rows(Attempt, Attempt.subject_id == sid)
        graded = [a for a in attempts if self.result(a) != "pending_review"]
        correct = sum(self.result(a) == "correct" for a in graded)
        card_rows = self.rows(Card, Card.subject_id == sid)
        active_ids = {v.question_id for v in active}
        active_version_ids = {v.id for v in active}
        data.update(published=len(active), needs_review=sum(v.status == "needs_review" for v in versions),
                    approved=sum(v.status == "approved" for v in versions), chapters=len(self.chapters(sid)),
                    sources=len(self.rows(Source, Source.subject_id == sid)), knowledge=len(self.rows(Knowledge, Knowledge.subject_id == sid)),
                    attempts=len(attempts), correct=correct, graded=len(graded), accuracy=round(correct / len(graded) * 100) if graded else None,
                    history_wrong=sum(self.result(a) == "incorrect" for a in attempts),
                    pending=sum(self.result(a) == "pending_review" for a in attempts),
                    due=sum(c.question_id in active_ids and c.state != "suspended" and c.due_at is not None and c.due_at <= self.now for c in card_rows),
                    coverage=round(len({a.version_id for a in graded if a.version_id in active_version_ids}) / len(active_version_ids) * 100) if active_version_ids else 0,
                    days_to_exam=(date.fromisoformat(subject.exam_date) - date.fromisoformat(self.local_day())).days if subject.exam_date else None)
        return data

    def dashboard(self):
        subjects = self.subjects()
        plans = [self.plan(s["id"]) for s in subjects]
        latest = []
        activity = []
        for offset in range(6, -1, -1):
            day = (date.fromisoformat(self.local_day()) - timedelta(days=offset)).isoformat()
            count = 0
            for subject in subjects:
                for a in self.rows(Attempt, Attempt.subject_id == subject["id"]):
                    if self.local_day(a.created_at) == day:
                        count += 1
            activity.append({"day": day, "count": count})
        for subject in subjects:
            latest += [{**a, "subject_name": subject["name"]} for a in self.attempts(subject["id"])[:5]]
        return {"subjects": subjects, "plans": plans, "recent": sorted(latest, key=lambda a: a["created_at"], reverse=True)[:8],
                "activity": activity, "day": self.local_day(), "timezone": self.settings()["timezone"],
                "totals": {key: sum(s[key] for s in subjects) for key in ("due", "published", "needs_review", "approved", "attempts", "history_wrong", "pending")}}
