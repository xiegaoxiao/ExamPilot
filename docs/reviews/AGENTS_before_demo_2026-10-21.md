# ExamPilot — Codex 项目指令

## 1. 项目定位

ExamPilot 是一个本地优先、面向计算机专业课程期末考试的智能复习系统。
学生通过 Vue 3 网页管理科目、导入章节 PDF、刷题、查看错题与复习计划。
FastAPI + SQLite 提供统一业务接口和持久化。
Codex 是通过项目工作区进行智能操作的外部 Agent；MVP 不要求在后端嵌入 LLM Agent Runtime。

核心闭环：资料导入 → 知识点提取 → 出题与质量校验 → 入库 → 答题 → 错题诊断 → 次日复习。

## 2. Codex 的角色与权限边界

- 阅读整个项目、文档与源代码，协助开发、测试、维护。
- 处理课程知识时，只能在用户选定的 `subject_id`/`chapter_id` 范围内工作；不跨科目混用资料。
- 优先使用 `backend/manage.py` 所提供的业务命令操作数据。不得通过临时 SQL 直接绕过审核、答题记录、复习调度等业务约束。
- 用户的 PDF、历史答题记录和现有已发布题目是重要数据：未经明确许可，不得删除、覆盖、批量重置。
- 自动生成的新题应携带原始 PDF 的页码/证据片段。没有可验证来源的题进入待审核，不得作为可靠知识直接发布。
- 修改项目代码时需运行适用的测试；变更数据库结构时添加迁移，并说明兼容性与备份方式。
- 避免运行需要关闭审批的高风险命令；权限仍受 Codex 沙盒及用户批准控制。

## 3. 目录约定（目标结构，可迭代）

- `frontend/`：Vue 3 + TypeScript 网页
- `backend/app/api/`：FastAPI 路由
- `backend/app/models/`：数据模型与数据库迁移
- `backend/app/services/`：导入、校验、组卷、答题、复习等共享业务逻辑
- `backend/manage.py`：供 Codex 与开发者调用的 CLI 入口
- `workspace/subjects/<subject_id>/sources/`：原始 PDF
- `workspace/subjects/<subject_id>/knowledge/`：带来源元数据的 Markdown 知识文档
- `docs/`：领域模型、流程、接口与验收标准
- `data/`：SQLite 数据库及备份（默认不提交 Git）

## 4. 核心实体

- `Subject`：科目；必须有唯一 `id`，可配置考试日期和复习时间预算。
- `Chapter`：属于且仅属于一个科目。
- `SourceDocument`：上传的 PDF，记录文件路径、哈希、解析版本、所属科目及章节。
- `KnowledgePoint`：知识点，可以关联多个来源片段。
- `Question`：题干、题型、选项、答案、解析、难度、知识点、来源证据、审核状态与版本。
- `Attempt`：每次作答的不可覆盖历史事件，记录时间、答案、结果、用时与题目版本。
- `ReviewCard`：特定用户对特定题目/知识点的间隔复习状态。
- `DailyPlan`：某日的复习任务，记录生成依据和用户覆盖/确认信息。
- `AgentJob`：一次导入、出题或整理任务的请求、执行记录、结果、失败原因。

## 5. 题目状态 != 学生掌握状态

题库生命周期 `Question.status`：

`draft` → `validating` → (`needs_review` | `approved`) → `published`

- `needs_review` 可经人工审核转为 `approved` 或 `rejected`。
- 失效或重复题可转为 `archived`；保留原始答题历史。
- 只有 `published` 且版本有效的题才能进入普通刷题/复习计划。
- 已发布题目的答案变更应创建新版本并保留旧作答关联，不可静默改写历史。

学生复习状态 `ReviewCard.state`：

`new` / `learning` / `review` / `relearning` / `suspended`

- 错题不是题目全局状态：答错要追加 `Attempt`，必要时更新 `ReviewCard`。
- 调度间隔由确定性算法计算（可使用 FSRS），Agent 只能建议优先级和题型，不得绕过事件记录直接伪造掌握度。

## 6. 生成题目的质量门槛

- 来源必须属于目标 `subject_id`，并尽量精确到章节、PDF 页码和知识点。
- 每题必须能从材料或明确标注的通用知识中验证答案；课程专属内容不得凭空补写。
- 自动检查 JSON schema、选项数量、答案一致性、重复题、歧义、解析可验证性。
- 无法判定答案、来源缺失、存在多解的单选题及主观评分规则不清的题，统一转 `needs_review`。
- 题目审核与发布要留审计记录；批量发布前显示摘要，并按系统发布策略执行。

## 7. 业务操作优先级

1. 阅读 `AGENTS.md`、相关文档，确认当前 `subject_id` 和用户目标。
2. 检查 `backend/manage.py --help` 中已经实现的命令；如果缺少工具，先实现并测试，而不是假装已有。
3. 所有数据写入统一走 `backend/app/services/` 的事务性业务方法，由 CLI 或 API 调用。
4. 对导入/出题任务提供幂等键或来源哈希，避免重复导入与重复写题。
5. 执行后给用户报告：影响的科目、章节、题目数量、待审数量、错误与下一步。

## 8. 建议提供的 CLI 契约（尚需实现，不得假设可执行）

```bash
python backend/manage.py course list
python backend/manage.py course create --name "软件需求工程"
python backend/manage.py import-pdf --subject-id <id> --chapter-id <id> --file <path>
python backend/manage.py questions import --subject-id <id> --chapter-id <id> --file <json>
python backend/manage.py questions validate --subject-id <id> --chapter-id <id>
python backend/manage.py questions publish --subject-id <id> --approved-only
python backend/manage.py review plan --subject-id <id> --date YYYY-MM-DD
python backend/manage.py report --subject-id <id>
```

这些命令应与网页 API 使用同一个服务层，确保 Codex 写入数据后，网页刷新即可显示一致结果。

## 9. 常见自然语言操作范式

- “把第三章 PDF 加入软件需求工程，整理知识点并生成 30 道单选题。”
  先定位科目和章节 → 导入原文 → 提取知识 → 生成结构化题 → 校验 → 导入草稿 → 发布合格题或送审 → 汇报。
- “查找我最近经常错的需求获取题目，补充 10 道变式题。”
  查询该科目的 Attempt 与知识点 → 定位薄弱概念 → 生成新题 → 校验与去重 → 审核入库。
- “我后天考试，重新规划今天的一小时复习。”
  查询考试日期、到期复习、知识覆盖与预算 → 使用确定性调度服务产生计划 → 保存计划调整记录。

## 10. MVP 开发顺序与验收

1. 初始化 Vue 3、FastAPI、SQLite，并提供可运行的一键本地启动方式。
2. 完成科目/章节 CRUD、PDF 上传、资料存储与来源定位。
3. 完成题库状态机、结构化导题、单选题作答、Attempt 历史。
4. 完成错题列表、ReviewCard 与每日计划。
5. 实现并测试 Codex CLI 契约；让 CLI 与网页共享数据库和服务层。
6. 跑通：创建科目 → 上传章节 PDF → Codex 生成题目 → 校验入库 → 网页刷题 → 第二天复习。

**成功标准**：网页操作和 Codex CLI 操作的状态一致、可追溯、可恢复；任何 AI 输出不能跳过业务校验。
