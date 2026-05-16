import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../api/apiConfig";
import {
  History as HistoryIcon,
  Download,
  RefreshCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Calendar,
  Users as UsersIcon,
  Layout as LayoutIcon,
} from "lucide-react";

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
}

const HistoryPage: React.FC = () => {
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/tasks`);
      const data = await res.json();
      setTasks(data);
    } catch {
      console.error("Failed to fetch tasks");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleDownload = (taskId: number) => {
    window.open(
      `${API_BASE_URL}/api/v1/scheduler/export?task_id=${taskId}`,
      "_blank",
    );
  };

  const handleInherit = (task: GenerationTask) => {
    try {
      // Navigate to generation page with loaded state
      navigate("/generation", {
        state: {
          groups: task.groups || [],
          holidays: task.holidays || [],
          settings: task.settings || {},
          start_date: task.start_date,
          end_date: task.end_date,
        },
      });
    } catch {
      console.error("Inherit error");
      alert("Не удалось загрузить параметры этой задачи.");
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return "Дата неизвестна";
      return d.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "Ошибка даты";
    }
  };

  if (isLoading)
    return (
      <div style={{ padding: "5rem", textAlign: "center" }}>
        <div
          className="spinner-mini"
          style={{
            margin: "0 auto 1rem",
            width: "30px",
            height: "30px",
            border: "3px solid #eee",
            borderTopColor: "var(--brand)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <div style={{ color: "var(--text-secondary)", fontWeight: 600 }}>
          Загрузка истории...
        </div>
      </div>
    );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "2rem",
        paddingBottom: "5rem",
      }}
      className="animate-fade-in"
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "2.5rem",
              fontWeight: 900,
              letterSpacing: "-0.02em",
              marginBottom: "0.5rem",
            }}
          >
            История
          </h1>
          <p style={{ color: "var(--text-secondary)", fontWeight: 600 }}>
            Просмотр и повторное использование прошлых расчетов
          </p>
        </div>
        <button
          onClick={fetchTasks}
          style={{
            backgroundColor: "white",
            border: "1px solid var(--border-light)",
            padding: "0.75rem 1.25rem",
            borderRadius: "12px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            cursor: "pointer",
          }}
        >
          <RefreshCcw size={18} /> Обновить
        </button>
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {tasks.map((task) => (
          <div
            key={task.id}
            style={{
              backgroundColor: "white",
              borderRadius: "24px",
              padding: "1.5rem",
              border: "1px solid var(--border-light)",
              boxShadow: "var(--shadow-sm)",
              display: "grid",
              gridTemplateColumns: "auto 1fr auto auto",
              alignItems: "center",
              gap: "2rem",
            }}
          >
            {/* Status Icon */}
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor:
                  task.status === "success"
                    ? "rgba(16, 185, 129, 0.1)"
                    : task.status === "failed"
                      ? "rgba(239, 68, 68, 0.1)"
                      : "rgba(245, 158, 11, 0.1)",
                color:
                  task.status === "success"
                    ? "#10b981"
                    : task.status === "failed"
                      ? "#ef4444"
                      : "#f59e0b",
              }}
            >
              {task.status === "success" ? (
                <CheckCircle2 size={24} />
              ) : task.status === "failed" ? (
                <XCircle size={24} />
              ) : (
                <Clock size={24} />
              )}
            </div>

            {/* Info */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.25rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                }}
              >
                <span style={{ fontWeight: 800, fontSize: "1.125rem" }}>
                  Расчет #{task.id}
                </span>
                <span
                  style={{
                    fontSize: "0.625rem",
                    fontWeight: 900,
                    textTransform: "uppercase",
                    padding: "2px 8px",
                    borderRadius: "20px",
                    backgroundColor:
                      task.status === "success"
                        ? "rgba(16, 185, 129, 0.1)"
                        : "rgba(245, 158, 11, 0.1)",
                    color: task.status === "success" ? "#10b981" : "#f59e0b",
                  }}
                >
                  {task.status === "success"
                    ? "Готово"
                    : task.status === "failed"
                      ? "Ошибка"
                      : "В процессе"}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "1.5rem",
                  color: "var(--text-secondary)",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                  }}
                >
                  <Calendar size={14} /> {formatDate(task.created_at)}
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                  }}
                >
                  <UsersIcon size={14} /> {task.groups ? task.groups.length : 0}{" "}
                  групп
                </div>
                {task.status === "success" && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      color: "#10b981",
                    }}
                  >
                    <CheckCircle2 size={14} /> {task.result_count} пар
                  </div>
                )}
              </div>
            </div>

            {/* Error message if failed */}
            {task.status === "failed" && (
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "#ef4444",
                  fontWeight: 600,
                  maxWidth: "300px",
                }}
              >
                {task.error_message}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                onClick={() => handleInherit(task)}
                style={{
                  padding: "0.75rem 1.25rem",
                  borderRadius: "12px",
                  border: "1px solid var(--border-light)",
                  backgroundColor: "white",
                  fontWeight: 700,
                  fontSize: "0.875rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <RefreshCcw size={16} /> Наследовать
              </button>
              {task.status === "success" && (
                <button
                  onClick={() => handleDownload(task.id)}
                  style={{
                    padding: "0.75rem 1.25rem",
                    borderRadius: "12px",
                    border: "none",
                    backgroundColor: "var(--brand)",
                    color: "white",
                    fontWeight: 700,
                    fontSize: "0.875rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    cursor: "pointer",
                    boxShadow: "0 4px 12px rgba(79, 70, 229, 0.2)",
                    transition: "all 0.2s",
                  }}
                >
                  <Download size={16} /> Скачать Excel
                </button>
              )}
              {task.status === "success" && (
                <button
                  onClick={() => navigate(`/schedule/${task.id}`)}
                  style={{
                    padding: "0.75rem 1.25rem",
                    borderRadius: "12px",
                    border: "1px solid var(--brand)",
                    backgroundColor: "rgba(79, 70, 229, 0.05)",
                    color: "var(--brand)",
                    fontWeight: 700,
                    fontSize: "0.875rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  <LayoutIcon size={16} /> Открыть редактор
                </button>
              )}
            </div>
          </div>
        ))}

        {tasks.length === 0 && (
          <div
            style={{
              padding: "5rem",
              textAlign: "center",
              backgroundColor: "white",
              borderRadius: "24px",
              border: "1px dashed var(--border-light)",
            }}
          >
            <HistoryIcon
              size={48}
              style={{ color: "var(--text-tertiary)", marginBottom: "1rem" }}
            />
            <h3 style={{ fontWeight: 800, color: "var(--text-secondary)" }}>
              История пуста
            </h3>
            <p style={{ fontSize: "0.875rem", color: "var(--text-tertiary)" }}>
              Запустите первый расчет, чтобы он появился здесь
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPage;
