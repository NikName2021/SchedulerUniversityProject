export const PAIR_TIMES = [
  { num: 1, label: "08:45 – 10:05", startMin: 525, endMin: 605 },
  { num: 2, label: "10:20 – 11:40", startMin: 620, endMin: 700 },
  { num: 3, label: "11:55 – 13:15", startMin: 715, endMin: 795 },
  { num: 4, label: "13:30 – 14:50", startMin: 810, endMin: 890 },
  { num: 5, label: "15:05 – 16:25", startMin: 905, endMin: 985 },
  { num: 6, label: "16:40 – 18:00", startMin: 1000, endMin: 1080 },
  { num: 7, label: "18:15 – 19:35", startMin: 1095, endMin: 1175 },
] as const;

export function timeToMinutes(hhmm: string): number {
  if (!/^\d{2}:\d{2}$/.test(hhmm)) {
    throw new RangeError("Time must use HH:MM");
  }
  const [hours, minutes] = hhmm.split(":").map(Number);
  if (hours > 23 || minutes > 59) {
    throw new RangeError("Time is outside the 24-hour clock");
  }
  return hours * 60 + minutes;
}

export function minutesToTime(minutesFromMidnight: number): string {
  if (
    !Number.isInteger(minutesFromMidnight) ||
    minutesFromMidnight < 0 ||
    minutesFromMidnight >= 24 * 60
  ) {
    throw new RangeError("Minutes must be an integer within one day");
  }
  const hours = Math.floor(minutesFromMidnight / 60);
  const minutes = minutesFromMidnight % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function getSlotsForInterval(start: string, end: string): number[] {
  const startMinutes = timeToMinutes(start);
  const endMinutes = timeToMinutes(end);
  if (endMinutes <= startMinutes) return [];

  return PAIR_TIMES.filter(
    (pair) => pair.startMin < endMinutes && pair.endMin > startMinutes,
  ).map((pair) => pair.num);
}
