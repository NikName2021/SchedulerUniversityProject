import { PAIR_TIMES } from "./scheduleTime.js";

export type DayRestrictionType = "specific" | "recurring";

export function getDayRestrictionKeys(
  date: string,
  type: DayRestrictionType,
): string[] {
  const prefix =
    type === "recurring" ? new Date(`${date}T00:00:00`).getDay() : date;
  return PAIR_TIMES.map((pair) => `${prefix}-${pair.num}`);
}

export function toggleDayRestrictions(
  current: string[],
  date: string,
  type: DayRestrictionType,
): string[] {
  const keys = getDayRestrictionKeys(date, type);
  if (keys.every((key) => current.includes(key))) {
    return current.filter((key) => !keys.includes(key));
  }
  return Array.from(new Set([...current, ...keys]));
}
