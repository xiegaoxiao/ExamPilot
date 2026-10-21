from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class SubjectInput(Input):
    name: str = Field(min_length=1, max_length=80)
    exam_date: date | None = None
    budget_minutes: int | None = Field(default=30, ge=0, le=240)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("名称不能为空")
        return value.strip()


class SubjectPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    exam_date: date | None = None
    budget_minutes: int | None = Field(default=None, ge=0, le=240)


class ChapterInput(Input):
    name: str = Field(min_length=1, max_length=80)
    exam_focus: bool = False


class KnowledgeInput(Input):
    chapter_id: str
    name: str = Field(min_length=1, max_length=120)
    source_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=5000)


class Option(Input):
    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=2000)


class Evidence(Input):
    source_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=5000)


class QuestionInput(Input):
    chapter_id: str
    kind: Literal["single", "multiple", "boolean", "fill"]
    stem: str = Field(min_length=1, max_length=10000)
    options: list[Option] = Field(default_factory=list)
    answer: Any
    explanation: str = Field(default="", max_length=15000)
    knowledge_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    uncertain: bool = False

    @model_validator(mode="after")
    def answer_contract(self):
        if not self.stem.strip():
            raise ValueError("题干不能为空")
        if self.kind in ("single", "multiple"):
            ids = [o.id for o in self.options]
            texts = [o.text.strip() for o in self.options]
            if len(ids) != 4 or len(set(ids)) != 4 or len(set(texts)) != 4 or not all(texts):
                raise ValueError("选择题必须恰有四个非空且唯一的选项")
            if self.kind == "single" and (not isinstance(self.answer, str) or self.answer not in ids):
                raise ValueError("单选答案必须是一个有效选项 ID")
            if self.kind == "multiple":
                if not isinstance(self.answer, list) or len(self.answer) not in (2, 3) or not all(isinstance(x, str) for x in self.answer) or len(set(self.answer)) != len(self.answer) or not set(self.answer) <= set(ids):
                    raise ValueError("多选标准答案必须是两个或三个不同的有效选项")
        elif self.options:
            raise ValueError("判断和填空不接受自定义选项")
        if self.kind == "boolean" and type(self.answer) is not bool:
            raise ValueError("判断答案必须是 true/false 布尔值")
        if self.kind == "fill":
            if not isinstance(self.answer, list) or not self.answer or not all(isinstance(a, str) and 0 < len(a.strip()) <= 200 for a in self.answer):
                raise ValueError("单空填空需非空短文本答案列表（每项不超过200字符）")
        return self


class ImportInput(Input):
    key: str = Field(min_length=1, max_length=200)
    questions: list[QuestionInput] = Field(min_length=1, max_length=500)


class ReviewInput(Input):
    ids: list[str] = Field(min_length=1, max_length=500)
    action: Literal["validate", "approve", "reject", "publish", "archive"]
    reason: str = Field(default="", max_length=2000)


class AttemptInput(Input):
    version_id: str
    answer: Any
    request_id: str = Field(min_length=1, max_length=200)
    elapsed_seconds: int = Field(default=0, ge=0, le=86400)


class ResolveInput(Input):
    correct: bool
    reason: str = Field(min_length=1, max_length=2000)
    add_equivalent: bool = False


class PlanInput(Input):
    replan: bool = False


class PlanEdit(Input):
    action: Literal["defer", "remove", "restore"]
    until: date | None = None


class PauseInput(Input):
    paused: bool


class SettingsInput(Input):
    timezone: str = Field(min_length=1, max_length=100)
