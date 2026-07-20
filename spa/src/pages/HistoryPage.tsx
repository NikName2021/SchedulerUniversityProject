import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Archive,
  Ban,
  Calendar,
  CheckCircle2,
  Clock3,
  Download,
  History as HistoryIcon,
  LayoutDashboard,
  RefreshCcw,
  RotateCcw,
  Send,
  Users,
  XCircle,
} from "lucide-react";
import { API_BASE_URL } from "../api/apiConfig";

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
}

const hasScheduleResult = (status: string) =>
  status === "success" || status === "partial";

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

const HistoryPage: React.FC = () => {
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const fetchTasks = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/scheduler/tasks`);
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

  const handleDownload = (taskId: number) =>
    window.open(
      `${API_BASE_URL}/api/v1/scheduler/export?task_id=${taskId}`,
      "_blank",
    );

  const runTaskAction = async (
    taskId: number,
    action: "cancel" | "retry" | "publish" | "archive",
  ) => {
    const response = await fetch(
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
    const response = await fetch(
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

  if (isLoading) {
    return (
      <div className="loading-state">
        <span className="loading-state__spinner" /> Загрузка журнала операций…
      </div>
    );
  }

  return (
    <div className="enterprise-page animate-fade-in">
      <section className="enterprise-page__header">
        <div>
          <h2 className="enterprise-page__heading">Реестр расчётов</h2>
          <p className="enterprise-page__description">
            Статус задач, версии сформированного расписания и доступные
            действия.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => void fetchTasks}
        >
          <RefreshCcw size={16} /> Обновить
        </button>
      </section>

      {tasks.length > 0 ? (
        <section className="task-registry app-panel">
          <div className="task-registry__head">
            <span>Расчёт</span>
            <span>Параметры</span>
            <span>Статус</span>
            <span>Публикация</span>
            <span>Действия</span>
          </div>
          <div className="task-registry__body">
            {tasks.map((task) => {
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
                  <div className="task-row__actions">
                    {(task.status === "queued" ||
                      task.status === "running") && (
                      <button
                        type="button"
                        className="button-icon button-danger"
                        title="Отменить расчёт"
                        onClick={() => void runTaskAction(task.id, "cancel")}
                      >
                        <Ban size={16} />
                      </button>
                    )}
                    {(task.status === "failed" ||
                      task.status === "canceled") && (
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
                    {(task.status === "partial" ||
                      task.status === "failed") && (
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
                        onClick={() => handleDownload(task.id)}
                      >
                        <Download size={16} />
                      </button>
                    )}
                    {hasScheduleResult(task.status) && (
                      <button
                        type="button"
                        className="button-icon task-action--primary"
                        title="Открыть редактор"
                        onClick={() => navigate(`/schedule/${task.id}`)}
                      >
                        <LayoutDashboard size={16} />
                      </button>
                    )}
                  </div>
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
