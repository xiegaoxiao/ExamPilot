import type { Answer } from "./types";
export const kinds = {
  single: "单选题",
  multiple: "多选题",
  boolean: "判断题",
  fill: "填空题",
};
export const statusLabels: Record<string, string> = {
  draft: "草稿",
  validating: "校验中",
  needs_review: "待人工审核",
  approved: "已批准待发布",
  published: "已发布",
  rejected: "已拒绝",
  archived: "已归档",
};
export const resultLabels: Record<string, string> = {
  correct: "回答正确",
  incorrect: "回答错误",
  pending_review: "待人工复核",
};
export const stateLabels: Record<string, string> = {
  new: "新题",
  learning: "学习中",
  review: "间隔复习",
  relearning: "重新巩固",
  suspended: "已暂停",
};
export const reasonLabels: Record<string, string> = {
  budget: "剩余预算不足，已跳过",
  budget_not_set: "尚未设置复习预算",
  pending_review: "有待复核作答，暂不重复安排",
  deferred: "用户已延期",
};
export function answerText(value: Answer | undefined): string {
  return Array.isArray(value)
    ? value.join("、")
    : typeof value === "boolean"
      ? value
        ? "正确"
        : "错误"
      : (value ?? "—");
}
export function dateTime(
  timestamp: number | null | undefined,
  zone = "Asia/Shanghai",
): string {
  return timestamp == null
    ? "暂无安排"
    : new Intl.DateTimeFormat("zh-CN", {
        timeZone: zone,
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(timestamp * 1000));
}
export function tomorrow(day: string): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}
