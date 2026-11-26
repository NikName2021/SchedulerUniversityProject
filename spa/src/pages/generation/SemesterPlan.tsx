import { RefreshCcw, RotateCcw } from "lucide-react";
import { isActiveTask } from "../../hooks/usePolling";
import type {
  AcademicPeriod,
  BatchWeekState,
  PlanningWeek,
  SemesterDistributionResult,
} from "./types";

const statuses: Record<BatchWeekState["status"], string> = {
  pending: "Подготовка",
  queued: "В очереди",
  running: "Расчёт",
  success: "Готово",
  partial: "Частично",
  failed: "Ошибка",
  canceled: "Отменён",
};

interface Props {
  period: AcademicPeriod;
  counts: Record<number, number>;
  selected: number[];
  distribution: SemesterDistributionResult | null;
  batch: BatchWeekState[];
  busy: boolean;
  canDistribute: boolean;
  onDistribute: () => void;
  onSelect: (ids: number[]) => void;
  onEdit: (week: PlanningWeek) => void;
  onRetry: (item: BatchWeekState) => void;
}

export function SemesterPlan({
  period,
  counts,
  selected,
  distribution,
  batch,
  busy,
  canDistribute,
  onDistribute,
  onSelect,
  onEdit,
  onRetry,
}: Props) {
  const readyIds = period.weeks
    .filter((week) => counts[week.id] > 0)
    .map((week) => week.id);
  const allSelected =
    readyIds.length > 0 && readyIds.every((id) => selected.includes(id));
  const byWeek = new Map(batch.map((item) => [item.week.id, item]));

  return (
    <section className="app-panel app-section generation-semester">
      <div className="app-section--header">
        <h2>Недельные расчёты</h2>
        <button
          className="btn-secondary"
          type="button"
          onClick={onDistribute}
          disabled={!canDistribute || busy}
        >
          <RefreshCcw
            size={16}
            className={busy ? "animate-spin" : ""}
            aria-hidden="true"
          />
          {busy
            ? "Распределяем…"
            : readyIds.length
              ? "Перераспределить нагрузку"
              : "Распределить нагрузку"}
        </button>
      </div>
      {distribution && (
        <p className="notice notice--success" role="status">
          План: {distribution.planned_lessons} · Опубликовано:{" "}
          {distribution.published_lessons} · Распределено:{" "}
          {distribution.distributed_lessons}
        </p>
      )}
      {batch.length > 0 && (
        <p role="status" className="text-text-secondary">
          Завершено{" "}
          {
            batch.filter(
              (item) => item.status !== "pending" && !isActiveTask(item.status),
            ).length
          }{" "}
          из {batch.length} недель
        </p>
      )}
      {!readyIds.length && !batch.length ? (
        <p className="text-text-secondary">
          Недельный план появится после распределения нагрузки.
        </p>
      ) : (
        <>
          <button
            className="btn-secondary justify-self-start"
            type="button"
            onClick={() => onSelect(allSelected ? [] : readyIds)}
            disabled={!readyIds.length}
          >
            {allSelected
              ? "Снять выбор недель"
              : "Выбрать все недели с нагрузкой"}
          </button>
          <ul className="generation-weeks" aria-label="Учебные недели">
            {period.weeks.map((week) => {
              const item = byWeek.get(week.id);
              const count = counts[week.id] || 0;
              const checked = selected.includes(week.id);
              return (
                <li
                  className={checked ? "generation-week--selected" : ""}
                  key={week.id}
                >
                  <label>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={count <= 0}
                      onChange={() =>
                        onSelect(
                          checked
                            ? selected.filter((id) => id !== week.id)
                            : [...selected, week.id],
                        )
                      }
                    />
                    <span>
                      <strong>Неделя {week.sequence_number}</strong>
                      <small>
                        {week.starts_on} — {week.ends_on}
                      </small>
                    </span>
                  </label>
                  <div className="generation-week__actions">
                    <span>{count} пар</span>
                    {count > 0 && !item && (
                      <button
                        className="btn-secondary"
                        type="button"
                        onClick={() => onEdit(week)}
                        aria-label={`Настроить нагрузку недели ${week.sequence_number}`}
                      >
                        Настроить
                      </button>
                    )}
                    {item && (
                      <span>
                        {statuses[item.status]} · {item.progress}%
                      </span>
                    )}
                    {item?.error && (
                      <small className="text-danger">{item.error}</small>
                    )}
                    {item?.status === "failed" && item.taskId && (
                      <button
                        type="button"
                        className="button-icon"
                        aria-label={`Повторить расчёт недели ${week.sequence_number}`}
                        onClick={() => onRetry(item)}
                      >
                        <RotateCcw size={15} />
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
