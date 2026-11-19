import { useState } from "react";
import { Minus, Plus, Search, X } from "lucide-react";
import { Modal } from "../../components/Modal";
import type { PlanningWeek, WeeklyDemand } from "./types";

type DemandFilter = "all" | "active" | "excluded";

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
  const [filter, setFilter] = useState<DemandFilter>("all");
  const title = `Нагрузка недели ${week.sequence_number}`;
  const normalizedQuery = query.trim().toLowerCase();
  const matches = demands.filter((item) => {
    if (filter === "active" && item.lessons_count <= 0) return false;
    if (filter === "excluded" && item.lessons_count > 0) return false;
    if (!normalizedQuery) return true;
    return `${item.event_name || ""} ${item.teacher_name || ""} ${item.stream_type || ""}`
      .toLowerCase()
      .includes(normalizedQuery);
  });
  const activeCount = demands.filter((item) => item.lessons_count > 0).length;
  const totalLessons = demands.reduce(
    (sum, item) => sum + Math.max(0, item.lessons_count),
    0,
  );

  const clampLessons = (value: number) =>
    Math.max(0, Math.min(14, Number.isFinite(value) ? Math.trunc(value) : 0));

  const clampPriority = (value: number) =>
    Math.max(1, Math.min(10, Number.isFinite(value) ? Math.trunc(value) : 5));

  return (
    <Modal
      label={title}
      onClose={onClose}
      className="app-dialog--wide generation-demand-dialog"
    >
      <div className="app-dialog__body generation-demand-dialog__body">
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

        <div className="generation-demand-toolbar">
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
          <div
            className="generation-demand-filters"
            role="group"
            aria-label="Фильтр потоков"
          >
            {(
              [
                ["all", `Все (${demands.length})`],
                ["active", `Активные (${activeCount})`],
                ["excluded", `Исключённые (${demands.length - activeCount})`],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className="app-toggle"
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="app-table-scroll generation-demand-scroll">
          {matches.length === 0 ? (
            <p className="empty-state">
              Потоки по выбранному фильтру не найдены
            </p>
          ) : (
            <table className="app-table generation-demand-table">
              <thead>
                <tr>
                  <th scope="col">Поток</th>
                  <th scope="col">Тип</th>
                  <th scope="col">Занятий</th>
                  <th scope="col" title="От 1 (низкий) до 10 (высокий)">
                    Приоритет (1–10)
                  </th>
                </tr>
              </thead>
              <tbody>
                {matches.map((item) => {
                  const name = item.event_name || `Поток ${item.stream_id}`;
                  const isExcluded = item.lessons_count === 0;
                  return (
                    <tr
                      key={item.stream_id}
                      className={
                        isExcluded ? "generation-demand-row--excluded" : ""
                      }
                    >
                      <th scope="row">
                        <strong>{name}</strong>
                        <small>
                          {item.teacher_name || "Преподаватель не назначен"}
                        </small>
                      </th>
                      <td>{item.stream_type || "—"}</td>
                      <td>
                        <div className="generation-demand-stepper">
                          <button
                            type="button"
                            className="button-icon"
                            aria-label={`Уменьшить занятия: ${name}`}
                            disabled={saving || item.lessons_count <= 0}
                            onClick={() =>
                              onChange(item.stream_id, {
                                lessons_count: clampLessons(
                                  item.lessons_count - 1,
                                ),
                              })
                            }
                          >
                            <Minus size={14} />
                          </button>
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
                                lessons_count: clampLessons(
                                  Number(event.target.value),
                                ),
                              })
                            }
                          />
                          <button
                            type="button"
                            className="button-icon"
                            aria-label={`Увеличить занятия: ${name}`}
                            disabled={saving || item.lessons_count >= 14}
                            onClick={() =>
                              onChange(item.stream_id, {
                                lessons_count: clampLessons(
                                  item.lessons_count + 1,
                                ),
                              })
                            }
                          >
                            <Plus size={14} />
                          </button>
                        </div>
                      </td>
                      <td>
                        <input
                          className="app-field generation-demand-priority"
                          aria-label={`Приоритет: ${name}`}
                          type="number"
                          min={1}
                          max={10}
                          value={item.priority}
                          disabled={saving}
                          onChange={(event) =>
                            onChange(item.stream_id, {
                              priority: clampPriority(
                                Number(event.target.value),
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
          )}
        </div>

        {error && (
          <p className="notice notice--danger" role="alert">
            {error}
          </p>
        )}
        <div className="generation-demand-footer">
          <span className="text-text-secondary">
            Активно потоков: <strong>{activeCount}</strong> · Всего пар:{" "}
            <strong>{totalLessons}</strong>
          </span>
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
      </div>
    </Modal>
  );
}
