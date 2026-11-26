import { useState } from "react";
import { Clock, Plus, Trash2 } from "lucide-react";
import type { TimeInterval } from "../../store/useAppStore";
import { getSlotsForInterval } from "../../utils/scheduleTime";
import { dateKey, FULL_WEEK_DAYS } from "./dates";

interface Props {
  intervals: TimeInterval[];
  onAdd: (interval: Omit<TimeInterval, "id">) => void;
  onRemove: (id: string) => void;
}

export function IntervalEditor({ intervals, onAdd, onRemove }: Props) {
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("15:00");
  const [type, setType] = useState<TimeInterval["type"]>("recurring");
  const [day, setDay] = useState(1);
  const [date, setDate] = useState(() => dateKey(new Date()));
  const slots = getSlotsForInterval(start, end);
  const canAdd = slots.length > 0 && (type === "recurring" || Boolean(date));

  return (
    <section className="calendar-interval">
      <h3>
        <Clock size={16} aria-hidden="true" /> Добавить временной интервал
      </h3>
      <form
        className="calendar-interval__form"
        onSubmit={(event) => {
          event.preventDefault();
          if (canAdd)
            onAdd({
              start,
              end,
              type,
              ...(type === "recurring" ? { day } : { date }),
            });
        }}
      >
        <label>
          Тип
          <select
            className="app-field"
            value={type}
            onChange={(event) =>
              setType(event.target.value as TimeInterval["type"])
            }
          >
            <option value="recurring">Еженедельно</option>
            <option value="specific">Конкретная дата</option>
          </select>
        </label>
        {type === "recurring" ? (
          <label>
            День недели
            <select
              className="app-field"
              value={day}
              onChange={(event) => setDay(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5, 6].map((option) => (
                <option key={option} value={option}>
                  {FULL_WEEK_DAYS[option]}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label>
            Дата
            <input
              className="app-field"
              type="date"
              value={date}
              required
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
        )}
        <label>
          Начало
          <input
            className="app-field"
            type="time"
            value={start}
            required
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <label>
          Окончание
          <input
            className="app-field"
            type="time"
            value={end}
            required
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>
        <span className="calendar-interval__pairs">
          Пары: {slots.join(", ") || "—"}
        </span>
        <button type="submit" className="btn-primary" disabled={!canAdd}>
          <Plus size={14} /> Добавить
        </button>
      </form>
      {intervals.length > 0 && (
        <>
          <h4>Сохранённые интервалы</h4>
          <ul className="calendar-interval__list">
            {intervals.map((interval) => (
              <li key={interval.id}>
                <strong>
                  {interval.start} – {interval.end}
                </strong>
                <span>
                  {interval.type === "recurring"
                    ? FULL_WEEK_DAYS[interval.day ?? 0]
                    : interval.date}
                </span>
                <small>
                  Пары:{" "}
                  {getSlotsForInterval(interval.start, interval.end).join(", ")}
                </small>
                <button
                  className="button-icon"
                  type="button"
                  aria-label={`Удалить интервал ${interval.start} – ${interval.end}`}
                  onClick={() => onRemove(interval.id)}
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
