import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Archive,
  Ban,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  History as HistoryIcon,
  Layers3,
  Link2,
  LayoutDashboard,
  RefreshCcw,
  RotateCcw,
  Send,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";
import { API_BASE_URL, apiFetch, openDownload } from "../api/apiConfig";

interface PlanningWeekSummary {
  id: number;
  sequence_number: number;
  starts_on: string;
  ends_on: string;
  period_id: number;
  period_name: string | null;
}

interface GenerationTask {
  id: number;
  created_at: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  groups: string[];
  holidays: string[];
  settings: Record<string, unknown>;
  result_count: number;
  error_message: string | null;
  total_components: number;
  completed_components: number;
  progress_percent: number;
  version_number: number;
  publication_status: "draft" | "published" | "archived";
  edit_revision: number;
  semester_batch_id: string | null;
  planning_week: PlanningWeekSummary | null;
}

interface SemesterBatch {
  id: string;
  tasks: GenerationTask[];
  createdAt: string;
  periodName: string;
}

const hasScheduleResult = (status: string) =>
  status === "success" || status === "partial";

const formatSemesterBatchId = (batchId: string) =>
  batchId.replace(/-/g, "").slice(0, 8).toUpperCase();

const statusMeta = (status: string) => {
  if (status === "success")
    return { label: "Готово", tone: "success", Icon: CheckCircle2 };
  if (status === "partial")
    return { label: "Частично", tone: "warning", Icon: AlertTriangle };
  if (status === "failed")
    return { label: "Ошибка", tone: "danger", Icon: XCircle };
  if (status === "canceled")
    return { label: "Отменено", tone: "neutral", Icon: Ban };
  return { label: "Выполняется", tone: "warning", Icon: Clock3 };
};

const publicationLabel = (task: GenerationTask) => {
  if (task.publication_status === "published") return "Опубликовано";
  if (task.publication_status === "archived") return "Архив";
  return `Черновик · редакция ${task.edit_revision || 0}`;
};

const batchStatus = (tasks: GenerationTask[]) => {
  if (
    tasks.some((task) => task.status === "running" || task.status === "queued")
  ) {
    return statusMeta("running");
  }
  if (tasks.every((task) => task.status === "canceled"))
    return statusMeta("canceled");
  if (
    tasks.some((task) => task.status === "failed" || task.status === "partial")
  ) {
    return statusMeta("partial");
  }
  if (tasks.every((task) => task.status === "success"))
    return statusMeta("success");
  return statusMeta("partial");
};

const HistoryPage: React.FC = () => {
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(
    new Set(),
  );
  const navigate = useNavigate();

  const fetchTasks = useCallback(async () => {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/v1/scheduler/tasks`);
      if (!response.ok) throw new Error("Не удалось загрузить задачи");
      setTasks(await response.json());
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchTasks();
    const intervalId = window.setInterval(() => void fetchTasks(), 3000);
    return () => window.clearInterval(intervalId);
  }, [fetchTasks]);

  const registryItems = useMemo(() => {
    const batches = new Map<string, GenerationTask[]>();
    const standalone: GenerationTask[] = [];
    for (const task of tasks) {
      if (task.semester_batch_id) {
        const batch = batches.get(task.semester_batch_id) || [];
        batch.push(task);
        batches.set(task.semester_batch_id, batch);
      } else {
        standalone.push(task);
      }
    }
    const semesterBatches: SemesterBatch[] = Array.from(batches.entries()).map(
      ([id, batchTasks]) => {
        const sortedTasks = [...batchTasks].sort(
          (left, right) =>
            (left.planning_week?.sequence_number || 0) -
            (right.planning_week?.sequence_number || 0),
        );
        return {
          id,
          tasks: sortedTasks,
          createdAt: batchTasks.reduce(
            (latest, task) =>
              latest > task.created_at ? latest : task.created_at,
            batchTasks[0].created_at,
          ),
          periodName:
            sortedTasks[0]?.planning_week?.period_name || "Учебный период",
        };
      },
    );
    return [
      ...semesterBatches.map((batch) => ({
        kind: "semester" as const,
        createdAt: batch.createdAt,
        batch,
      })),
      ...standalone.map((task) => ({
        kind: "task" as const,
        createdAt: task.created_at,
        task,
      })),
    ].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
  }, [tasks]);

  const runTaskAction = async (
    taskId: number,
    action: "cancel" | "retry" | "publish" | "archive",
  ) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/scheduler/tasks/${taskId}/${action}`,
      { method: "POST" },
    );
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      alert(payload.detail || "Операция не выполнена");
      return;
    }
    await fetchTasks();
  };

  const showDiagnostics = async (taskId: number) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/scheduler/tasks/${taskId}/diagnostics`,
    );
    const payload = (await response.json()) as {
      counts?: Record<string, number>;
    };
    const summary = Object.entries(payload.counts || {})
      .map(([kind, count]) => `${kind}: ${count}`)
      .join("\n");
    alert(summary || "Проблем при генерации не обнаружено");
  };

  const handleInherit = (task: GenerationTask) => {
    navigate("/generation", {
      state: {
        groups: task.groups || [],
        holidays: task.holidays || [],
        settings: task.settings || {},
        start_date: task.start_date,
        end_date: task.end_date,
      },
    });
  };

  const formatDate = (date: string) => {
    const parsed = new Date(date);
    return Number.isNaN(parsed.getTime())
      ? "Дата неизвестна"
      : parsed.toLocaleString("ru-RU", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
  };

  const openSemester = (batchId: string, week?: PlanningWeekSummary | null) => {
    const params = new URLSearchParams({ semester_batch_id: batchId });
    if (week) params.set("week", week.starts_on);
    navigate(`/schedule?${params.toString()}`);
  };

  const semesterSchedulePath = (
    batchId: string,
    week?: PlanningWeekSummary | null,
  ) => {
    const params = new URLSearchParams({ semester_batch_id: batchId });
    if (week) params.set("week", week.starts_on);
    return `/schedule?${params.toString()}`;
  };

  const shareSchedule = async (path: string, title: string) => {
    const url = new URL(path, window.location.origin).toString();
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
      } else {
        await navigator.clipboard.writeText(url);
        alert("Ссылка на расчёт скопирована");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      window.prompt("Скопируйте ссылку на расчёт", url);
    }
  };

  const deleteTask = async (task: GenerationTask) => {
    if (
      !window.confirm(
        `Удалить расчёт #${task.id} и всё связанное расписание? Это действие нельзя отменить.`,
      )
    ) {
      return;
    }
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/scheduler/tasks/${task.id}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      alert(payload.detail || "Не удалось удалить расчёт");
      return;
    }
    await fetchTasks();
  };

  const deleteSemesterBatch = async (batch: SemesterBatch) => {
    const displayId = formatSemesterBatchId(batch.id);
    if (
      !window.confirm(
        `Удалить семестровый расчёт #${displayId} и все ${batch.tasks.length} недель? Это действие нельзя отменить.`,
      )
    ) {
      return;
    }
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/scheduler/semester-batches/${encodeURIComponent(batch.id)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      alert(payload.detail || "Не удалось удалить семестровый расчёт");
      return;
    }
    setExpandedBatches((current) => {
      const next = new Set(current);
      next.delete(batch.id);
      return next;
    });
    await fetchTasks();
  };

  const renderTaskActions = (
    task: GenerationTask,
    semesterBatchId?: string,
  ) => (
    <div className="task-row__actions">
      {(task.status === "queued" || task.status === "running") && (
        <button
          type="button"
          className="button-icon button-danger"
          title="Отменить расчёт"
          onClick={() => void runTaskAction(task.id, "cancel")}
        >
          <Ban size={16} />
        </button>
      )}
      {(task.status === "failed" || task.status === "canceled") && (
        <button
          type="button"
          className="button-icon"
          title="Повторить расчёт"
          onClick={() => void runTaskAction(task.id, "retry")}
        >
          <RotateCcw size={16} />
        </button>
      )}
      {hasScheduleResult(task.status) &&
        task.publication_status === "draft" && (
          <button
            type="button"
            className="button-icon task-action--success"
            title="Опубликовать версию"
            onClick={() => void runTaskAction(task.id, "publish")}
          >
            <Send size={16} />
          </button>
        )}
      {task.publication_status === "published" && (
        <button
          type="button"
          className="button-icon"
          title="Отправить в архив"
          onClick={() => void runTaskAction(task.id, "archive")}
        >
          <Archive size={16} />
        </button>
      )}
      {(task.status === "partial" || task.status === "failed") && (
        <button
          type="button"
          className="button-icon task-action--warning"
          title="Показать диагностику"
          onClick={() => void showDiagnostics(task.id)}
        >
          <AlertTriangle size={16} />
        </button>
      )}
      <button
        type="button"
        className="button-icon"
        title="Наследовать параметры"
        onClick={() => handleInherit(task)}
      >
        <RefreshCcw size={16} />
      </button>
      {hasScheduleResult(task.status) && (
        <button
          type="button"
          className="button-icon task-action--primary"
          title="Скачать Excel"
          onClick={() =>
            openDownload(
              `${API_BASE_URL}/api/v1/scheduler/export?task_id=${task.id}`,
            )
          }
        >
          <Download size={16} />
        </button>
      )}
      {hasScheduleResult(task.status) && (
        <button
          type="button"
          className="button-icon task-action--primary"
          title="Открыть расписание"
          onClick={() =>
            semesterBatchId
              ? openSemester(semesterBatchId, task.planning_week)
              : navigate(`/schedule/${task.id}`)
          }
        >
          <LayoutDashboard size={16} />
        </button>
      )}
      {hasScheduleResult(task.status) && (
        <button
          type="button"
          className="button-icon task-action--primary"
          title="Поделиться ссылкой"
          onClick={() =>
            void shareSchedule(
              semesterBatchId
                ? semesterSchedulePath(semesterBatchId, task.planning_week)
                : `/schedule/${task.id}`,
              `Расписание #${task.id}`,
            )
          }
        >
          <Link2 size={16} />
        </button>
      )}
      <button
        type="button"
        className="button-icon button-danger"
        title="Удалить расчёт"
        onClick={() => void deleteTask(task)}
      >
        <Trash2 size={16} />
      </button>
    </div>
  );

  if (isLoading)
    return (
      <div className="loading-state">
        <span className="loading-state__spinner" /> Загрузка журнала операций…
      </div>
    );

  return (
    <div className="enterprise-page animate-fade-in">
      <section className="enterprise-page__header">
        <div>
          <h2 className="enterprise-page__heading">Реестр расчётов</h2>
          <p className="enterprise-page__description">
            Семестровые запуски объединены в одну операцию с детализацией по
            неделям.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void fetchTasks()}
          >
            <RefreshCcw size={16} /> Обновить
          </button>
        </div>
      </section>

      {registryItems.length > 0 ? (
        <section className="task-registry app-panel">
          <div className="task-registry__head">
            <span>Расчёт</span>
            <span>Параметры</span>
            <span>Статус</span>
            <span>Публикация</span>
            <span>Действия</span>
          </div>
          <div className="task-registry__body">
            {registryItems.map((item) => {
              if (item.kind === "task") {
                const task = item.task;
                const status = statusMeta(task.status);
                const StatusIcon = status.Icon;
                return (
                  <article className="task-row" key={task.id}>
                    <div className="task-row__identity">
                      <div
                        className={`task-row__status-icon task-row__status-icon--${status.tone}`}
                      >
                        <StatusIcon size={18} />
                      </div>
                      <div>
                        <strong>Расчёт #{task.id}</strong>
                        <span>
                          Версия {task.version_number || 1} ·{" "}
                          {formatDate(task.created_at)}
                        </span>
                      </div>
                    </div>
                    <div className="task-row__parameters">
                      <span>
                        <Users size={14} /> {task.groups?.length || 0} групп
                      </span>
                      {hasScheduleResult(task.status) && (
                        <span>
                          <Calendar size={14} /> {task.result_count} пар
                        </span>
                      )}
                      {!hasScheduleResult(task.status) &&
                        task.status !== "failed" && (
                          <span>
                            {task.progress_percent || 0}% ·{" "}
                            {task.completed_components || 0}/
                            {task.total_components || 0}
                          </span>
                        )}
                      {task.error_message && (
                        <small title={task.error_message}>
                          {task.error_message}
                        </small>
                      )}
                    </div>
                    <div>
                      <span
                        className={`status-badge status-badge--${status.tone}`}
                      >
                        <StatusIcon size={13} /> {status.label}
                      </span>
                    </div>
                    <div>
                      <span className="task-row__publication">
                        {publicationLabel(task)}
                      </span>
                    </div>
                    {renderTaskActions(task)}
                  </article>
                );
              }

              const batch = item.batch;
              const status = batchStatus(batch.tasks);
              const StatusIcon = status.Icon;
              const expanded = expandedBatches.has(batch.id);
              const completedWeeks = batch.tasks.filter((task) =>
                hasScheduleResult(task.status),
              ).length;
              const scheduledLessons = batch.tasks.reduce(
                (sum, task) => sum + task.result_count,
                0,
              );
              const displayId = formatSemesterBatchId(batch.id);
              return (
                <article className="semester-task" key={batch.id}>
                  <div className="task-row task-row--semester">
                    <button
                      type="button"
                      className="semester-task__toggle"
                      onClick={() =>
                        setExpandedBatches((current) => {
                          const next = new Set(current);
                          if (next.has(batch.id)) next.delete(batch.id);
                          else next.add(batch.id);
                          return next;
                        })
                      }
                      aria-label={
                        expanded ? "Свернуть недели" : "Развернуть недели"
                      }
                    >
                      {expanded ? (
                        <ChevronDown size={17} />
                      ) : (
                        <ChevronRight size={17} />
                      )}
                    </button>
                    <div className="task-row__identity">
                      <div
                        className={`task-row__status-icon task-row__status-icon--${status.tone}`}
                      >
                        <Layers3 size={18} />
                      </div>
                      <div>
                        <strong title={`Полный ID: ${batch.id}`}>
                          Семестровый расчёт #{displayId}
                        </strong>
                        <span>
                          {batch.periodName} · {formatDate(batch.createdAt)}
                        </span>
                      </div>
                    </div>
                    <div className="task-row__parameters">
                      <span>
                        <Users size={14} /> {batch.tasks[0]?.groups.length || 0}{" "}
                        групп
                      </span>
                      <span>
                        <Calendar size={14} /> {batch.tasks.length} нед.
                      </span>
                      <span>{scheduledLessons} пар</span>
                    </div>
                    <div>
                      <span
                        className={`status-badge status-badge--${status.tone}`}
                      >
                        <StatusIcon size={13} /> {completedWeeks}/
                        {batch.tasks.length} недель
                      </span>
                    </div>
                    <div>
                      <span className="task-row__publication">
                        {status.label}
                      </span>
                    </div>
                    <div className="task-row__actions">
                      <button
                        type="button"
                        className="button-icon task-action--primary"
                        title="Открыть расписание семестра"
                        onClick={() => openSemester(batch.id)}
                      >
                        <LayoutDashboard size={16} />
                      </button>
                      <button
                        type="button"
                        className="button-icon task-action--primary"
                        title="Скачать расписание семестра"
                        onClick={() =>
                          openDownload(
                            `${API_BASE_URL}/api/v1/scheduler/export?semester_batch_id=${encodeURIComponent(batch.id)}`,
                          )
                        }
                      >
                        <Download size={16} />
                      </button>
                      <button
                        type="button"
                        className="button-icon task-action--primary"
                        title="Поделиться ссылкой на семестровый расчёт"
                        onClick={() =>
                          void shareSchedule(
                            semesterSchedulePath(batch.id),
                            `Семестровое расписание #${displayId} · ${batch.periodName}`,
                          )
                        }
                      >
                        <Link2 size={16} />
                      </button>
                      <button
                        type="button"
                        className="button-icon button-danger"
                        title="Удалить семестровый расчёт"
                        onClick={() => void deleteSemesterBatch(batch)}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  {expanded && (
                    <div className="semester-task__weeks">
                      {batch.tasks.map((task) => {
                        const weekStatus = statusMeta(task.status);
                        const WeekStatusIcon = weekStatus.Icon;
                        return (
                          <div className="semester-week-row" key={task.id}>
                            <div className="semester-week-row__title">
                              <span>
                                Неделя{" "}
                                {task.planning_week?.sequence_number || "—"} ·
                                расчёт #{task.id}
                              </span>
                              <small>
                                {task.planning_week
                                  ? `${task.planning_week.starts_on} — ${task.planning_week.ends_on}`
                                  : formatDate(task.created_at)}
                              </small>
                            </div>
                            <div>{task.result_count} пар</div>
                            <div>
                              <span
                                className={`status-badge status-badge--${weekStatus.tone}`}
                              >
                                <WeekStatusIcon size={13} /> {weekStatus.label}
                              </span>
                            </div>
                            <div>{publicationLabel(task)}</div>
                            {renderTaskActions(task, batch.id)}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      ) : (
        <section className="empty-registry app-panel">
          <HistoryIcon size={32} />
          <h3>Расчётов пока нет</h3>
          <p>
            Запустите первый расчёт расписания — его статус и версии появятся в
            этом журнале.
          </p>
        </section>
      )}
    </div>
  );
};

export default HistoryPage;
