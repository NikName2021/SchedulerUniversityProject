import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarDays,
  Eye,
  Pencil,
  RefreshCcw,
  Users,
} from "lucide-react";

import { API_BASE_URL, apiFetch } from "../api/apiConfig";

interface PublicScheduleSummary {
  id: number;
  title: string;
  owner_display_name: string;
  starts_on: string | null;
  ends_on: string | null;
  groups: string[];
  result_count: number;
  edit_revision: number;
  published_at: string;
  updated_at: string;
  can_edit: boolean;
  source_task_id: number | null;
}

interface PublicScheduleEntry {
  id: number;
  group_name: string;
  event_name: string;
  stream_type: string;
  teacher: string | null;
  room_id: string | null;
  date: string | null;
  lesson_number: number | null;
}

interface PublicScheduleDetails extends PublicScheduleSummary {
  entries: PublicScheduleEntry[];
}

const formatDate = (value: string | null) =>
  value
    ? new Date(value).toLocaleDateString("ru-RU", {
        timeZone: "Europe/Moscow",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "—";

const formatTimestamp = (value: string) =>
  new Date(value).toLocaleString("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export const PublishedSchedulesPage = () => {
  const { publicationId } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<PublicScheduleSummary[]>([]);
  const [details, setDetails] = useState<PublicScheduleDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const endpoint = publicationId
        ? `/api/v1/scheduler/publications/${publicationId}`
        : "/api/v1/scheduler/publications";
      const response = await apiFetch(`${API_BASE_URL}${endpoint}`);
      if (!response.ok) throw new Error("Не удалось загрузить общий каталог");
      if (publicationId) {
        const payload = (await response.json()) as PublicScheduleDetails;
        setDetails(payload);
        setSelectedGroup(payload.groups[0] || "");
      } else {
        setDetails(null);
        setSelectedGroup("");
        setItems((await response.json()) as PublicScheduleSummary[]);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ошибка загрузки");
    } finally {
      setIsLoading(false);
    }
  }, [publicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleEntries = useMemo(
    () =>
      (details?.entries || []).filter(
        (entry) => !selectedGroup || entry.group_name.includes(selectedGroup),
      ),
    [details, selectedGroup],
  );

  if (isLoading) {
    return (
      <div className="loading-state">Загрузка опубликованных расписаний…</div>
    );
  }

  if (error) {
    return (
      <section className="empty-registry app-panel">
        <h3>{error}</h3>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => void load()}
        >
          <RefreshCcw size={16} /> Повторить
        </button>
      </section>
    );
  }

  if (details) {
    return (
      <div className="enterprise-page animate-fade-in">
        <section className="enterprise-page__header">
          <div>
            <button
              type="button"
              className="published-back"
              onClick={() => navigate("/published")}
            >
              <ArrowLeft size={16} /> К каталогу
            </button>
            <h2 className="enterprise-page__heading">{details.title}</h2>
            <p className="enterprise-page__description">
              Опубликовал: {details.owner_display_name} · обновлено{" "}
              {formatTimestamp(details.updated_at)} · редакция{" "}
              {details.edit_revision}
            </p>
          </div>
          {details.can_edit && details.source_task_id && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => navigate(`/schedule/${details.source_task_id}`)}
            >
              <Pencil size={16} /> Редактировать
            </button>
          )}
        </section>

        <section className="published-toolbar app-panel">
          <span>
            <CalendarDays size={16} /> {formatDate(details.starts_on)} —{" "}
            {formatDate(details.ends_on)}
          </span>
          <label>
            Группа
            <select
              value={selectedGroup}
              onChange={(event) => setSelectedGroup(event.target.value)}
            >
              <option value="">Все группы</option>
              {details.groups.map((group) => (
                <option value={group} key={group}>
                  {group}
                </option>
              ))}
            </select>
          </label>
        </section>

        <section className="published-table app-panel">
          <div className="published-table__head">
            <span>Дата</span>
            <span>Пара</span>
            <span>Группа</span>
            <span>Занятие</span>
            <span>Преподаватель</span>
            <span>Аудитория</span>
          </div>
          {visibleEntries.map((entry) => (
            <div className="published-table__row" key={entry.id}>
              <span>{formatDate(entry.date)}</span>
              <span>{entry.lesson_number ?? "—"}</span>
              <span>{entry.group_name}</span>
              <span>
                <strong>{entry.event_name}</strong>
                <small>{entry.stream_type}</small>
              </span>
              <span>{entry.teacher || "—"}</span>
              <span>{entry.room_id || "—"}</span>
            </div>
          ))}
          {visibleEntries.length === 0 && (
            <div className="published-table__empty">
              Для выбранной группы занятий нет.
            </div>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="enterprise-page animate-fade-in">
      <section className="enterprise-page__header">
        <div>
          <h2 className="enterprise-page__heading">
            Опубликованные расписания
          </h2>
          <p className="enterprise-page__description">
            Готовые расписания, доступные всем сотрудникам системы.
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => void load()}
        >
          <RefreshCcw size={16} /> Обновить
        </button>
      </section>
      {items.length ? (
        <section className="published-catalog">
          {items.map((item) => (
            <button
              type="button"
              className="published-card app-panel"
              key={item.id}
              onClick={() => navigate(`/published/${item.id}`)}
            >
              <span className="published-card__icon">
                <CalendarDays size={20} />
              </span>
              <span className="published-card__content">
                <strong>{item.title}</strong>
                <small>
                  {item.owner_display_name} · обновлено{" "}
                  {formatTimestamp(item.updated_at)}
                </small>
                <span>
                  <Users size={14} /> {item.groups.length} групп ·{" "}
                  {item.result_count} пар
                </span>
              </span>
              <Eye size={18} />
            </button>
          ))}
        </section>
      ) : (
        <section className="empty-registry app-panel">
          <CalendarDays size={32} />
          <h3>Опубликованных расписаний пока нет</h3>
          <p>Они появятся здесь после публикации готового расчёта.</p>
        </section>
      )}
    </div>
  );
};
