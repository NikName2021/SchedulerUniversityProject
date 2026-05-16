import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  Calendar,
  Download,
  AlertCircle,
  MapPin,
  User,
  Trash2,
  GripVertical,
  ChevronLeft,
  ChevronRight,
  X,
  Layers,
  Users,
  UserCheck,
} from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { API_BASE_URL } from "../api/apiConfig";

interface ScheduleEntry {
  id: number;
  group_name: string;
  event_name: string;
  stream_type: string;
  teacher: string | null;
  teacher_id: number | null;
  room_id: string | null;
  date: string;
  lesson_number: number;
  warning: string | null;
}

const DAYS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
const PAIRS = [
  { num: 1, time: "08:45-10:05" },
  { num: 2, time: "10:20-11:40" },
  { num: 3, time: "11:55-13:15" },
  { num: 4, time: "13:30-14:50" },
  { num: 5, time: "15:05-16:25" },
  { num: 6, time: "16:40-18:00" },
  { num: 7, time: "18:15-19:35" },
];

const getTypeStyles = (type: string) => {
  const t = type?.toLowerCase() || "";
  if (t.includes("лекция") || t.includes("lecture"))
    return {
      bg: "bg-[#e6fffa]",
      border: "border-[#2c7a7b]",
      text: "text-[#2c7a7b]",
    };
  if (t.includes("лабораторная") || t.includes("lab"))
    return {
      bg: "bg-[#f3e8ff]",
      border: "border-[#7e22ce]",
      text: "text-[#7e22ce]",
    };
  return {
    bg: "bg-[#e0f2fe]",
    border: "border-[#0369a1]",
    text: "text-[#0369a1]",
  }; // Default to Practice
};

const DraggableCard: React.FC<{
  entry: ScheduleEntry;
  selectedGroup: string;
  viewMode?: "group" | "teacher";
  dayIdx?: number;
  pairNum?: number;
  count?: number;
}> = ({ entry, selectedGroup, viewMode, dayIdx, pairNum, count }) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `card-${entry.id}`,
      data: { ...entry, dayIdx, pairNum },
    });

  const style = {
    transform: CSS.Translate.toString(transform),
    zIndex: isDragging ? 100 : 1,
    opacity: isDragging ? 0.5 : 1,
    touchAction: "none",
  };

  const styles = getTypeStyles(entry.stream_type);

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`${styles.bg} ${styles.border} border border-l-4 rounded-lg p-2 shadow-sm relative group/card hover:shadow-md transition-shadow cursor-grab active:cursor-grabbing ${entry.warning ? "ring-2 ring-red-500 ring-offset-1" : ""}`}
      title={entry.warning || undefined}
    >
      {count && count > 1 && (
        <div className="absolute -top-2 -right-2 bg-brand text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shadow-sm border border-white z-10">
          {count}
        </div>
      )}
      {count && count > 1 && (
        <div className="absolute inset-0 border border-black/5 rounded-lg -rotate-1 -translate-x-1 translate-y-1 bg-white/50 -z-10" />
      )}
      {count && count > 2 && (
        <div className="absolute inset-0 border border-black/5 rounded-lg -rotate-2 -translate-x-2 translate-y-2 bg-white/30 -z-20" />
      )}
      <div className="flex justify-between items-start mb-1">
        <div className="flex items-center gap-1">
          <div className="p-0.5 hover:bg-black/5 rounded">
            <GripVertical size={10} className="text-text-tertiary" />
          </div>
          <span className={`text-[9px] font-bold uppercase ${styles.text}`}>
            {entry.stream_type}
          </span>
        </div>
        <div className="flex gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
          {entry.date ? (
            <button
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                (
                  window as unknown as { unassignEntry: (id: number) => void }
                ).unassignEntry(entry.id);
              }}
              className="p-1 hover:bg-black/5 rounded text-text-tertiary hover:text-orange-500 pointer-events-auto"
              title="Убрать в невыставленные"
            >
              <X size={12} />
            </button>
          ) : (
            <button
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                (
                  window as unknown as { deleteEntry: (id: number) => void }
                ).deleteEntry(entry.id);
              }}
              className="p-1 hover:bg-black/5 rounded text-text-tertiary hover:text-red-500 pointer-events-auto"
              title="Удалить навсегда"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>
      <div className="text-[11px] font-bold text-text-primary leading-tight mb-2 line-clamp-2">
        {entry.event_name}
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-1 text-[10px] text-text-secondary">
          <MapPin size={10} className="shrink-0" />
          <span className="truncate">{entry.room_id || "—"}</span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-text-secondary">
          <User size={10} className="shrink-0" />
          <span className="truncate">{entry.teacher || "—"}</span>
        </div>
        {(selectedGroup === "Все" || viewMode === "teacher") && (
          <div className="mt-1 pt-1 border-t border-black/5 text-[9px] font-bold text-text-tertiary">
            {entry.group_name}
          </div>
        )}
      </div>
      {entry.warning && (
        <div className="mt-2 p-1.5 bg-red-50 border border-red-100 rounded text-[9px] text-red-600 font-medium flex items-start gap-1">
          <AlertCircle size={10} className="shrink-0 mt-0.5" />
          <span>{entry.warning}</span>
        </div>
      )}
    </div>
  );
};

const DroppableCell: React.FC<{
  dayIdx: number;
  pairNum: number;
  children: React.ReactNode;
}> = ({ dayIdx, pairNum, children }) => {
  const { isOver, setNodeRef } = useDroppable({
    id: `cell-${dayIdx}-${pairNum}`,
    data: { dayIdx, pairNum },
  });

  return (
    <td
      ref={setNodeRef}
      className={`p-2 border-l border-border-light align-top min-h-[140px] transition-colors relative ${isOver ? "bg-brand/5" : "bg-white hover:bg-gray-50/30"}`}
    >
      <div className="flex flex-col gap-2 min-h-[100px]">{children}</div>
    </td>
  );
};

const SidebarDroppable: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isOver, setNodeRef } = useDroppable({
    id: "sidebar",
    data: { isSidebar: true },
  });

  return (
    <div
      ref={setNodeRef}
      className={`flex-1 overflow-y-auto p-4 transition-colors ${isOver ? "bg-brand/5 ring-2 ring-brand ring-inset" : ""}`}
    >
      <div className="grid grid-cols-1 gap-3">{children}</div>
    </div>
  );
};

export const SchedulePage: React.FC = () => {
  const { taskId } = useParams<{ taskId?: string }>();
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tasks, setTasks] = useState<{ id: number; created_at: string }[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(
    taskId || null,
  );
  const [selectedGroup, setSelectedGroup] = useState<string>("");
  const [groups, setGroups] = useState<string[]>([]);
  const [teachers, setTeachers] = useState<{ id: string; name: string }[]>([]);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string>("");
  const [viewMode, setViewMode] = useState<"group" | "teacher">("group");
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const [applyExtracurricularToStream, setApplyExtracurricularToStream] =
    useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/tasks`);
      const data = await res.json();
      setTasks(data);
      if (!selectedTaskId && data.length > 0) {
        setSelectedTaskId(data[0].id.toString());
      }
    } catch {
      console.error("Failed to fetch tasks");
    }
  }, [selectedTaskId]);

  const fetchGroups = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/groups`);
      const data = await res.json();
      const fetchedGroups = data.groups || [];
      setGroups(fetchedGroups);
      if (!selectedGroup) {
        setSelectedGroup(fetchedGroups[0] || "");
      }
    } catch {
      console.error("Failed to fetch groups");
    }
  }, [selectedGroup]);

  const fetchTeachersList = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/teachers`);
      const data = await res.json();
      setTeachers(data);
      if (!selectedTeacherId && data.length > 0) {
        setSelectedTeacherId(data[0].id);
      }
    } catch {
      console.error("Failed to fetch teachers");
    }
  }, [selectedTeacherId]);

  const fetchSchedule = useCallback(
    async (id: string, mode: "group" | "teacher", filterId: string) => {
      setIsLoading(true);
      try {
        let url = `${API_BASE_URL}/api/v1/scheduler/schedule?task_id=${id}`;
        if (mode === "group" && filterId) {
          url += `&group_name=${encodeURIComponent(filterId)}`;
        } else if (mode === "teacher" && filterId) {
          url += `&teacher_id=${filterId}`;
        }
        const res = await fetch(url);
        const data = await res.json();
        setEntries(data);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    },
    [setEntries],
  );

  const handleExport = () => {
    if (selectedTaskId) {
      window.open(
        `${API_BASE_URL}/api/v1/scheduler/export?task_id=${selectedTaskId}`,
        "_blank",
      );
    }
  };

  useEffect(() => {
    fetchTasks();
    fetchGroups();
    fetchTeachersList();
  }, [fetchTasks, fetchGroups, fetchTeachersList]);

  useEffect(() => {
    if (selectedTaskId) {
      const filterId = viewMode === "group" ? selectedGroup : selectedTeacherId;
      fetchSchedule(selectedTaskId, viewMode, filterId);
    }
  }, [
    selectedTaskId,
    viewMode,
    selectedGroup,
    selectedTeacherId,
    fetchSchedule,
  ]);

  // Derive weeks from entries
  const availableWeeks = React.useMemo(() => {
    const weekMap = new Map<string, string>();
    entries.forEach((e) => {
      if (!e.date) return;
      const d = new Date(e.date);
      if (isNaN(d.getTime())) return;

      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const weekKey = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, "0")}-${String(monday.getDate()).padStart(2, "0")}`;

      if (!weekMap.has(weekKey)) {
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        weekMap.set(
          weekKey,
          `${monday.toLocaleDateString()} — ${sunday.toLocaleDateString()}`,
        );
      }
    });
    return Array.from(weekMap.entries()).sort((a, b) =>
      a[0].localeCompare(b[0]),
    );
  }, [entries]);

  useEffect(() => {
    if (availableWeeks.length > 0 && !selectedWeek) {
      setSelectedWeek(availableWeeks[0][0]);
    }
  }, [availableWeeks, selectedWeek]);

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over) {
      const activeId = active.id.toString();
      if (!activeId.startsWith("card-")) return;
      const entryId = activeId.replace("card-", "");
      const { dayIdx, pairNum, isSidebar } = over.data.current as {
        dayIdx?: number;
        pairNum?: number;
        isSidebar?: boolean;
      };

      if (isSidebar) {
        // Move to sidebar
        unassignEntry(Number(entryId), true);
        return;
      }

      if (dayIdx === undefined || pairNum === undefined || !selectedWeek)
        return;

      // Parse selectedWeek as local date to avoid timezone shift
      const [year, month, day] = selectedWeek.split("-").map(Number);
      const mondayDate = new Date(year, month - 1, day);

      const targetDate = new Date(mondayDate);
      targetDate.setDate(mondayDate.getDate() + dayIdx);

      const dateStr = `${targetDate.getFullYear()}-${String(targetDate.getMonth() + 1).padStart(2, "0")}-${String(targetDate.getDate()).padStart(2, "0")}`;

      // Optimistic update
      setEntries((prev) =>
        prev.map((e) =>
          e.id.toString() === entryId.toString()
            ? { ...e, date: dateStr, lesson_number: pairNum }
            : e,
        ),
      );

      try {
        const res = await fetch(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${entryId}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              date: dateStr,
              lesson_number: pairNum,
              apply_to_stream: applyExtracurricularToStream,
            }),
          },
        );
        const result = await res.json();
        if (result.entries) {
          setEntries(result.entries);
        }
      } catch (error) {
        console.error("Update failed:", error);
      }
    }
  };

  const deleteEntry = useCallback(async (id: number) => {
    if (!confirm("Вы уверены, что хотите удалить эту пару навсегда?")) return;

    setEntries((prev) => prev.filter((e) => e.id !== id));

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/scheduler/schedule/${id}`,
        {
          method: "DELETE",
        },
      );
      const result = await res.json();
      if (result.entries) {
        setEntries(result.entries);
      }
    } catch (e) {
      console.error("Delete failed:", e);
    }
  }, []);

  const unassignEntry = useCallback(
    async (id: number, skipOptimistic = false) => {
      if (!skipOptimistic) {
        setEntries((prev) =>
          prev.map((e) =>
            e.id === id ? { ...e, date: "", lesson_number: 0 } : e,
          ),
        );
      }

      try {
        const res = await fetch(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${id}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              date: null,
              lesson_number: null,
            }),
          },
        );
        const result = await res.json();
        if (result.entries) {
          setEntries(result.entries);
        }
      } catch (e) {
        console.error("Unassign failed:", e);
      }
    },
    [],
  );

  // Expose to cards
  useEffect(() => {
    const win = window as unknown as {
      deleteEntry: typeof deleteEntry | null;
      unassignEntry: typeof unassignEntry | null;
    };
    win.deleteEntry = deleteEntry;
    win.unassignEntry = unassignEntry;
    return () => {
      win.deleteEntry = null;
      win.unassignEntry = null;
    };
  }, [deleteEntry, unassignEntry]);

  const assignedEntries = entries.filter((e) => e.date);
  const unassignedEntries = entries.filter((e) => !e.date);
  const filteredUnassigned = unassignedEntries.filter((e) => {
    if (viewMode === "group") {
      return selectedGroup === "Все" || e.group_name === selectedGroup;
    }
    return e.teacher_id?.toString() === selectedTeacherId;
  });

  const groupedUnassigned = React.useMemo(() => {
    const groups: Record<string, ScheduleEntry[]> = {};
    filteredUnassigned.forEach((e) => {
      const key = `${e.event_name}-${e.stream_type}-${e.group_name}-${e.teacher_id || "none"}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(e);
    });
    return Object.values(groups).sort((a, b) =>
      a[0].event_name.localeCompare(b[0].event_name),
    );
  }, [filteredUnassigned]);

  const academicUnassigned = groupedUnassigned.filter(
    (g) => g[0].stream_type !== "Внеучебное мероприятие",
  );
  const extracurricularUnassigned = groupedUnassigned.filter(
    (g) => g[0].stream_type === "Внеучебное мероприятие",
  );

  return (
    <div className="space-y-6">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Интерактивное расписание
          </h1>
          <p className="text-text-secondary mt-1 text-sm">
            Просмотр и ручная корректировка сгенерированного расписания.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-border-light rounded-xl text-sm font-semibold hover:bg-gray-50 transition-all"
          >
            <Download size={18} />
            Экспорт Excel
          </button>
        </div>
      </header>

      <div className="bg-white p-4 rounded-2xl border border-border-light shadow-sm flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <Calendar size={18} className="text-text-tertiary" />
          <select
            value={selectedTaskId || ""}
            onChange={(e) => setSelectedTaskId(e.target.value)}
            className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
          >
            <option value="">Выберите расчет...</option>
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>
                Расчет #{t.id} ({new Date(t.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
        </div>

        <div className="h-6 w-px bg-border-light mx-2" />

        {/* Mode & Filters Toolbar */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="flex bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setViewMode("group")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  viewMode === "group"
                    ? "bg-white text-brand shadow-sm"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <Users size={16} />
                По группам
              </button>
              <button
                onClick={() => setViewMode("teacher")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  viewMode === "teacher"
                    ? "bg-white text-brand shadow-sm"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <UserCheck size={16} />
                По педагогам
              </button>
            </div>

            {viewMode === "group" ? (
              <select
                value={selectedGroup}
                onChange={(e) => setSelectedGroup(e.target.value)}
                className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
              >
                {groups.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
                <option value="Все">Все группы</option>
              </select>
            ) : (
              <select
                value={selectedTeacherId}
                onChange={(e) => setSelectedTeacherId(e.target.value)}
                className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
              >
                {teachers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {availableWeeks.length > 1 && (
          <>
            <div className="h-6 w-px bg-border-light mx-2" />
            <div className="flex items-center gap-2">
              <button
                disabled={
                  availableWeeks.findIndex((w) => w[0] === selectedWeek) <= 0
                }
                onClick={() => {
                  const idx = availableWeeks.findIndex(
                    (w) => w[0] === selectedWeek,
                  );
                  if (idx > 0) setSelectedWeek(availableWeeks[idx - 1][0]);
                }}
                className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
              >
                <ChevronLeft size={18} />
              </button>
              <select
                value={selectedWeek || ""}
                onChange={(e) => setSelectedWeek(e.target.value)}
                className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer text-sm"
              >
                {availableWeeks.map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                disabled={
                  availableWeeks.findIndex((w) => w[0] === selectedWeek) >=
                  availableWeeks.length - 1
                }
                onClick={() => {
                  const idx = availableWeeks.findIndex(
                    (w) => w[0] === selectedWeek,
                  );
                  if (idx < availableWeeks.length - 1)
                    setSelectedWeek(availableWeeks[idx + 1][0]);
                }}
                className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </>
        )}
      </div>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-text-secondary font-medium">
          Загрузка расписания...
        </div>
      ) : entries.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center text-text-secondary gap-4 bg-white rounded-2xl border border-dashed border-border-light">
          <AlertCircle size={48} opacity={0.2} />
          <p>Выберите задачу генерации для просмотра сетки</p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-6 items-start">
            {/* Grid Area */}
            <div className="flex-1 overflow-x-auto bg-white rounded-2xl border border-border-light shadow-sm">
              <table className="w-full border-collapse min-w-[800px] table-fixed">
                <thead>
                  <tr className="border-b border-border-light bg-bg-base/30">
                    <th className="p-4 text-left text-xs font-bold text-text-tertiary uppercase w-24">
                      Пара
                    </th>
                    {DAYS.map((day) => (
                      <th
                        key={day}
                        className="p-4 text-center text-xs font-bold text-text-tertiary uppercase border-l border-border-light"
                      >
                        {day}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PAIRS.map((pair) => (
                    <tr
                      key={pair.num}
                      className="border-b border-border-light last:border-0 min-h-[140px]"
                    >
                      <td className="p-4 text-center bg-bg-base/10">
                        <div className="font-bold text-text-primary text-lg">
                          {pair.num}
                        </div>
                        <div className="text-[10px] text-text-tertiary font-semibold">
                          {pair.time}
                        </div>
                      </td>
                      {DAYS.map((day, dayIdx) => {
                        const dayEntries = assignedEntries.filter((e) => {
                          if (!e.date) return false;
                          const d = new Date(e.date);
                          if (isNaN(d.getTime())) return false;

                          const dayNum = (d.getDay() + 6) % 7;

                          // Week filtering
                          const monday = new Date(d);
                          monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
                          const weekKey = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, "0")}-${String(monday.getDate()).padStart(2, "0")}`;

                          return (
                            dayNum === dayIdx &&
                            weekKey === selectedWeek &&
                            e.lesson_number === pair.num &&
                            (viewMode === "group"
                              ? selectedGroup === "Все" ||
                                e.group_name === selectedGroup
                              : e.teacher_id?.toString() === selectedTeacherId)
                          );
                        });

                        return (
                          <DroppableCell
                            key={day}
                            dayIdx={dayIdx}
                            pairNum={pair.num}
                          >
                            {dayEntries.map((entry) => (
                              <DraggableCard
                                key={entry.id}
                                entry={entry}
                                selectedGroup={selectedGroup}
                                viewMode={viewMode}
                                dayIdx={dayIdx}
                                pairNum={pair.num}
                              />
                            ))}
                          </DroppableCell>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Unassigned Sidebar */}
            <div className="w-80 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col h-[800px] sticky top-6">
              <div className="p-4 border-b border-border-light bg-bg-base/20 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers size={18} className="text-brand" />
                  <h2 className="font-bold text-text-primary">
                    {viewMode === "group" ? "Невыставленные" : "Пары педагога"}
                  </h2>
                </div>
                <span className="bg-brand/10 text-brand text-xs font-bold px-2 py-0.5 rounded-full">
                  {groupedUnassigned.length}
                </span>
              </div>

              <SidebarDroppable>
                {filteredUnassigned.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-text-tertiary gap-2 py-20 text-center">
                    <X size={32} opacity={0.3} />
                    <p className="text-xs font-medium">
                      Нет невыставленных пар
                    </p>
                  </div>
                ) : (
                  <>
                    {academicUnassigned.length > 0 && (
                      <div className="text-[10px] font-bold text-text-tertiary uppercase mt-1">
                        Учебные пары
                      </div>
                    )}
                    {academicUnassigned.map((group) => (
                      <DraggableCard
                        key={group[0].id}
                        entry={group[0]}
                        selectedGroup={selectedGroup}
                        viewMode={viewMode}
                        count={group.length}
                      />
                    ))}

                    {extracurricularUnassigned.length > 0 && (
                      <>
                        <div className="mt-2 pt-3 border-t border-border-light text-[10px] font-bold text-text-tertiary uppercase">
                          Внеучебные мероприятия
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-text-secondary mb-1">
                          <input
                            type="checkbox"
                            checked={applyExtracurricularToStream}
                            onChange={(e) =>
                              setApplyExtracurricularToStream(e.target.checked)
                            }
                            className="rounded border-gray-300 text-brand focus:ring-brand"
                          />
                          Ставить всему потоку
                        </label>
                        {extracurricularUnassigned.map((group) => (
                          <DraggableCard
                            key={group[0].id}
                            entry={group[0]}
                            selectedGroup={selectedGroup}
                            viewMode={viewMode}
                            count={group.length}
                          />
                        ))}
                      </>
                    )}
                  </>
                )}
              </SidebarDroppable>

              <div className="p-4 bg-orange-50 border-t border-orange-100 rounded-b-2xl">
                <p className="text-[10px] text-orange-700 leading-relaxed font-medium">
                  Перетащите карточки отсюда в сетку расписания, чтобы назначить
                  им время и день.
                </p>
              </div>
            </div>
          </div>
        </DndContext>
      )}
    </div>
  );
};
