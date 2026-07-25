import React, { useState, useEffect } from "react";
import {
  Users,
  MapPin,
  Search,
  Lock,
  ChevronRight,
  ChevronLeft,
  CalendarDays,
  Repeat,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Trash2,
  Plus,
} from "lucide-react";
import {
  useAppStore,
  getSlotsForInterval,
  PAIR_TIMES,
} from "../store/useAppStore";
import type { TimeInterval } from "../store/useAppStore";

const TIMES = PAIR_TIMES.map((pair) => pair.label);

const WEEK_DAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
const MONTHS = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];
const MONTHS_SHORT = [
  "Янв",
  "Фев",
  "Мар",
  "Апр",
  "Май",
  "Июн",
  "Июл",
  "Авг",
  "Сен",
  "Окт",
  "Ноя",
  "Дек",
];

// Helpers
const getStartOfWeek = (date: Date) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust for Sunday (0)
  return new Date(d.setDate(diff));
};

const getDaysOfWeek = (startDate: Date) => {
  const days = [];
  for (let i = 0; i < 7; i++) {
    // Mon - Sun
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);
    days.push(d);
  }
  return days;
};

const formatDateFull = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const WEEK_DAYS_FULL = [
  "Воскресенье",
  "Понедельник",
  "Вторник",
  "Среда",
  "Четверг",
  "Пятница",
  "Суббота",
];

export const CalendarPage: React.FC = () => {
  const {
    teachers,
    selectedTeacherId,
    setSelectedTeacherId,
    toggleRestriction,
    setRestrictionMode,
    saveTeacherRestrictions,
    addInterval,
    removeInterval,
    fetchInitialData,
    isLoading,
    error,
  } = useAppStore();

  const selectedTeacher = teachers.find((t) => t.id === selectedTeacherId);

  // Date State
  const [currentDate, setCurrentDate] = useState(() => {
    const today = new Date();
    // Reset to midnight
    today.setHours(0, 0, 0, 0);
    return today;
  });

  const [dragState, setDragState] = useState<{
    isDragging: boolean;
    mode: "block" | "unblock" | null;
  }>({
    isDragging: false,
    mode: null,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [editMode, setEditMode] = useState<"specific" | "recurring" | "time">(
    "specific",
  );

  // Time interval form state
  const [intervalStart, setIntervalStart] = useState("09:00");
  const [intervalEnd, setIntervalEnd] = useState("15:00");
  const [intervalType, setIntervalType] = useState<"recurring" | "specific">(
    "recurring",
  );
  const [intervalDay, setIntervalDay] = useState(1); // JS weekday
  const [intervalDate, setIntervalDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  });

  const filteredTeachers = teachers.filter(
    (t) =>
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.dept.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (dragState.isDragging && selectedTeacherId) {
        saveTeacherRestrictions(selectedTeacherId);
      }
      setDragState({ isDragging: false, mode: null });
    };
    window.addEventListener("mouseup", handleGlobalMouseUp);
    return () => window.removeEventListener("mouseup", handleGlobalMouseUp);
  }, [dragState.isDragging, selectedTeacherId, saveTeacherRestrictions]);

  if (isLoading) {
    return (
      <div className="p-20 text-center text-text-secondary">
        Загрузка данных преподавателей...
      </div>
    );
  }

  const handleMouseDown = (dateStr: string, slotIdx: number) => {
    if (!selectedTeacherId || !selectedTeacher) return;

    const weekday = new Date(dateStr).getDay();
    const recurringKey = `${weekday}-${slotIdx + 1}`;
    const specificKey = `${dateStr}-${slotIdx + 1}`;

    const isCurrentlyActive =
      editMode === "recurring"
        ? selectedTeacher.restrictions.recurring.includes(recurringKey)
        : selectedTeacher.restrictions.specific.includes(specificKey);

    const newMode = isCurrentlyActive ? "unblock" : "block";
    setDragState({ isDragging: true, mode: newMode });

    toggleRestriction(
      selectedTeacherId,
      editMode,
      editMode === "recurring" ? recurringKey : specificKey,
    );
  };

  const handleMouseEnter = (dateStr: string, slotIdx: number) => {
    if (
      !dragState.isDragging ||
      !dragState.mode ||
      !selectedTeacherId ||
      !selectedTeacher
    )
      return;

    const weekday = new Date(dateStr).getDay();
    const recurringKey = `${weekday}-${slotIdx + 1}`;
    const specificKey = `${dateStr}-${slotIdx + 1}`;

    const isCurrentlyActive =
      editMode === "recurring"
        ? selectedTeacher.restrictions.recurring.includes(recurringKey)
        : selectedTeacher.restrictions.specific.includes(specificKey);

    if (
      (dragState.mode === "block" && !isCurrentlyActive) ||
      (dragState.mode === "unblock" && isCurrentlyActive)
    ) {
      toggleRestriction(
        selectedTeacherId,
        editMode,
        editMode === "recurring" ? recurringKey : specificKey,
      );
    }
  };

  // Date Navigation
  const startOfWeek = getStartOfWeek(currentDate);
  const weekDays = getDaysOfWeek(startOfWeek);
  const currentMonthName = MONTHS[startOfWeek.getMonth()];
  const currentYear = startOfWeek.getFullYear();

  const handlePrevWeek = () => {
    const prev = new Date(currentDate);
    prev.setDate(prev.getDate() - 7);
    setCurrentDate(prev);
  };

  const handleNextWeek = () => {
    const next = new Date(currentDate);
    next.setDate(next.getDate() + 7);
    setCurrentDate(next);
  };

  const handleToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    setCurrentDate(today);
  };

  return (
    <div
      className="space-y-6"
      style={{
        height: "calc(100vh - 120px)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Доступность преподавателей
          </h1>
          <p className="text-text-secondary mt-1 text-sm">
            Отметьте окна (красным), когда преподаватель не может проводить
            занятия.
          </p>
        </div>
      </header>
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}

      <div
        style={{ display: "flex", gap: "1.5rem", flex: 1, overflow: "hidden" }}
      >
        {/* Left Sidebar: List */}
        <div
          style={{
            width: "280px",
            backgroundColor: "white",
            borderRadius: "12px",
            border: "1px solid var(--border-light)",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "1rem",
              borderBottom: "1px solid var(--border-light)",
            }}
          >
            <div style={{ position: "relative" }}>
              <Search
                size={16}
                style={{
                  position: "absolute",
                  left: "0.75rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-tertiary)",
                }}
              />
              <input
                type="text"
                placeholder="Поиск..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem 0.75rem 0.5rem 2.25rem",
                  borderRadius: "8px",
                  border: "1px solid var(--border-light)",
                  backgroundColor: "var(--bg-base)",
                  fontSize: "0.875rem",
                }}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {filteredTeachers.map((teacher) => (
              <button
                key={teacher.id}
                onClick={() => setSelectedTeacherId(teacher.id)}
                style={{
                  width: "100%",
                  padding: "0.75rem 1rem",
                  textAlign: "left",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  borderBottom: "1px solid var(--border-light)",
                  backgroundColor:
                    selectedTeacherId === teacher.id
                      ? "#eef2ff"
                      : "transparent",
                  color:
                    selectedTeacherId === teacher.id
                      ? "var(--brand)"
                      : "var(--text-primary)",
                  transition: "background-color 0.15s",
                  cursor: "pointer",
                }}
                className="hover:bg-gray-50"
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.875rem" }}>
                    {teacher.name}
                  </div>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-tertiary)",
                      marginTop: "0.125rem",
                    }}
                  >
                    {teacher.dept}
                  </div>
                </div>
                {selectedTeacherId === teacher.id && (
                  <ChevronRight size={16} color="var(--brand)" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right Content: Grid */}
        <div
          style={{
            flex: 1,
            backgroundColor: "white",
            borderRadius: "12px",
            border: "1px solid var(--border-light)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {selectedTeacher ? (
            <>
              {/* Toolbar & Date Navigation */}
              <div
                style={{
                  padding: "0.75rem 1.25rem",
                  borderBottom: "1px solid var(--border-light)",
                  backgroundColor: "#fafafa",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: "1rem",
                      alignItems: "center",
                    }}
                  >
                    <div
                      style={{
                        width: "40px",
                        height: "40px",
                        borderRadius: "8px",
                        backgroundColor: "var(--brand)",
                        color: "white",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "1.25rem",
                        fontWeight: 700,
                      }}
                    >
                      {selectedTeacher.name[0]}
                    </div>
                    <div>
                      <h2 style={{ fontSize: "1.125rem", fontWeight: 700 }}>
                        {selectedTeacher.name}
                      </h2>
                      <div
                        className="flex gap-4 mt-0.5 text-text-secondary"
                        style={{ fontSize: "0.75rem" }}
                      >
                        <span className="flex items-center gap-1">
                          <MapPin size={12} /> {selectedTeacher.dept}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "1rem",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.25rem",
                      }}
                    >
                      <button
                        onClick={handlePrevWeek}
                        aria-label="Предыдущая неделя"
                        title="Предыдущая неделя"
                        style={{
                          padding: "0.5rem",
                          borderRadius: "8px",
                          backgroundColor: "white",
                          border: "1px solid var(--border-light)",
                        }}
                        className="hover:bg-gray-50"
                      >
                        <ChevronLeft size={16} />
                      </button>
                      <button
                        onClick={handleToday}
                        style={{
                          padding: "0.5rem 1rem",
                          borderRadius: "8px",
                          backgroundColor: "white",
                          border: "1px solid var(--border-light)",
                          fontSize: "0.875rem",
                          fontWeight: 600,
                        }}
                        className="hover:bg-gray-50"
                      >
                        Сегодня
                      </button>
                      <button
                        onClick={handleNextWeek}
                        aria-label="Следующая неделя"
                        title="Следующая неделя"
                        style={{
                          padding: "0.5rem",
                          borderRadius: "8px",
                          backgroundColor: "white",
                          border: "1px solid var(--border-light)",
                        }}
                        className="hover:bg-gray-50"
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: "1rem",
                        minWidth: "120px",
                        textAlign: "right",
                      }}
                    >
                      {currentMonthName} {currentYear}
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "2rem",
                    alignItems: "center",
                    padding: "0.5rem",
                    backgroundColor: "white",
                    borderRadius: "8px",
                    border: "1px solid var(--border-light)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: "var(--text-secondary)",
                      }}
                    >
                      Режим:
                    </span>
                    <div
                      style={{
                        display: "flex",
                        backgroundColor: "var(--bg-base)",
                        padding: "2px",
                        borderRadius: "6px",
                      }}
                    >
                      <button
                        onClick={() => setEditMode("specific")}
                        style={{
                          padding: "0.25rem 0.75rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            editMode === "specific" ? "white" : "transparent",
                          boxShadow:
                            editMode === "specific"
                              ? "0 1px 3px rgba(0,0,0,0.1)"
                              : "none",
                          color:
                            editMode === "specific"
                              ? "var(--brand)"
                              : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <CalendarDays size={14} /> Конкретный день
                      </button>
                      <button
                        onClick={() => setEditMode("recurring")}
                        style={{
                          padding: "0.25rem 0.75rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            editMode === "recurring" ? "white" : "transparent",
                          boxShadow:
                            editMode === "recurring"
                              ? "0 1px 3px rgba(0,0,0,0.1)"
                              : "none",
                          color:
                            editMode === "recurring"
                              ? "var(--brand)"
                              : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <Repeat size={14} /> Повтор (еженедельно)
                      </button>
                      <button
                        onClick={() => setEditMode("time")}
                        style={{
                          padding: "0.25rem 0.75rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            editMode === "time" ? "white" : "transparent",
                          boxShadow:
                            editMode === "time"
                              ? "0 1px 3px rgba(0,0,0,0.1)"
                              : "none",
                          color:
                            editMode === "time"
                              ? "var(--brand)"
                              : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <Clock size={14} /> По времени
                      </button>
                    </div>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: "var(--text-secondary)",
                      }}
                    >
                      Логика:
                    </span>
                    <div
                      style={{
                        display: "flex",
                        backgroundColor: "var(--bg-base)",
                        padding: "2px",
                        borderRadius: "6px",
                      }}
                    >
                      <button
                        onClick={() =>
                          selectedTeacherId &&
                          setRestrictionMode(selectedTeacherId, "blacklist")
                        }
                        style={{
                          padding: "0.25rem 0.75rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            selectedTeacher.restrictions.mode === "blacklist"
                              ? "white"
                              : "transparent",
                          boxShadow:
                            selectedTeacher.restrictions.mode === "blacklist"
                              ? "0 1px 3px rgba(0,0,0,0.1)"
                              : "none",
                          color:
                            selectedTeacher.restrictions.mode === "blacklist"
                              ? "#ef4444"
                              : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <ShieldAlert size={14} /> Черный список
                      </button>
                      <button
                        onClick={() =>
                          selectedTeacherId &&
                          setRestrictionMode(selectedTeacherId, "whitelist")
                        }
                        style={{
                          padding: "0.25rem 0.75rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            selectedTeacher.restrictions.mode === "whitelist"
                              ? "white"
                              : "transparent",
                          boxShadow:
                            selectedTeacher.restrictions.mode === "whitelist"
                              ? "0 1px 3px rgba(0,0,0,0.1)"
                              : "none",
                          color:
                            selectedTeacher.restrictions.mode === "whitelist"
                              ? "#10b981"
                              : "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          cursor: "pointer",
                        }}
                      >
                        <ShieldCheck size={14} /> Белый список
                      </button>
                    </div>
                  </div>

                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-tertiary)",
                      fontStyle: "italic",
                    }}
                  >
                    {selectedTeacher.restrictions.mode === "blacklist"
                      ? "Все разрешено, отмеченное — ЗАПРЕЩЕНО"
                      : "Все запрещено, отмеченное — РАЗРЕШЕНО"}
                  </div>
                </div>
              </div>

              {/* Grid Content */}
              <div
                style={{
                  flex: 1,
                  padding: "1.5rem",
                  overflowY: "auto",
                  backgroundColor: "white",
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: `80px repeat(${WEEK_DAYS.length}, minmax(92px, 1fr))`,
                    minWidth: "820px",
                    border: "1px solid var(--border-light)",
                    borderRadius: "8px",
                    overflow: "hidden",
                  }}
                >
                  {/* Empty top-left cell */}
                  <div
                    style={{
                      backgroundColor: "var(--bg-base)",
                      borderRight: "1px solid var(--border-light)",
                      borderBottom: "1px solid var(--border-light)",
                    }}
                  ></div>

                  {/* Days Header */}
                  {weekDays.map((dateObj, idx) => {
                    const isToday =
                      formatDateFull(dateObj) === formatDateFull(new Date());
                    return (
                      <div
                        key={idx}
                        style={{
                          backgroundColor: isToday
                            ? "#eef2ff"
                            : "var(--bg-base)",
                          padding: "0.75rem",
                          textAlign: "center",
                          borderBottom: "1px solid var(--border-light)",
                          borderRight:
                            idx !== weekDays.length - 1
                              ? "1px solid var(--border-light)"
                              : "none",
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: "0.75rem",
                            color: isToday
                              ? "var(--brand)"
                              : "var(--text-secondary)",
                          }}
                        >
                          {WEEK_DAYS[idx]}
                        </div>
                        <div
                          style={{
                            fontWeight: 800,
                            fontSize: "1.125rem",
                            color: isToday
                              ? "var(--brand)"
                              : "var(--text-primary)",
                            marginTop: "0.125rem",
                          }}
                        >
                          {dateObj.getDate()} {MONTHS_SHORT[dateObj.getMonth()]}
                        </div>
                      </div>
                    );
                  })}

                  {/* Body rows */}
                  {TIMES.map((time, slotIdx) => (
                    <React.Fragment key={time}>
                      {/* Time Label (Y-axis) */}
                      <div
                        style={{
                          backgroundColor: "#fafafa",
                          padding: "0.75rem 0.5rem",
                          textAlign: "center",
                          borderRight: "1px solid var(--border-light)",
                          borderBottom:
                            slotIdx !== TIMES.length - 1
                              ? "1px solid var(--border-light)"
                              : "none",
                          display: "flex",
                          flexDirection: "column",
                          justifyContent: "center",
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 700,
                            fontSize: "0.75rem",
                            color: "var(--text-primary)",
                          }}
                        >
                          {slotIdx + 1} пара
                        </div>
                        <div
                          style={{
                            fontSize: "0.625rem",
                            color: "var(--text-tertiary)",
                            marginTop: "0.125rem",
                          }}
                        >
                          {time}
                        </div>
                      </div>

                      {/* Days Grid Cells */}
                      {weekDays.map((dateObj, idx) => {
                        const dateStr = formatDateFull(dateObj);
                        const weekday = dateObj.getDay();
                        const slotNum = slotIdx + 1;

                        const recurringKey = `${weekday}-${slotNum}`;
                        const specificKey = `${dateStr}-${slotNum}`;

                        const hasRecurring =
                          selectedTeacher.restrictions.recurring.includes(
                            recurringKey,
                          );
                        const hasSpecific =
                          selectedTeacher.restrictions.specific.includes(
                            specificKey,
                          );

                        const isWhiteList =
                          selectedTeacher.restrictions.mode === "whitelist";

                        // Logical blockage
                        let isBlocked = false;
                        if (isWhiteList) {
                          isBlocked = !hasRecurring && !hasSpecific;
                        } else {
                          isBlocked = hasRecurring || hasSpecific;
                        }

                        // Colors
                        let bgColor = "white";
                        let textColor = "transparent";
                        if (isWhiteList) {
                          bgColor = isBlocked ? "#f9fafb" : "#f0fdf4"; // Light gray if blocked, green if allowed
                          textColor = isBlocked ? "#9ca3af" : "#16a34a";
                        } else {
                          bgColor = isBlocked ? "#fef2f2" : "white"; // Red if blocked, white if allowed
                          textColor = isBlocked ? "#dc2626" : "transparent";
                        }

                        return (
                          <button
                            key={idx}
                            aria-label={`${dateStr}, ${slotNum} пара: ${
                              isBlocked ? "недоступно" : "доступно"
                            }`}
                            aria-pressed={hasRecurring || hasSpecific}
                            onMouseDown={() =>
                              handleMouseDown(dateStr, slotIdx)
                            }
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                handleMouseDown(dateStr, slotIdx);
                              }
                            }}
                            onMouseEnter={() =>
                              handleMouseEnter(dateStr, slotIdx)
                            }
                            onDragStart={(e) => e.preventDefault()}
                            style={{
                              backgroundColor: bgColor,
                              backgroundImage: hasRecurring
                                ? `repeating-linear-gradient(45deg, transparent, transparent 10px, ${isWhiteList ? "rgba(22, 163, 74, 0.1)" : "rgba(220, 38, 38, 0.1)"} 10px, ${isWhiteList ? "rgba(22, 163, 74, 0.1)" : "rgba(220, 38, 38, 0.1)"} 20px)`
                                : "none",
                              color: textColor,
                              borderBottom:
                                slotIdx !== TIMES.length - 1
                                  ? "1px solid var(--border-light)"
                                  : "none",
                              borderRight:
                                idx !== weekDays.length - 1
                                  ? "1px solid var(--border-light)"
                                  : "none",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              transition: "all 0.1s",
                              height: "64px",
                              padding: 0,
                              position: "relative",
                              border:
                                hasRecurring || hasSpecific
                                  ? `2px solid ${isWhiteList ? "#10b981" : "#ef4444"}`
                                  : undefined,
                              zIndex: hasRecurring || hasSpecific ? 10 : 1,
                            }}
                            className={
                              isBlocked ? "grid-cell-blocked" : "grid-cell"
                            }
                          >
                            {isBlocked && (
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  zIndex: 2,
                                }}
                              >
                                <Lock size={14} />
                                <span
                                  style={{
                                    fontSize: "0.625rem",
                                    fontWeight: 800,
                                  }}
                                >
                                  БЛОК
                                </span>
                              </div>
                            )}
                            {!isBlocked && isWhiteList && (
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  zIndex: 2,
                                }}
                              >
                                <ShieldCheck size={14} />
                                <span
                                  style={{
                                    fontSize: "0.625rem",
                                    fontWeight: 800,
                                  }}
                                >
                                  OK
                                </span>
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </div>

                {/* Time Interval Panel */}
                {editMode === "time" && selectedTeacher && (
                  <div
                    style={{
                      marginTop: "1.5rem",
                      padding: "1.25rem",
                      backgroundColor: "#fafafa",
                      borderRadius: "10px",
                      border: "1px solid var(--border-light)",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "0.9rem",
                        fontWeight: 700,
                        marginBottom: "1rem",
                      }}
                    >
                      <Clock
                        size={16}
                        style={{
                          display: "inline",
                          verticalAlign: "middle",
                          marginRight: "0.5rem",
                        }}
                      />
                      Добавить временной интервал
                    </h3>

                    <div
                      style={{
                        display: "flex",
                        gap: "0.75rem",
                        alignItems: "flex-end",
                        flexWrap: "wrap",
                      }}
                    >
                      {/* Type toggle */}
                      <div>
                        <label
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            display: "block",
                            marginBottom: "4px",
                          }}
                        >
                          Тип
                        </label>
                        <select
                          value={intervalType}
                          onChange={(e) =>
                            setIntervalType(
                              e.target.value as "recurring" | "specific",
                            )
                          }
                          style={{
                            padding: "0.45rem 0.6rem",
                            borderRadius: "6px",
                            border: "1px solid var(--border-light)",
                            fontSize: "0.8rem",
                            backgroundColor: "white",
                          }}
                        >
                          <option value="recurring">Еженедельно</option>
                          <option value="specific">Конкретная дата</option>
                        </select>
                      </div>

                      {/* Day or Date selector */}
                      {intervalType === "recurring" ? (
                        <div>
                          <label
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              color: "var(--text-secondary)",
                              display: "block",
                              marginBottom: "4px",
                            }}
                          >
                            День недели
                          </label>
                          <select
                            value={intervalDay}
                            onChange={(e) =>
                              setIntervalDay(Number(e.target.value))
                            }
                            style={{
                              padding: "0.45rem 0.6rem",
                              borderRadius: "6px",
                              border: "1px solid var(--border-light)",
                              fontSize: "0.8rem",
                              backgroundColor: "white",
                            }}
                          >
                            {[1, 2, 3, 4, 5, 6].map((wd) => (
                              <option key={wd} value={wd}>
                                {WEEK_DAYS_FULL[wd]}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : (
                        <div>
                          <label
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              color: "var(--text-secondary)",
                              display: "block",
                              marginBottom: "4px",
                            }}
                          >
                            Дата
                          </label>
                          <input
                            type="date"
                            value={intervalDate}
                            onChange={(e) => setIntervalDate(e.target.value)}
                            style={{
                              padding: "0.45rem 0.6rem",
                              borderRadius: "6px",
                              border: "1px solid var(--border-light)",
                              fontSize: "0.8rem",
                              backgroundColor: "white",
                            }}
                          />
                        </div>
                      )}

                      {/* Start time */}
                      <div>
                        <label
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            display: "block",
                            marginBottom: "4px",
                          }}
                        >
                          С
                        </label>
                        <input
                          type="time"
                          value={intervalStart}
                          onChange={(e) => setIntervalStart(e.target.value)}
                          style={{
                            padding: "0.45rem 0.6rem",
                            borderRadius: "6px",
                            border: "1px solid var(--border-light)",
                            fontSize: "0.8rem",
                            backgroundColor: "white",
                          }}
                        />
                      </div>

                      {/* End time */}
                      <div>
                        <label
                          style={{
                            fontSize: "0.7rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            display: "block",
                            marginBottom: "4px",
                          }}
                        >
                          До
                        </label>
                        <input
                          type="time"
                          value={intervalEnd}
                          onChange={(e) => setIntervalEnd(e.target.value)}
                          style={{
                            padding: "0.45rem 0.6rem",
                            borderRadius: "6px",
                            border: "1px solid var(--border-light)",
                            fontSize: "0.8rem",
                            backgroundColor: "white",
                          }}
                        />
                      </div>

                      {/* Preview */}
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-tertiary)",
                          paddingBottom: "0.45rem",
                        }}
                      >
                        Пары:{" "}
                        {getSlotsForInterval(intervalStart, intervalEnd).join(
                          ", ",
                        ) || "—"}
                      </div>

                      {/* Add button */}
                      <button
                        onClick={() => {
                          if (!selectedTeacherId) return;
                          const data: Omit<TimeInterval, "id"> = {
                            start: intervalStart,
                            end: intervalEnd,
                            type: intervalType,
                            ...(intervalType === "recurring"
                              ? { day: intervalDay }
                              : { date: intervalDate }),
                          };
                          addInterval(selectedTeacherId, data);
                          saveTeacherRestrictions(selectedTeacherId);
                        }}
                        disabled={
                          getSlotsForInterval(intervalStart, intervalEnd)
                            .length === 0
                        }
                        style={{
                          padding: "0.45rem 1rem",
                          borderRadius: "6px",
                          backgroundColor:
                            getSlotsForInterval(intervalStart, intervalEnd)
                              .length > 0
                              ? "var(--brand)"
                              : "#e5e7eb",
                          color:
                            getSlotsForInterval(intervalStart, intervalEnd)
                              .length > 0
                              ? "white"
                              : "#9ca3af",
                          fontSize: "0.8rem",
                          fontWeight: 600,
                          cursor:
                            getSlotsForInterval(intervalStart, intervalEnd)
                              .length > 0
                              ? "pointer"
                              : "not-allowed",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.375rem",
                          border: "none",
                        }}
                      >
                        <Plus size={14} /> Добавить
                      </button>
                    </div>

                    {/* Saved intervals list */}
                    {selectedTeacher.restrictions.intervals.length > 0 && (
                      <div style={{ marginTop: "1rem" }}>
                        <div
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Сохранённые интервалы
                        </div>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "0.375rem",
                          }}
                        >
                          {selectedTeacher.restrictions.intervals.map((iv) => (
                            <div
                              key={iv.id}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: "0.5rem 0.75rem",
                                backgroundColor: "white",
                                borderRadius: "6px",
                                border: "1px solid var(--border-light)",
                                fontSize: "0.8rem",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "0.75rem",
                                }}
                              >
                                <Clock size={14} color="var(--brand)" />
                                <span style={{ fontWeight: 600 }}>
                                  {iv.start} – {iv.end}
                                </span>
                                <span
                                  style={{
                                    color: "var(--text-tertiary)",
                                    fontSize: "0.75rem",
                                  }}
                                >
                                  {iv.type === "recurring"
                                    ? WEEK_DAYS_FULL[iv.day ?? 0]
                                    : iv.date}
                                </span>
                                <span
                                  style={{
                                    color: "var(--text-tertiary)",
                                    fontSize: "0.7rem",
                                  }}
                                >
                                  → пары{" "}
                                  {getSlotsForInterval(iv.start, iv.end).join(
                                    ", ",
                                  )}
                                </span>
                              </div>
                              <button
                                onClick={() => {
                                  if (!selectedTeacherId) return;
                                  removeInterval(selectedTeacherId, iv.id);
                                  saveTeacherRestrictions(selectedTeacherId);
                                }}
                                style={{
                                  padding: "0.25rem",
                                  borderRadius: "4px",
                                  backgroundColor: "transparent",
                                  color: "#ef4444",
                                  cursor: "pointer",
                                  border: "none",
                                  display: "flex",
                                  alignItems: "center",
                                }}
                                className="hover:bg-red-50"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-tertiary)",
                flexDirection: "column",
                gap: "1rem",
                backgroundColor: "#fafafa",
              }}
            >
              <Users size={48} opacity={0.2} />
              <div style={{ fontWeight: 600 }}>
                Выберите преподавателя слева
              </div>
            </div>
          )}
        </div>
      </div>

      <style
        dangerouslySetInnerHTML={{
          __html: `
        .grid-cell:hover {
          background-color: #f3f4f6 !important;
        }
        .grid-cell-blocked {
          border: 1px solid #fca5a5 !important;
          z-index: 1;
        }
        .grid-cell-blocked:hover {
          background-color: #fee2e2 !important;
        }
        body {
          user-select: none;
        }
      `,
        }}
      />
    </div>
  );
};
