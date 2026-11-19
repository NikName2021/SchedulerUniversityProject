import { useState } from "react";
import { Search, X } from "lucide-react";
import { Modal } from "../../components/Modal";
import type { PlanningWeek, WeeklyDemand } from "./types";

interface Props {
  week: PlanningWeek;
  demands: WeeklyDemand[];
  saving: boolean;
  error?: string;
  onClose: () => void;
  onSave: () => void;
  onChange: (
    id: number,
    value: Partial<Pick<WeeklyDemand, "lessons_count" | "priority">>,
  ) => void;
}

export function WeeklyDemandDialog({
  week,
  demands,
  saving,
  error,
  onClose,
  onSave,
  onChange,
}: Props) {
  const [query, setQuery] = useState("");
  const title = `Нагрузка недели ${week.sequence_number}`;
  const matches = demands.filter((item) =>
    `${item.event_name || ""} ${item.teacher_name || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );

  return (
    <Modal label={title} onClose={onClose} className="app-dialog--wide">
      <div className="app-dialog__body">
        <div className="app-section--header">
          <div>
            <h2>{title}</h2>
            <p className="text-text-secondary">
              {week.starts_on} — {week.ends_on} · 0 исключает поток из недели
            </p>
          </div>
          <button
            type="button"
            className="button-icon"
            aria-label="Закрыть нагрузку недели"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <label className="app-search">
          <Search size={16} aria-hidden="true" />
          <input
            className="app-field"
            aria-label="Поиск дисциплины или преподавателя"
            placeholder="Поиск дисциплины или преподавателя"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="app-table-scroll">
          <table className="app-table generation-demand-table">
            <thead>
              <tr>
                <th scope="col">Поток</th>
                <th scope="col">Тип</th>
                <th scope="col">Занятий</th>
                <th scope="col">Приоритет</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((item) => {
                const name = item.event_name || `Поток ${item.stream_id}`;
                return (
                  <tr key={item.stream_id}>
                    <th scope="row">
                      <strong>{name}</strong>
                      <small>
                        {item.teacher_name || "Преподаватель не назначен"}
                      </small>
                    </th>
                    <td>{item.stream_type || "—"}</td>
                    <td>
                      <input
                        className="app-field"
                        aria-label={`Занятий: ${name}`}
                        type="number"
                        min={0}
                        max={14}
                        value={item.lessons_count}
                        disabled={saving}
                        onChange={(event) =>
                          onChange(item.stream_id, {
                            lessons_count: Math.max(
                              0,
                              Math.min(14, Number(event.target.value)),
                            ),
                          })
                        }
                      />
                    </td>
                    <td>
                      <input
                        className="app-field"
                        aria-label={`Приоритет: ${name}`}
                        type="number"
                        min={1}
                        max={10}
                        value={item.priority}
                        disabled={saving}
                        onChange={(event) =>
                          onChange(item.stream_id, {
                            priority: Math.max(
                              1,
                              Math.min(10, Number(event.target.value)),
                            ),
                          })
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {error && (
          <p className="notice notice--danger" role="alert">
            {error}
          </p>
        )}
        <div className="app-dialog__actions">
          <button className="btn-secondary" type="button" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn-primary"
            type="button"
            onClick={onSave}
            disabled={saving}
          >
            {saving ? "Сохранение…" : "Сохранить нагрузку"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
