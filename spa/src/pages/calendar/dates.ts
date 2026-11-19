export const WEEK_DAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"];
export const FULL_WEEK_DAYS = [
  "Воскресенье",
  "Понедельник",
  "Вторник",
  "Среда",
  "Четверг",
  "Пятница",
  "Суббота",
];

export function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function addDays(date: Date, offset: number) {
  const result = new Date(date);
  result.setDate(date.getDate() + offset);
  return result;
}

export function getStudyWeek(date: Date) {
  const monday = addDays(date, -((date.getDay() + 6) % 7));
  return WEEK_DAYS.map((_, index) => addDays(monday, index));
}
