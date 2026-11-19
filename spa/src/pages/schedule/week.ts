export const DAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
export const WEEK_DATE_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export const parseLocalDate = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
};

const formatDateKey = (value: Date) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;

export const getWeekKey = (value: string) => {
  const date = parseLocalDate(value);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return formatDateKey(date);
};

export const getWeekDayDate = (weekKey: string, dayIndex: number) => {
  const date = parseLocalDate(weekKey);
  date.setDate(date.getDate() + dayIndex);
  return formatDateKey(date);
};

export const getSlotKey = (date: string, lessonNumber: number) =>
  `${date}:${lessonNumber}`;

export const PAIRS = [
  { num: 1, time: "08:45-10:05" },
  { num: 2, time: "10:20-11:40" },
  { num: 3, time: "11:55-13:15" },
  { num: 4, time: "13:30-14:50" },
  { num: 5, time: "15:05-16:25" },
  { num: 6, time: "16:40-18:00" },
  { num: 7, time: "18:15-19:35" },
];
