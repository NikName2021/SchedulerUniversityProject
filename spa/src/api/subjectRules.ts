import { API_BASE_URL, apiFetch } from "./apiConfig.js";
import type {
  SubjectRuleCheck,
  SubjectRuleConfig,
  SubjectRuleContext,
  SubjectRuleItem,
} from "../utils/subjectRules.js";

async function request<T>(
  path: string,
  body: unknown,
  signal: AbortSignal | undefined,
  method = "POST",
): Promise<T> {
  const response = await apiFetch(
    `${API_BASE_URL}/api/v1/scheduler/subject-rules${path}`,
    {
      method,
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  const payload: unknown = await response.json();
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : null;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map(
                (item: { msg?: string }) =>
                  item.msg || "Некорректные настройки",
              )
              .join(". ")
          : "Не удалось обработать настройки предмета";
    throw new Error(message.replaceAll("Value error, ", ""));
  }
  return payload as T;
}

export function fetchSubjectRules(
  context: SubjectRuleContext,
  signal?: AbortSignal,
): Promise<{ items: SubjectRuleItem[] }> {
  return request("/query", context, signal);
}

export function checkSubjectRule(
  context: SubjectRuleContext,
  subject: string,
  rule: SubjectRuleConfig,
  signal?: AbortSignal,
): Promise<SubjectRuleCheck> {
  return request("/check", { ...context, subject, rule }, signal);
}

export function saveSubjectRule(
  context: SubjectRuleContext,
  subject: string,
  rule: SubjectRuleConfig,
  signal?: AbortSignal,
): Promise<SubjectRuleCheck> {
  return request("", { ...context, subject, rule }, signal, "PUT");
}
