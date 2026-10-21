"""Opt-in, idempotent original demo. Does not approve or publish any questions."""
import io
import json
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from backend.app.models import Subject


FACTS = [
    ["需求描述系统必须具备的能力或满足的约束。", "功能需求描述系统应提供的行为与服务。",
     "非功能需求描述性能、可靠性和安全性等质量约束。", "需求应具备可验证性，验收条件必须能够客观判断。"],
    ["需求验证检查需求文档是否完整、一致且可验证。", "需求确认检查需求是否反映利益相关者的真实需要。",
     "需求追踪连接业务目标、需求、设计和测试。", "基线变更必须经过影响分析和明确批准，并保留变更记录。"],
]


def original_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(595, 842), invariant=1)
    pdf.setTitle("ExamPilot original demo - Requirements Engineering")
    pdf.setAuthor("ExamPilot Demo")
    for i, facts in enumerate(FACTS):
        pdf.setFillColor(colors.HexColor("#1446d4"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, 788, "EXAMPILOT / ORIGINAL LEARNING NOTES")
        pdf.setFont("STSong-Light", 26)
        pdf.drawString(48, 726, ["第一章 需求基础", "第二章 验证与变更"][i])
        pdf.setFillColor(colors.HexColor("#222435"))
        for j, fact in enumerate(facts):
            y = 646 - j * 110
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(48, y, f"0{j + 1}")
            pdf.setFont("STSong-Light", 13)
            # Deliberately short lines: CID text remains selectable and verifiable after extraction.
            for k in range(0, len(fact), 30):
                pdf.drawString(80, y - (k // 30) * 25, fact[k:k + 30])
        pdf.setStrokeColor(colors.HexColor("#d3dee4"))
        pdf.line(48, 100, 547, 100)
        pdf.setFont("STSong-Light", 10)
        pdf.drawString(48, 78, "原创演示材料，仅用于功能演示；不替代正式课程教材。")
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(547, 78, f"{i + 1} / 2")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def initialize_demo(workspace):
    pdf_bytes = original_pdf()
    with workspace.service("system") as svc:
        existing = svc.rows(Subject, Subject.demo_key == "original-requirements-v1")
        if existing:
            subject = existing[0]
        else:
            created = svc.create_subject({"name": "软件需求工程", "exam_date": (date.fromisoformat(svc.local_day()) + timedelta(days=7)).isoformat(), "budget_minutes": 30})
            subject = svc.s.get(Subject, created["id"])
            subject.demo_key = "original-requirements-v1"
        sid = subject.id
        chapters = svc.chapters(sid)
        if len(chapters) < 2:
            for name in ("第一章 需求基础", "第二章 验证与变更"):
                if not any(c["name"] == name for c in chapters):
                    svc.create_chapter(sid, {"name": name})
            chapters = svc.chapters(sid)
        source = svc.upload_pdf(sid, chapters[0]["id"], "软件需求工程_原创演示教材.pdf", pdf_bytes)
        # One chapter/source record per authorized chapter, even for identical source bytes.
        source2 = svc.upload_pdf(sid, chapters[1]["id"], "软件需求工程_原创演示教材.pdf", pdf_bytes)
        sources = [source, source2]
        kps = []
        for i, chapter in enumerate(chapters[:2]):
            kp = svc.import_knowledge(sid, {"chapter_id": chapter["id"], "name": ["需求分类与可验证性", "验证、确认与追踪"][i],
                                           "source_id": sources[i]["id"], "page": i + 1, "quote": FACTS[i][0]})
            kps.append(kp)
        fixtures = [
            (0, "single", "功能需求主要描述什么？", ["系统应提供的行为与服务", "开发团队人数", "考试日期", "软件售价"], "A", 1),
            (0, "multiple", "根据教材，哪些属于非功能需求关注的质量属性？", ["性能", "可靠性", "安全性", "团队午餐安排"], ["A", "B", "C"], 2),
            (0, "boolean", "验收条件应能够客观判断，以支持需求的可验证性。", [], True, 3),
            (0, "fill", "需求描述系统必须具备的____或满足的约束。", [], ["能力"], 0),
            (1, "single", "检查需求是否反映利益相关者真实需要，属于哪项活动？", ["需求确认", "数据备份", "界面美化", "程序编译"], "A", 1),
            (1, "multiple", "教材中的需求追踪连接哪些对象？", ["业务目标", "需求", "设计和测试", "无关课程的资料"], ["A", "B", "C"], 2),
            (1, "boolean", "基线变更可以不经批准，也无需保留变更记录。", [], False, 3),
            (1, "fill", "需求验证检查文档是否完整、一致且具有____。", [], ["可验证性", "可验证的性质"], 0),
        ]
        questions = []
        for chapter_index, kind, stem, options, answer, fact_index in fixtures:
            questions.append({"chapter_id": chapters[chapter_index]["id"], "kind": kind, "stem": stem,
                              "options": [{"id": letter, "text": text} for letter, text in zip("ABCD", options)],
                              "answer": answer, "explanation": FACTS[chapter_index][fact_index], "knowledge_ids": [kps[chapter_index]["id"]],
                              "evidence": [{"source_id": sources[chapter_index]["id"], "page": chapter_index + 1, "quote": FACTS[chapter_index][fact_index]}]})
        result = svc.import_questions(sid, {"key": "original-demo-questions-v1", "questions": questions})
        summary = {"subject_id": sid, "source_id": source["id"], "questions": len(result["questions"]),
                   "message": "示例已准备；不会自动批准或发布。请到审核中心由用户操作。"}
    out = workspace.root / "output/pdf"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "exampilot-original-demo.pdf"
    if not path.exists():
        path.write_bytes(pdf_bytes)
    example = workspace.root / "workspace/demo-questions.json"
    if not example.exists():
        example.write_text(json.dumps({"key": "original-demo-questions-v1", "questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    from backend.app.database import Workspace
    print(json.dumps(initialize_demo(Workspace()), ensure_ascii=False, indent=2))
