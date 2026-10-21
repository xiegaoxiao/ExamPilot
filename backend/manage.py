"""Codex/developer CLI. All domain operations call the same transactional Service as the API."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from pydantic import ValidationError
from backend.app.database import Workspace
from backend.app.models import Audit, Job, Source, Version
from backend.app.services.core import DomainError, record


def build_parser():
    p = argparse.ArgumentParser(description="ExamPilot — 受控本地课程、教材与题库操作")
    p.add_argument("--home", type=Path, help="显式指定工作区根目录；默认项目根目录或 EXAMPILOT_HOME")
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="运行非破坏性结构迁移")
    commands.add_parser("demo", help="幂等导入原创示例；绝不批准或发布题目")
    course = commands.add_parser("course", help="查询/建立科目").add_subparsers(dest="action", required=True)
    course.add_parser("list")
    create = course.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--exam-date")
    create.add_argument("--budget-minutes", type=int, default=30)
    chapter = commands.add_parser("chapter", help="查询/建立章节").add_subparsers(dest="action", required=True)
    for action in ("list", "create"):
        sub = chapter.add_parser(action)
        sub.add_argument("--subject-id", required=True)
        if action == "create":
            sub.add_argument("--name", required=True)
    pdf = commands.add_parser("import-pdf", help="导入授权的本地 PDF")
    pdf.add_argument("--subject-id", required=True)
    pdf.add_argument("--chapter-id", required=True)
    pdf.add_argument("--file", type=Path, required=True)
    sources = commands.add_parser("sources", help="查询资料及可提取分页文本")
    sources.add_argument("--subject-id", required=True)
    sources.add_argument("--chapter-id")
    sources.add_argument("--source-id")
    knowledge = commands.add_parser("knowledge", help="知识点查询/结构化导入").add_subparsers(dest="action", required=True)
    for action in ("list", "import"):
        sub = knowledge.add_parser(action)
        sub.add_argument("--subject-id", required=True)
        if action == "import":
            sub.add_argument("--file", type=Path, required=True)
    questions = commands.add_parser("questions", help="题目导入、校验、查询与显式人工操作").add_subparsers(dest="action", required=True)
    for action in ("list", "import", "validate", "approve", "reject", "publish", "archive"):
        sub = questions.add_parser(action)
        sub.add_argument("--subject-id", required=True)
        sub.add_argument("--chapter-id")
        if action == "import":
            sub.add_argument("--file", type=Path, required=True)
        elif action != "list":
            sub.add_argument("--ids", nargs="+", required=True, help="明确列出题目版本 ID；不提供隐式全库发布")
            sub.add_argument("--reason", default="")
            if action in ("approve", "publish"):
                sub.add_argument("--human-confirmed", action="store_true", help="仅在用户明确批准此批次/发布时使用；Agent 不得自行添加")
        else:
            sub.add_argument("--status")
    review = commands.add_parser("review", help="复习计划/卡片查询").add_subparsers(dest="action", required=True)
    for action in ("plan", "cards"):
        sub = review.add_parser(action)
        sub.add_argument("--subject-id", required=True)
        if action == "plan":
            sub.add_argument("--replan", action="store_true", help="明确重新规划；默认返回已有当日计划")
    for command in ("report", "attempts", "jobs", "audit"):
        sub = commands.add_parser(command, help="按科目查询业务数据")
        sub.add_argument("--subject-id", required=True)
    backup = commands.add_parser("backup", help="写锁保护的完整本地备份；建议先停止服务")
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore", help="校验并恢复到空目录，不覆盖当前数据")
    restore.add_argument("--file", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "restore":
            from backend.app.services.backup import restore_backup
            result = restore_backup(args.file, args.destination)
        else:
            workspace = Workspace(args.home)
            if args.command == "init":
                result = {"schema": 1, "home": str(workspace.root), "status": "ready"}
            elif args.command == "demo":
                from backend.demo import initialize_demo
                result = initialize_demo(workspace)
            elif args.command == "backup":
                from backend.app.services.backup import create_backup
                result = create_backup(workspace, args.output)
            else:
                actor = "user" if getattr(args, "human_confirmed", False) else "codex"
                with workspace.service(actor) as svc:
                    sid = getattr(args, "subject_id", None)
                    if args.command == "course":
                        result = svc.subjects() if args.action == "list" else svc.create_subject({"name": args.name, "exam_date": args.exam_date, "budget_minutes": args.budget_minutes})
                    elif args.command == "chapter":
                        result = svc.chapters(sid) if args.action == "list" else svc.create_chapter(sid, {"name": args.name})
                    elif args.command == "import-pdf":
                        result = svc.upload_pdf(sid, args.chapter_id, args.file.name, args.file.read_bytes())
                    elif args.command == "sources":
                        result = svc.source_data(svc.scoped(Source, args.source_id, sid, args.chapter_id), include_text=True) if args.source_id else svc.sources(sid, args.chapter_id)
                    elif args.command == "knowledge":
                        result = svc.knowledge(sid) if args.action == "list" else [svc.import_knowledge(sid, item) for item in json.loads(args.file.read_text(encoding="utf-8-sig"))]
                    elif args.command == "questions":
                        if args.action == "list":
                            result = svc.questions(sid, args.chapter_id, status=args.status)
                        elif args.action == "import":
                            value = json.loads(args.file.read_text(encoding="utf-8-sig"))
                            if args.chapter_id and any(q.get("chapter_id") != args.chapter_id for q in value["questions"]):
                                raise DomainError("输入包含目标章节范围以外的题目")
                            result = svc.import_questions(sid, value)
                        else:
                            if args.chapter_id:
                                for vid in args.ids:
                                    svc.scoped(Version, vid, sid, args.chapter_id)
                            result = svc.review(sid, {"ids": args.ids, "action": args.action, "reason": args.reason})
                    elif args.command == "review":
                        result = svc.plan(sid, args.replan) if args.action == "plan" else svc.cards(sid)
                    elif args.command in ("report", "attempts"):
                        result = svc.subject_stats(sid) if args.command == "report" else svc.attempts(sid)
                    else:
                        svc.subject(sid, active=False)
                        cls = Job if args.command == "jobs" else Audit
                        result = [record(row) for row in svc.rows(cls, cls.subject_id == sid)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DomainError, ValidationError, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
