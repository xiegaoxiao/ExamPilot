import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_demo_initializer_is_repeatable_and_never_publishes(tmp_path):
    from backend.demo import initialize_demo
    from backend.app.database import Workspace
    workspace = Workspace(tmp_path)
    first = initialize_demo(workspace)
    second = initialize_demo(workspace)
    assert first["subject_id"] == second["subject_id"]
    with TestClient(create_app(tmp_path)) as c:
        sid = first["subject_id"]
        assert len(c.get("/api/subjects").json()) == 1
        questions = c.get(f"/api/subjects/{sid}/questions").json()
        assert {q["kind"] for q in questions} == {"single", "multiple", "boolean", "fill"}
        assert len(questions) == 8
        assert all(q["status"] == "needs_review" and not q["issues"] for q in questions)
        assert c.get(f"/api/subjects/{sid}/practice").json() == []
        assert first["source_id"] == second["source_id"]


def test_backup_restores_documents_attempts_and_scope_into_empty_directory(tmp_path):
    from backend.demo import initialize_demo
    from backend.app.database import Workspace
    from backend.app.services.backup import create_backup, restore_backup
    workspace = Workspace(tmp_path / "original")
    demo = initialize_demo(workspace)
    with workspace.service("user") as svc:
        questions = svc.questions(demo["subject_id"])
        vid = questions[0]["id"]
        svc.review(demo["subject_id"], {"ids": [vid], "action": "approve"})
        svc.review(demo["subject_id"], {"ids": [vid], "action": "publish"})
        svc.submit(demo["subject_id"], {"version_id": vid, "answer": "A", "request_id": "backup-test"})
    archive = tmp_path / "backup.zip"
    create_backup(workspace, archive)
    restore_backup(archive, tmp_path / "restored")
    restored = Workspace(tmp_path / "restored")
    with restored.service() as svc:
        assert len(svc.attempts(demo["subject_id"])) == 1
        assert len(svc.questions(demo["subject_id"])) == 8
        source = svc.rows(__import__('backend.app.models', fromlist=['Source']).Source)[0]
        assert svc.source_path(source).is_file()
    with pytest.raises(ValueError):
        restore_backup(archive, tmp_path / "original")


def test_cli_and_web_share_the_same_database(tmp_path):
    manage = Path(__file__).resolve().parents[1] / "manage.py"
    command = [sys.executable, str(manage), "--home", str(tmp_path), "course", "create", "--name", "CLI course"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    created = json.loads(result.stdout)
    with TestClient(create_app(tmp_path)) as c:
        subjects = c.get("/api/subjects").json()
        assert subjects[0]["id"] == created["id"]


def test_codex_cli_cannot_implicitly_approve_or_publish(tmp_path):
    from backend.demo import initialize_demo
    from backend.app.database import Workspace
    workspace = Workspace(tmp_path)
    demo = initialize_demo(workspace)
    with workspace.service("codex") as svc:
        vid = svc.questions(demo["subject_id"])[0]["id"]
        from backend.app.services.core import DomainError
        with pytest.raises(DomainError):
            svc.review(demo["subject_id"], {"ids": [vid], "action": "approve"})
