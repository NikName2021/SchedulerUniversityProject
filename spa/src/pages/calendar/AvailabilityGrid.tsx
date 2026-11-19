import { Fragment, useEffect, useRef } from "react";
import { CalendarDays, Check, Lock, ShieldCheck } from "lucide-react";
import type { Teacher } from "../../store/useAppStore";
import { getDayRestrictionKeys } from "../../utils/dayRestrictions";
import { PAIR_TIMES } from "../../utils/scheduleTime";
import { dateKey, FULL_WEEK_DAYS, WEEK_DAYS } from "./dates";

export type EditMode = "specific" | "recurring" | "time";

interface Props {
  teacher: Teacher;
  week: Date[];
  mode: EditMode;
  onToggle: (type: "specific" | "recurring", key: string) => void;
  onToggleDay: (type: "specific" | "recurring", date: string) => void;
  onSave: () => void;
}

const dayFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
});

export function AvailabilityGrid({
  teacher,
  week,
  mode,
  onToggle,
  onToggleDay,
  onSave,
}: Props) {
  const drag = useRef<{ mark: boolean; visited: Set<string> } | null>(null);

  useEffect(() => {
    const finish = () => {
      if (drag.current) {
        drag.current = null;
        onSave();
      }
    };
    window.addEventListener("mouseup", finish);
    window.addEventListener("blur", finish);
    return () => {
      window.removeEventListener("mouseup", finish);
      window.removeEventListener("blur", finish);
      finish();
    };
  }, [onSave]);

  const type = mode === "recurring" ? "recurring" : "specific";
  const whitelist = teacher.restrictions.mode === "whitelist";
  const restrictions = new Set(teacher.restrictions[type]);
  const recurring = new Set(teacher.restrictions.recurring);
  const specific = new Set(teacher.restrictions.specific);
  const today = dateKey(new Date());

  return (
    <div className="calendar-grid-content">
      <div className="calendar-week" aria-label="Доступность по парам">
        <div className="calendar-week__heading" aria-hidden="true" />
        {week.map((day, index) => {
          const date = dateKey(day);
          const selected = getDayRestrictionKeys(date, type).every((key) =>
            restrictions.has(key),
          );
          const action = selected
            ? whitelist
              ? "Снять допуск"
              : "Снять блок"
            : whitelist
              ? "Разрешить весь день"
              : "Заблокировать весь день";
          const label = `${action}: ${type === "recurring" ? FULL_WEEK_DAYS[day.getDay()] + " (еженедельно)" : date}`;
          return (
            <div
              className={`calendar-week__heading calendar-week__day${date === today ? " calendar-week__day--today" : ""}`}
              key={date}
            >
              <small>{WEEK_DAYS[index]}</small>
              <time className="calendar-week__date" dateTime={date}>
                {dayFormatter.format(day)}
              </time>
              <button
                type="button"
                className="calendar-week__day-toggle"
                aria-label={label}
                title={label}
                aria-pressed={selected}
                onClick={() => onToggleDay(type, date)}
              >
                <span className="calendar-week__day-toggle-label">
                  {selected ? action : "Весь день"}
                </span>
                {selected ? (
                  <Check
                    className="calendar-week__day-toggle-icon"
                    size={14}
                    aria-hidden="true"
                  />
                ) : (
                  <CalendarDays
                    className="calendar-week__day-toggle-icon"
                    size={14}
                    aria-hidden="true"
                  />
                )}
              </button>
            </div>
          );
        })}
        {PAIR_TIMES.map((pair, index) => (
          <Fragment key={pair.label}>
            <div className="calendar-week__time">
              <strong>{index + 1}</strong>
              <small>{pair.label}</small>
            </div>
            {week.map((day) => {
              const date = dateKey(day);
              const recurringKey = `${day.getDay()}-${index + 1}`;
              const specificKey = `${date}-${index + 1}`;
              const repeating = recurring.has(recurringKey);
              const marked = repeating || specific.has(specificKey);
              const blocked = whitelist ? !marked : marked;
              const key = type === "recurring" ? recurringKey : specificKey;
              const checked = restrictions.has(key);
              const state = blocked
                ? "blocked"
                : whitelist
                  ? "allowed"
                  : "available";
              return (
                <button
                  key={date}
                  type="button"
                  className={`calendar-week__slot calendar-week__slot--${state}${repeating ? " calendar-week__slot--recurring" : ""}`}
                  disabled={mode === "time"}
                  aria-label={`${date}, ${index + 1} пара: ${blocked ? "недоступно" : "доступно"}`}
                  aria-pressed={checked}
                  onMouseDown={(event) => {
                    if (event.button !== 0 || mode === "time") return;
                    drag.current = { mark: !checked, visited: new Set([key]) };
                    onToggle(type, key);
                  }}
                  onMouseEnter={() => {
                    const selection = drag.current;
                    if (
                      mode === "time" ||
                      !selection ||
                      selection.visited.has(key)
                    )
                      return;
                    selection.visited.add(key);
                    if (checked !== selection.mark) onToggle(type, key);
                  }}
                  onClick={(event) => {
                    if (mode === "time" || event.detail > 0) return;
                    onToggle(type, key);
                    onSave();
                  }}
                  onDragStart={(event) => event.preventDefault()}
                >
                  {blocked ? (
                    <Lock size={14} aria-hidden="true" />
                  ) : (
                    whitelist && <ShieldCheck size={14} aria-hidden="true" />
                  )}
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
