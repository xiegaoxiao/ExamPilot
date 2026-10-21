export type Kind = "single" | "multiple" | "boolean" | "fill";
export type Answer = string | string[] | boolean | null;
export interface Subject {
  id: string;
  name: string;
  exam_date: string | null;
  budget_minutes: number | null;
  archived: boolean;
  published: number;
  needs_review: number;
  approved: number;
  chapters: number;
  sources: number;
  knowledge: number;
  attempts: number;
  correct: number;
  graded: number;
  accuracy: number | null;
  due: number;
  history_wrong: number;
  pending: number;
  coverage: number;
  days_to_exam: number | null;
}
export interface Chapter {
  id: string;
  subject_id: string;
  name: string;
  position: number;
  exam_focus: boolean;
  archived: boolean;
}
export interface Evidence {
  source_id: string;
  page: number;
  quote: string;
  filename?: string;
}
export interface Knowledge {
  id: string;
  name: string;
  chapter_id: string;
  evidence: Evidence;
}
export interface Source {
  id: string;
  chapter_id: string;
  filename: string;
  sha256: string;
  page_count: number;
  unavailable_pages: number[];
  status: string;
  created_at: number;
}
export interface Card {
  question_id: string;
  state: string;
  due_at: number | null;
  stage: number;
}
export interface Question {
  id: string;
  subject_id: string;
  chapter_id: string;
  chapter_name: string;
  question_id: string;
  version: number;
  kind: Kind;
  stem: string;
  options: { id: string; text: string }[];
  answer?: Answer;
  explanation?: string;
  knowledge_ids: string[];
  knowledge: Knowledge[];
  evidence?: Evidence[];
  status: string;
  issues?: string[];
  active: boolean;
  card?: Card;
  created_at: number;
}
export interface Attempt {
  id: string;
  subject_id: string;
  version_id: string;
  question_id: string;
  answer: Answer;
  initial_result: string;
  result: string;
  standard_answer: Answer;
  question: Question;
  stem: string;
  kind: Kind;
  created_at: number;
  elapsed_seconds: number;
  resolution: {
    correct: boolean;
    reason: string;
    proposed_version_id: string | null;
  } | null;
  subject_name?: string;
}
export interface PlanItem {
  id: string;
  question_id: string;
  version_id: string;
  stem: string;
  kind: Kind;
  minutes: number;
  priority: string;
  status: string;
  active: boolean;
  until?: string;
  attempt_id?: string;
}
export interface Plan {
  id: string;
  subject_id: string;
  day: string;
  timezone: string;
  budget_minutes: number | null;
  minutes: number;
  items: PlanItem[];
  skipped: {
    version_id: string;
    stem: string;
    reason: string;
    minutes?: number;
    until?: string;
  }[];
  revision: number;
  generated_at: number;
}
export interface Audit {
  id: string;
  actor: string;
  action: string;
  target_id: string;
  created_at: number;
  details: Record<string, unknown>;
}
export interface Settings {
  timezone: string;
  data_path: string;
  workspace_path: string;
  schema_version: number;
  demo_policies: { weakness: string; limits: string };
}
export interface Dashboard {
  subjects: Subject[];
  plans: Plan[];
  recent: Attempt[];
  activity: { day: string; count: number }[];
  day: string;
  timezone: string;
  totals: Record<
    | "due"
    | "published"
    | "needs_review"
    | "approved"
    | "attempts"
    | "history_wrong"
    | "pending",
    number
  >;
}
export interface Job {
  id: string;
  key: string;
  status: string;
  result: {
    input?: number;
    inserted?: number;
    skipped?: number;
    needs_review?: number;
    reason?: string;
  };
  created_at: number;
}
