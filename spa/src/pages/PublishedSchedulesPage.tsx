import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Eye,
  MapPin,
  Pencil,
  RefreshCcw,
  UserRound,
  Users,
} from "lucide-react";

import { API_BASE_URL, apiFetch } from "../api/apiConfig";
import { groupLabelIncludesBase } from "../utils/groupSelection";

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

type ScheduleViewMode = "group" | "teacher";

const DAYS = [
  { short: "ПН", full: "Понедельник" },
  { short: "ВТ", full: "Вторник" },
  { short: "СР", full: "Среда" },
  { short: "ЧТ", full: "Четверг" },
  { short: "ПТ", full: "Пятница" },
  { short: "СБ", full: "Суббота" },
  { short: "ВС", full: "Воскресенье" },
] as const;

const PAIRS = [
  { number: 1, time: "08:45–10:05" },
  { number: 2, time: "10:20–11:40" },
  { number: 3, time: "11:55–13:15" },
  { number: 4, time: "13:30–14:50" },
  { number: 5, time: "15:05–16:25" },
  { number: 6, time: "16:40–18:00" },
  { number: 7, time: "18:15–19:35" },
] as const;

const parseLocalDate = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
};

const formatDateKey = (value: Date) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;

const getWeekKey = (value: string) => {
  const date = parseLocalDate(value);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return formatDateKey(date);
};

const getWeekDayDate = (weekKey: string, dayIndex: number) => {
  const date = parseLocalDate(weekKey);
  date.setDate(date.getDate() + dayIndex);
  return formatDateKey(date);
};

const formatShortDate = (value: string) =>
  parseLocalDate(value).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
  });

const formatWeekLabel = (weekKey: string) =>
  `${formatShortDate(weekKey)} — ${formatShortDate(getWeekDayDate(weekKey, 6))}`;

const formatMonthLabel = (weekKey: string) => {
  const start = parseLocalDate(weekKey);
  const end = parseLocalDate(getWeekDayDate(weekKey, 6));
  const monthFormatter = new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric",
  });
  if (
    start.getMonth() === end.getMonth() &&
    start.getFullYear() === end.getFullYear()
  ) {
    return monthFormatter.format(start);
  }
  return `${monthFormatter.format(start)} — ${monthFormatter.format(end)}`;
};

const getEntryTypeClass = (streamType: string) => {
  const normalizedType = streamType.toLocaleLowerCase("ru-RU");
  if (normalizedType.includes("лекц")) return "published-event--lecture";
  if (normalizedType.includes("лаборатор")) return "published-event--lab";
  if (normalizedType.includes("экзам") || normalizedType.includes("зач")) {
    return "published-event--exam";
  }
  return "published-event--practice";
};

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
  const [viewMode, setViewMode] = useState<ScheduleViewMode>("group");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedTeacher, setSelectedTeacher] = useState("");
  const [selectedWeek, setSelectedWeek] = useState("");

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
        setViewMode("group");
        setSelectedGroup(payload.groups[0] || "");
        setSelectedTeacher(
          Array.from(
            new Set(
              payload.entries
                .map((entry) => entry.teacher?.trim())
                .filter((teacher): teacher is string => Boolean(teacher)),
            ),
          ).sort((left, right) => left.localeCompare(right, "ru"))[0] || "",
        );
        const firstDatedEntry = payload.entries.find((entry) => entry.date);
        setSelectedWeek(
          firstDatedEntry?.date
            ? getWeekKey(firstDatedEntry.date)
            : payload.starts_on
              ? getWeekKey(payload.starts_on)
              : "",
        );
      } else {
        setDetails(null);
        setViewMode("group");
        setSelectedGroup("");
        setSelectedTeacher("");
        setSelectedWeek("");
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

  const availableWeeks = useMemo(() => {
    const weekKeys = new Set<string>();
    (details?.entries || []).forEach((entry) => {
      if (entry.date) weekKeys.add(getWeekKey(entry.date));
    });
    if (details?.starts_on) weekKeys.add(getWeekKey(details.starts_on));
    return Array.from(weekKeys).sort();
  }, [details]);

  const teachers = useMemo(
    () =>
      Array.from(
        new Set(
          (details?.entries || [])
            .map((entry) => entry.teacher?.trim())
            .filter((teacher): teacher is string => Boolean(teacher)),
        ),
      ).sort((left, right) => left.localeCompare(right, "ru")),
    [details],
  );

  const visibleEntries = useMemo(() => {
    const slotEntries = new Map<string, PublicScheduleEntry[]>();
    (details?.entries || []).forEach((entry) => {
      if (
        !entry.date ||
        !entry.lesson_number ||
        getWeekKey(entry.date) !== selectedWeek ||
        (viewMode === "group"
          ? selectedGroup &&
            !groupLabelIncludesBase(entry.group_name, selectedGroup)
          : entry.teacher?.trim() !== selectedTeacher)
      ) {
        return;
      }
      const slotKey = `${entry.date}:${entry.lesson_number}`;
      const entries = slotEntries.get(slotKey) || [];
      entries.push(entry);
      slotEntries.set(slotKey, entries);
    });
    return slotEntries;
  }, [details, selectedGroup, selectedTeacher, selectedWeek, viewMode]);

  const selectedWeekIndex = availableWeeks.indexOf(selectedWeek);

  const selectAdjacentWeek = (offset: number) => {
    const nextWeek = availableWeeks[selectedWeekIndex + offset];
    if (nextWeek) setSelectedWeek(nextWeek);
  };

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
      <div className="enterprise-page published-schedule-page animate-fade-in">
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

        <section className="published-grid-toolbar app-panel">
          <div className="published-grid-toolbar__period">
            <span className="published-grid-toolbar__month">
              {selectedWeek ? formatMonthLabel(selectedWeek) : "Расписание"}
            </span>
            <div className="published-week-switcher">
              <button
                type="button"
                aria-label="Предыдущая неделя"
                title="Предыдущая неделя"
                disabled={selectedWeekIndex <= 0}
                onClick={() => selectAdjacentWeek(-1)}
              >
                <ChevronLeft size={18} />
              </button>
              <label>
                <CalendarDays size={16} />
                <select
                  aria-label="Учебная неделя"
                  value={selectedWeek}
                  onChange={(event) => setSelectedWeek(event.target.value)}
                >
                  {availableWeeks.map((week) => (
                    <option value={week} key={week}>
                      {formatWeekLabel(week)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                aria-label="Следующая неделя"
                title="Следующая неделя"
                disabled={
                  selectedWeekIndex < 0 ||
                  selectedWeekIndex >= availableWeeks.length - 1
                }
                onClick={() => selectAdjacentWeek(1)}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
          <div className="published-grid-toolbar__filters">
            <div
              className="published-view-switcher"
              aria-label="Режим просмотра расписания"
            >
              <button
                type="button"
                className={viewMode === "group" ? "is-active" : ""}
                aria-pressed={viewMode === "group"}
                onClick={() => setViewMode("group")}
              >
                <Users size={15} /> По группам
              </button>
              <button
                type="button"
                className={viewMode === "teacher" ? "is-active" : ""}
                aria-pressed={viewMode === "teacher"}
                disabled={teachers.length === 0}
                title={
                  teachers.length === 0
                    ? "В расписании нет назначенных педагогов"
                    : undefined
                }
                onClick={() => setViewMode("teacher")}
              >
                <UserRound size={15} /> По педагогам
              </button>
            </div>
            {viewMode === "group" ? (
              <label className="published-grid-toolbar__filter">
                <Users size={16} />
                <span>Группа</span>
                <select
                  aria-label="Группа"
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
            ) : (
              <label className="published-grid-toolbar__filter">
                <UserRound size={16} />
                <span>Педагог</span>
                <select
                  aria-label="Педагог"
                  value={selectedTeacher}
                  onChange={(event) => setSelectedTeacher(event.target.value)}
                >
                  {teachers.map((teacher) => (
                    <option value={teacher} key={teacher}>
                      {teacher}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </section>

        {selectedWeek ? (
          <section className="published-schedule-grid app-panel">
            <div className="published-schedule-grid__scroll">
              <table>
                <thead>
                  <tr>
                    <th className="published-schedule-grid__pair-heading">
                      Пара
                    </th>
                    {DAYS.map((day, dayIndex) => (
                      <th key={day.short}>
                        <span>{day.short}</span>
                        <strong>
                          {formatShortDate(
                            getWeekDayDate(selectedWeek, dayIndex),
                          )}
                        </strong>
                        <small>{day.full}</small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PAIRS.map((pair) => (
                    <tr key={pair.number}>
                      <td className="published-schedule-grid__pair">
                        <strong>{pair.number}</strong>
                        <span>{pair.time}</span>
                      </td>
                      {DAYS.map((day, dayIndex) => {
                        const date = getWeekDayDate(selectedWeek, dayIndex);
                        const entries =
                          visibleEntries.get(`${date}:${pair.number}`) || [];
                        return (
                          <td key={day.short}>
                            <div className="published-schedule-grid__cell">
                              {entries.map((entry) => (
                                <article
                                  className={`published-event ${getEntryTypeClass(entry.stream_type)}`}
                                  key={entry.id}
                                  title={`${entry.event_name}\n${entry.teacher || "Преподаватель не указан"}\n${entry.room_id || "Аудитория не указана"}`}
                                >
                                  <div className="published-event__header">
                                    <strong>{entry.event_name}</strong>
                                    <span>{entry.stream_type}</span>
                                  </div>
                                  <div className="published-event__meta">
                                    <span>
                                      <MapPin size={13} />
                                      {entry.room_id || "Аудитория не указана"}
                                    </span>
                                    {viewMode === "group" && (
                                      <span>
                                        <UserRound size={13} />
                                        {entry.teacher ||
                                          "Преподаватель не указан"}
                                      </span>
                                    )}
                                    {(viewMode === "teacher" ||
                                      !selectedGroup) && (
                                      <span>
                                        <Users size={13} /> {entry.group_name}
                                      </span>
                                    )}
                                  </div>
                                </article>
                              ))}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <section className="empty-registry app-panel">
            <CalendarDays size={32} />
            <h3>В расписании пока нет выставленных занятий</h3>
            <p>После добавления дат и пар они появятся в недельной сетке.</p>
          </section>
        )}
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
