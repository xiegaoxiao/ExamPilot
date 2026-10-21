"""Real SQLite/HTTP/PDF tests: catch scope leaks, unauthorized publication and false learning events."""
import io
from datetime import datetime, timezone

from pypdf import PdfWriter
from reportlab.pdfgen import canvas
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def env(tmp_path):
    clock = [datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc).timestamp()]
    with TestClient(create_app(tmp_path, clock=lambda: clock[0])) as client:
        yield client, clock, tmp_path


def post(c, path, payload, status=200):
    r = c.post(path, json=payload)
    assert r.status_code == status, r.text
    return r.json()


def setup_course(c, name="Requirements"):
    subject = post(c, "/api/subjects", {"name": name, "budget_minutes": 10}, 201)
    sid = subject["id"]
    chapter = post(c, f"/api/subjects/{sid}/chapters", {"name": "Chapter 1"}, 201)
    stream = io.BytesIO()
    doc = canvas.Canvas(stream, invariant=1)
    doc.drawString(50, 780, "A requirement describes a needed capability. Validation checks stakeholder needs.")
    doc.save()
    content = stream.getvalue()
    r = c.post(f"/api/subjects/{sid}/sources?chapter_id={chapter['id']}", files={"file": ("textbook.pdf", content, "application/pdf")})
    assert r.status_code == 201, r.text
    source = r.json()
    kp = post(c, f"/api/subjects/{sid}/knowledge", {"chapter_id": chapter["id"], "name": "Requirements", "source_id": source["id"], "page": 1, "quote": "A requirement describes a needed capability."}, 201)
    return sid, chapter, source, kp


def payload(ctx, kind="single", stem="What is a requirement?"):
    sid, chapter, source, kp = ctx
    answers = {"single": "A", "multiple": ["A", "B"], "boolean": True, "fill": ["capability", "needed capability"]}
    return {"chapter_id": chapter["id"], "kind": kind, "stem": stem,
            "options": [{"id": key, "text": key + " text"} for key in "ABCD"] if kind in ("single", "multiple") else [],
            "answer": answers[kind], "explanation": "The evidence defines a requirement as a needed capability.",
            "knowledge_ids": [kp["id"]], "evidence": [{"source_id": source["id"], "page": 1, "quote": "A requirement describes a needed capability."}]}


def imported(c, ctx, kind="single", publish=True, stem=None):
    sid = ctx[0]
    q = payload(ctx, kind, stem or f"Question {kind}")
    r = post(c, f"/api/subjects/{sid}/questions/import", {"key": q["stem"], "questions": [q]})
    vid = r["questions"][0]["id"]
    if publish:
        post(c, f"/api/subjects/{sid}/review", {"ids": [vid], "action": "approve", "reason": "Checked source"})
        post(c, f"/api/subjects/{sid}/review", {"ids": [vid], "action": "publish", "reason": "Explicit human publication"})
    return vid


def submit(c, sid, vid, answer, key="request-1"):
    return post(c, f"/api/subjects/{sid}/attempts", {"version_id": vid, "answer": answer, "request_id": key, "elapsed_seconds": 15})


@pytest.mark.parametrize("kind,answer,result", [
    ("single", "A", "correct"), ("single", "B", "incorrect"),
    ("multiple", ["B", "A"], "correct"), ("multiple", ["A"], "incorrect"),
    ("multiple", ["A", "B", "C"], "incorrect"), ("boolean", True, "correct"),
    ("boolean", False, "incorrect"), ("fill", " capability ", "correct"),
    ("fill", "unknown", "pending_review"), ("fill", "Capability", "pending_review"),
])
def test_four_types_grade_without_ai(env, kind, answer, result):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx, kind)
    assert submit(c, ctx[0], vid, answer)["result"] == result


def test_human_approval_is_required_and_separate_from_publication(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx, publish=False)
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [vid], "action": "publish"}, 409)
    assert c.get(f"/api/subjects/{ctx[0]}/practice").json() == []
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [vid], "action": "approve"})
    assert c.get(f"/api/subjects/{ctx[0]}/practice").json() == []
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [vid], "action": "publish"})
    audits = c.get(f"/api/subjects/{ctx[0]}/questions/{vid}/audit").json()
    assert [a["action"] for a in audits][-2:] == ["approve", "publish"]


def test_missing_or_wrong_evidence_cannot_be_approved(env):
    c, _, _ = env
    ctx = setup_course(c)
    q = payload(ctx)
    q["evidence"][0]["quote"] = "This text does not appear in the PDF."
    result = post(c, f"/api/subjects/{ctx[0]}/questions/import", {"key": "invalid-evidence", "questions": [q]})
    vid = result["questions"][0]["id"]
    assert result["questions"][0]["issues"]
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [vid], "action": "approve"}, 409)


def test_cross_subject_reads_and_imports_are_rejected_atomically(env):
    c, _, _ = env
    a, b = setup_course(c, "A"), setup_course(c, "B")
    av = imported(c, a)
    assert c.get(f"/api/subjects/{b[0]}/questions/{av}").status_code == 404
    assert c.get(f"/api/subjects/{b[0]}/sources/{a[2]['id']}").status_code == 404
    q1, q2 = payload(b, stem="valid B"), payload(b, stem="bad B")
    q2["evidence"] = payload(a)["evidence"]
    post(c, f"/api/subjects/{b[0]}/questions/import", {"key": "bad-scope", "questions": [q1, q2]}, 422)
    assert c.get(f"/api/subjects/{b[0]}/questions").json() == []
    post(c, f"/api/subjects/{b[0]}/attempts", {"version_id": av, "answer": "A", "request_id": "wrong-scope"}, 404)


def test_idempotency_prevents_duplicate_attempts_and_rejects_changed_payload(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    first = submit(c, ctx[0], vid, "B")
    second = submit(c, ctx[0], vid, "B")
    assert first["id"] == second["id"]
    assert len(c.get(f"/api/subjects/{ctx[0]}/attempts").json()) == 1
    post(c, f"/api/subjects/{ctx[0]}/attempts", {"version_id": vid, "answer": "A", "request_id": "request-1", "elapsed_seconds": 15}, 409)


def test_pending_fill_does_not_schedule_until_resolution_and_resolves_once(env):
    c, clock, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx, "fill")
    a = submit(c, ctx[0], vid, "unlisted answer")
    assert c.get(f"/api/subjects/{ctx[0]}/cards").json() == []
    assert c.get(f"/api/subjects/{ctx[0]}/mistakes?view=history").json() == []
    clock[0] += 600
    path = f"/api/subjects/{ctx[0]}/attempts/{a['id']}/resolve"
    resolved = post(c, path, {"correct": False, "reason": "Compared with original textbook"})
    assert resolved["result"] == "incorrect"
    assert post(c, path, {"correct": False, "reason": "Compared with original textbook"})["id"] == a["id"]
    card = c.get(f"/api/subjects/{ctx[0]}/cards").json()[0]
    assert card["due_at"] == clock[0] + 600
    assert len(c.get(f"/api/subjects/{ctx[0]}/mistakes?view=history").json()) == 1


def test_fixed_intervals_are_exact_and_errors_reset_the_sequence(env):
    c, clock, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    for n, (answer, state, seconds) in enumerate([
        ("B", "relearning", 600), ("A", "learning", 86400), ("A", "review", 259200),
        ("A", "review", 604800), ("A", "review", 1209600), ("A", "review", 1209600),
        ("B", "relearning", 600),
    ]):
        submit(c, ctx[0], vid, answer, f"step-{n}")
        card = c.get(f"/api/subjects/{ctx[0]}/cards").json()[0]
        assert (card["state"], card["due_at"]) == (state, clock[0] + seconds)
        clock[0] += seconds


def test_suspended_card_records_manual_answer_without_rescheduling(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    a = submit(c, ctx[0], vid, "A")
    card = c.get(f"/api/subjects/{ctx[0]}/cards").json()[0]
    post(c, f"/api/subjects/{ctx[0]}/cards/{card['question_id']}/pause", {"paused": True})
    submit(c, ctx[0], vid, "B", "manual-2")
    after = c.get(f"/api/subjects/{ctx[0]}/cards").json()[0]
    assert after["state"] == "suspended" and after["due_at"] == card["due_at"]
    assert len(c.get(f"/api/subjects/{ctx[0]}/attempts").json()) == 2


def test_budget_skips_large_questions_continues_and_preserves_manual_deferral(env):
    c, clock, _ = env
    ctx = setup_course(c)
    sid = ctx[0]
    multi = imported(c, ctx, "multiple")
    boolean = imported(c, ctx, "boolean")
    single = imported(c, ctx, "single")
    submit(c, sid, multi, ["D"], "m")
    submit(c, sid, boolean, False, "b")
    clock[0] += 600
    c.patch(f"/api/subjects/{sid}", json={"budget_minutes": 2})
    plan = post(c, f"/api/subjects/{sid}/plan", {})
    assert [i["version_id"] for i in plan["items"]] == [boolean]
    assert any(i["version_id"] == multi and i["reason"] == "budget" for i in plan["skipped"])
    item = plan["items"][0]
    post(c, f"/api/subjects/{sid}/plan/items/{item['id']}", {"action": "defer", "until": "2026-10-23"})
    same = post(c, f"/api/subjects/{sid}/plan", {})
    assert same["items"][0]["status"] == "deferred"
    clock[0] += 86400
    next_day = post(c, f"/api/subjects/{sid}/plan", {})
    assert boolean not in [i["version_id"] for i in next_day["items"]]


def test_history_survives_later_correct_answer_and_archive(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    submit(c, ctx[0], vid, "B")
    submit(c, ctx[0], vid, "A", "redo")
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [vid], "action": "archive"})
    history = c.get(f"/api/subjects/{ctx[0]}/mistakes?view=history").json()
    assert len(history) == 1 and history[0]["version_id"] == vid
    assert c.get(f"/api/subjects/{ctx[0]}/practice").json() == []


def test_invalid_boolean_or_duplicate_options_are_rejected(env):
    c, _, _ = env
    ctx = setup_course(c)
    q = payload(ctx, "boolean")
    q["answer"] = "false"
    post(c, f"/api/subjects/{ctx[0]}/questions/import", {"key": "bad-bool", "questions": [q]}, 422)
    q = payload(ctx)
    q["options"][1]["text"] = q["options"][0]["text"]
    post(c, f"/api/subjects/{ctx[0]}/questions/import", {"key": "bad-options", "questions": [q]}, 422)


def test_changed_published_question_creates_unpublished_version_without_rewriting_history(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    a = submit(c, ctx[0], vid, "A")
    q = payload(ctx, stem="Revised meaning")
    q["answer"] = "B"
    revised = post(c, f"/api/subjects/{ctx[0]}/questions/{vid}/revise", q)
    assert revised["version"] == 2 and revised["status"] == "needs_review"
    assert c.get(f"/api/subjects/{ctx[0]}/practice").json()[0]["id"] == vid
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [revised['id']], "action": "approve"})
    post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [revised['id']], "action": "publish"})
    old = c.get(f"/api/subjects/{ctx[0]}/attempts").json()[0]
    assert old["result"] == "correct" and old["standard_answer"] == "A"
    post(c, f"/api/subjects/{ctx[0]}/attempts", {"version_id": vid, "answer": "A", "request_id": "old"}, 409)


def test_external_origins_cannot_write_local_database(env):
    c, _, _ = env
    r = c.post("/api/subjects", json={"name": "injected"}, headers={"Origin": "https://untrusted.example"})
    assert r.status_code == 403
    assert c.get("/api/subjects").json() == []


def test_same_origin_on_a_custom_loopback_port_can_write(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8001") as c:
        r = c.post("/api/subjects", json={"name": "same origin"}, headers={"Origin": "http://127.0.0.1:8001"})
        assert r.status_code == 201


def test_replanning_after_a_second_due_event_retains_completion_and_adds_new_task(env):
    c, clock, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    original = post(c, f"/api/subjects/{ctx[0]}/plan", {})
    submit(c, ctx[0], vid, "B")
    clock[0] += 600
    renewed = post(c, f"/api/subjects/{ctx[0]}/plan", {"replan": True})
    assert len([i for i in renewed["items"] if i["status"] == "completed"]) == 1
    assert len([i for i in renewed["items"] if i["status"] == "pending" and i["version_id"] == vid]) == 1


def test_practice_does_not_silently_accept_a_foreign_version_filter(env):
    c, _, _ = env
    a, b = setup_course(c, "A"), setup_course(c, "B")
    vid = imported(c, a)
    assert c.get(f"/api/subjects/{b[0]}/practice?version_id={vid}").status_code == 404


def test_cli_failure_job_is_available_through_shared_service(tmp_path):
    from backend.app.database import Workspace
    from backend.app.services.core import DomainError
    from backend.app.models import Job
    workspace = Workspace(tmp_path)
    with workspace.service() as svc:
        sid = svc.create_subject({"name": "Failure trace"})["id"]
    with pytest.raises(DomainError):
        with workspace.service("codex") as svc:
            svc.import_questions(sid, {"key": "invalid-chapter", "questions": [{
                "chapter_id": "not-in-scope", "kind": "boolean", "stem": "Question", "answer": True}]})
    with workspace.service() as svc:
        jobs = svc.rows(Job, Job.subject_id == sid)
        assert len(jobs) == 1 and jobs[0].status == "failed"


def test_db_commit_failure_does_not_leave_attempt_card_or_completion(env):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    post(c, f"/api/subjects/{ctx[0]}/plan", {})
    def fail_commit(session):
        raise RuntimeError("simulated commit failure")
    event.listen(Session, "before_commit", fail_commit, once=True)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        submit(c, ctx[0], vid, "B")
    assert c.get(f"/api/subjects/{ctx[0]}/attempts").json() == []
    assert c.get(f"/api/subjects/{ctx[0]}/cards").json() == []
    assert post(c, f"/api/subjects/{ctx[0]}/plan", {})["items"][0]["status"] == "pending"


def test_new_published_semantic_version_requires_new_coverage_evidence(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    submit(c, ctx[0], vid, "A")
    content = payload(ctx, stem="A revised requirement question")
    content["answer"] = "B"
    revised = post(c, f"/api/subjects/{ctx[0]}/questions/{vid}/revise", content)
    for action in ("approve", "publish"):
        post(c, f"/api/subjects/{ctx[0]}/review", {"ids": [revised['id']], "action": action})
    report = c.get(f"/api/subjects/{ctx[0]}/report").json()
    assert report["coverage"] == 0
    assert report["attempts"] == 1


def test_adding_equivalent_answer_keeps_old_attempt_and_requires_publication(env):
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx, "fill")
    attempt = submit(c, ctx[0], vid, "alternative")
    resolved = post(c, f"/api/subjects/{ctx[0]}/attempts/{attempt['id']}/resolve", {"correct": True, "reason": "Equivalent in this context", "add_equivalent": True})
    assert resolved["initial_result"] == "pending_review" and resolved["result"] == "correct"
    new_id = resolved["resolution"]["proposed_version_id"]
    assert c.get(f"/api/subjects/{ctx[0]}/questions/{new_id}").json()["status"] == "needs_review"
    assert submit(c, ctx[0], vid, "alternative", "again-before-publish")["result"] == "pending_review"


def test_concurrent_identical_submissions_commit_only_one_attempt(env):
    from concurrent.futures import ThreadPoolExecutor
    c, _, _ = env
    ctx = setup_course(c)
    vid = imported(c, ctx)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: submit(c, ctx[0], vid, "A"), range(2)))
    assert replies[0]["id"] == replies[1]["id"]
    assert len(c.get(f"/api/subjects/{ctx[0]}/attempts").json()) == 1


def test_retrying_a_cli_import_after_transient_commit_failure_uses_canonical_digest(env):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    c, _, _ = env
    ctx = setup_course(c)
    batch = {"key": "retry-transient", "questions": [payload(ctx, stem="Retry after disk failure")]}
    workspace = c.app.state.workspace
    def transient_failure(session):
        raise RuntimeError("transient disk failure")
    event.listen(Session, "before_commit", transient_failure, once=True)
    with pytest.raises(RuntimeError, match="transient disk failure"):
        with workspace.service("codex") as svc:
            svc.import_questions(ctx[0], batch)
    with workspace.service("codex") as svc:
        result = svc.import_questions(ctx[0], batch)
        assert result["inserted"] == 1
        assert len(svc.questions(ctx[0])) == 1


@pytest.mark.parametrize("password", ["", "protected"])
def test_encrypted_pdf_is_rejected_without_registering_a_source(env, password):
    c, _, _ = env
    sid, chapter, _, _ = setup_course(c)
    plain = io.BytesIO()
    doc = canvas.Canvas(plain, invariant=1)
    doc.drawString(50, 780, "Readable text does not remove PDF encryption.")
    doc.save()
    writer = PdfWriter(clone_from=io.BytesIO(plain.getvalue()))
    writer.encrypt(password, owner_password="owner-only")
    stream = io.BytesIO()
    writer.write(stream)
    response = c.post(f"/api/subjects/{sid}/sources?chapter_id={chapter['id']}",
                      files={"file": ("encrypted.pdf", stream.getvalue(), "application/pdf")})
    assert response.status_code == 422
    assert "加密" in response.text
    assert len(c.get(f"/api/subjects/{sid}/sources").json()) == 1


def test_pdf_import_preserves_physical_pages_and_identifies_actual_parser(env):
    c, _, _ = env
    sid, chapter, _, _ = setup_course(c)
    stream = io.BytesIO()
    doc = canvas.Canvas(stream, invariant=1)
    doc.showPage()
    doc.drawString(50, 780, "The evidence is on physical page two.")
    doc.save()
    response = c.post(f"/api/subjects/{sid}/sources?chapter_id={chapter['id']}",
                      files={"file": ("mixed.pdf", stream.getvalue(), "application/pdf")})
    assert response.status_code == 201
    source = response.json()
    assert source["status"] == "partial"
    assert source["page_count"] == 2
    assert source["unavailable_pages"] == [1]
    assert source["parser_version"].startswith("pypdf-")
    post(c, f"/api/subjects/{sid}/knowledge", {"chapter_id": chapter["id"], "name": "Page two",
         "source_id": source["id"], "page": 2, "quote": "The evidence is on physical page two."}, 201)
