import { useCallback, useEffect, useState } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Repeat,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useAppStore, type TeacherRestrictions } from "../store/useAppStore";
import { AvailabilityGrid, type EditMode } from "./calendar/AvailabilityGrid";
import { IntervalEditor } from "./calendar/IntervalEditor";
import { addDays, getStudyWeek } from "./calendar/dates";
import "./CalendarPage.css";

const monthFormatter = new Intl.DateTimeFormat("ru-RU", {
  month: "long",
  year: "numeric",
});
const editModes = [
  { value: "specific", label: "Конкретный день", icon: CalendarDays },
  { value: "recurring", label: "Повтор (еженедельно)", icon: Repeat },
  { value: "time", label: "По времени", icon: Clock },
] as const;
const restrictionModes = [
  { value: "blacklist", label: "Черный список", icon: ShieldAlert },
  { value: "whitelist", label: "Белый список", icon: ShieldCheck },
] as const;

export function CalendarPage() {
  const {
    teachers,
    selectedTeacherId,
    setSelectedTeacherId,
    toggleRestriction,
    toggleDayRestriction,
    setRestrictionMode,
    saveTeacherRestrictions,
    addInterval,
    removeInterval,
    fetchInitialData,
    isLoading,
    error,
  } = useAppStore();
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<EditMode>("specific");
  const teacher = teachers.find((item) => item.id === selectedTeacherId);
  const week = getStudyWeek(currentDate);

  useEffect(() => {
    void fetchInitialData();
  }, [fetchInitialData]);

  const save = useCallback(() => {
    if (selectedTeacherId !== null)
      void saveTeacherRestrictions(selectedTeacherId);
  }, [saveTeacherRestrictions, selectedTeacherId]);

  const changeMode = (value: TeacherRestrictions["mode"]) => {
    if (!teacher || teacher.restrictions.mode === value) return;
    setRestrictionMode(teacher.id, value);
    save();
  };

  return (
    <div className="calendar-page space-y-5">
      <header className="workspace-header">
        <div>
          <h1>Доступность преподавателей</h1>
          <p>
            Отмечайте пары или весь день. Изменения сохраняются автоматически.
          </p>
        </div>
      </header>
      {error && (
        <p className="notice notice--danger" role="alert">
          {error}
        </p>
      )}
      {isLoading ? (
        <p className="loading-state" role="status">
          Загрузка данных преподавателей…
        </p>
      ) : (
        <div className="calendar-layout">
          <aside
            className="app-panel calendar-teachers"
            aria-label="Преподаватели"
          >
            <label className="app-search">
              <Search size={16} aria-hidden="true" />
              <input
                className="app-field"
                aria-label="Поиск преподавателя"
                placeholder="Поиск преподавателя"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="calendar-teacher-list">
              {teachers
                .filter((item) =>
                  `${item.name} ${item.dept}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    aria-pressed={teacher?.id === item.id}
                    onClick={() => setSelectedTeacherId(item.id)}
                  >
                    <strong>{item.name}</strong>
                    {item.dept && <small>{item.dept}</small>}
                  </button>
                ))}
            </div>
          </aside>
          <section
            className="app-panel calendar-card"
            aria-label="Календарь преподавателя"
          >
            {teacher ? (
              <>
                <div className="calendar-toolbar">
                  <div className="calendar-teacher-toolbar">
                    <div>
                      <h2>{teacher.name}</h2>
                      <p>{teacher.dept}</p>
                    </div>
                    <div
                      className="calendar-toolbar__controls"
                      aria-label="Навигация по неделям"
                    >
                      <button
                        type="button"
                        className="button-icon"
                        aria-label="Предыдущая неделя"
                        onClick={() => setCurrentDate(addDays(currentDate, -7))}
                      >
                        <ChevronLeft size={18} />
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setCurrentDate(new Date())}
                      >
                        Сегодня
                      </button>
                      <button
                        type="button"
                        className="button-icon"
                        aria-label="Следующая неделя"
                        onClick={() => setCurrentDate(addDays(currentDate, 7))}
                      >
                        <ChevronRight size={18} />
                      </button>
                      <strong className="calendar-month" aria-live="polite">
                        {monthFormatter.format(week[0])}
                      </strong>
                    </div>
                  </div>
                  <div
                    className="calendar-toolbar__controls"
                    role="group"
                    aria-label="Способ выбора"
                  >
                    {editModes.map(({ value, label, icon: Icon }) => (
                      <button
                        className="app-toggle"
                        type="button"
                        key={value}
                        aria-pressed={mode === value}
                        onClick={() => setMode(value)}
                      >
                        <Icon size={14} aria-hidden="true" />
                        {label}
                      </button>
                    ))}
                  </div>
                  <div
                    className="calendar-toolbar__controls"
                    role="group"
                    aria-label="Режим доступности"
                  >
                    {restrictionModes.map(({ value, label, icon: Icon }) => (
                      <button
                        className="app-toggle"
                        type="button"
                        key={value}
                        aria-pressed={teacher.restrictions.mode === value}
                        onClick={() => changeMode(value)}
                      >
                        <Icon size={14} aria-hidden="true" />
                        {label}
                      </button>
                    ))}
                    <small>
                      {teacher.restrictions.mode === "blacklist"
                        ? "Отмеченные пары недоступны"
                        : "Доступны только отмеченные пары"}
                    </small>
                  </div>
                </div>
                <AvailabilityGrid
                  teacher={teacher}
                  week={week}
                  mode={mode}
                  onToggle={(type, key) =>
                    toggleRestriction(teacher.id, type, key)
                  }
                  onToggleDay={(type, date) => {
                    toggleDayRestriction(teacher.id, type, date);
                    save();
                  }}
                  onSave={save}
                />
                {mode === "time" && (
                  <IntervalEditor
                    intervals={teacher.restrictions.intervals}
                    onAdd={(interval) => {
                      addInterval(teacher.id, interval);
                      save();
                    }}
                    onRemove={(id) => {
                      removeInterval(teacher.id, id);
                      save();
                    }}
                  />
                )}
              </>
            ) : (
              <div className="calendar-empty">
                <Users size={36} aria-hidden="true" />
                Выберите преподавателя
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
