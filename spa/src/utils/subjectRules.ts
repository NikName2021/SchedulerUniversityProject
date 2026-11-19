export const SUBJECT_WEEKDAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"];

export interface SubjectRuleConfig {
  lectures: number;
  seminars: number;
  laboratories: number;
  days_per_week: number;
  weekdays: number[];
  days_hard: boolean;
  lecture_before_practice: boolean;
  time_preference: "morning" | "day" | "evening";
}

export interface SubjectRuleContext {
  groups: string[];
  start_date: string;
  end_date: string;
  week_ids: number[];
  enabled_types: string[];
  holidays: string[];
}

export interface SubjectRuleItem {
  subject: string;
  groups: string[];
  rule: SubjectRuleConfig;
  saved: boolean;
  mixed: boolean;
}

export interface SubjectRuleCheck {
  can_save: boolean;
  errors: string[];
  warnings: string[];
  total_per_week: number;
  preview: Array<{
    date: string;
    lesson_number: number;
    type: "lec" | "sem" | "lab";
    groups: string[];
  }>;
}

export function ruleLessonCount(rule: SubjectRuleConfig): number {
  return rule.lectures + rule.seminars + rule.laboratories;
}

export function ruleValidationError(rule: SubjectRuleConfig): string | null {
  if (
    [rule.lectures, rule.seminars, rule.laboratories].some(
      (count) => !Number.isInteger(count) || count < 0 || count > 14,
    )
  ) {
    return "Для каждого типа выберите от 0 до 14 пар";
  }
  const total = ruleLessonCount(rule);
  if (!total) return "Добавьте хотя бы одно занятие";
  if (
    !Number.isInteger(rule.days_per_week) ||
    rule.days_per_week < 1 ||
    rule.days_per_week > 6 ||
    rule.days_per_week > total
  ) {
    return "Учебных дней должно быть от 1 до 6, но не больше числа пар";
  }
  if (rule.weekdays.some((day) => !Number.isInteger(day) || day < 0 || day > 5))
    return "Выберите дни с понедельника по субботу";
  if (
    rule.days_hard &&
    rule.weekdays.length > 0 &&
    new Set(rule.weekdays).size < rule.days_per_week
  ) {
    return "Выбранных дней меньше, чем учебных дней в неделю";
  }
  return null;
}

export function applyRulePreset(
  rule: SubjectRuleConfig,
  seminars: 1 | 2,
): SubjectRuleConfig {
  return {
    ...rule,
    lectures: 1,
    seminars,
    laboratories: 0,
    days_per_week: Math.min(rule.days_per_week, seminars + 1),
  };
}

export function subjectRuleSummary(rule: SubjectRuleConfig): string {
  return [
    rule.lectures ? `Лекции: ${rule.lectures}` : "",
    rule.seminars ? `Семинары: ${rule.seminars}` : "",
    rule.laboratories ? `Лабораторные: ${rule.laboratories}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function subjectRuleContextKey(context: SubjectRuleContext): string {
  return JSON.stringify({
    ...context,
    groups: [...context.groups].sort(),
    week_ids: [...context.week_ids].sort((a, b) => a - b),
    enabled_types: [...context.enabled_types].sort(),
    holidays: [...context.holidays].sort(),
  });
}
