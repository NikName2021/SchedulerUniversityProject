import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  Calendar,
  Filter,
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
} from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
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
}> = ({ entry, selectedGroup }) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: entry.id.toString(),
      data: entry,
    });

  const style = {
    transform: CSS.Translate.toString(transform),
    zIndex: isDragging ? 100 : 1,
    opacity: isDragging ? 0.5 : 1,
  };

  const styles = getTypeStyles(entry.stream_type);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${styles.bg} ${styles.border} border border-l-4 rounded-lg p-2 shadow-sm relative group/card hover:shadow-md transition-shadow cursor-grab active:cursor-grabbing ${entry.warning ? "ring-2 ring-red-500 ring-offset-1" : ""}`}
      title={entry.warning || undefined}
    >
      <div className="flex justify-between items-start mb-1">
        <div className="flex items-center gap-1">
          <div
            {...listeners}
            {...attributes}
            className="p-0.5 hover:bg-black/5 rounded cursor-grab"
          >
            <GripVertical size={10} className="text-text-tertiary" />
          </div>
          <span className={`text-[9px] font-bold uppercase ${styles.text}`}>
            {entry.stream_type}
          </span>
        </div>
        <div className="flex gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
          {entry.date ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                (
                  window as unknown as { unassignEntry: (id: number) => void }
                ).unassignEntry(entry.id);
              }}
              className="p-1 hover:bg-black/5 rounded text-text-tertiary hover:text-orange-500"
              title="Убрать в невыставленные"
            >
              <X size={12} />
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                (
                  window as unknown as { deleteEntry: (id: number) => void }
                ).deleteEntry(entry.id);
              }}
              className="p-1 hover:bg-black/5 rounded text-text-tertiary hover:text-red-500"
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
        {selectedGroup === "Все" && (
          <div className="mt-1 pt-1 border-t border-black/5 text-[9px] font-bold text-text-tertiary">
            {entry.group_name}
          </div>
        )}
      </div>
      {entry.warning && (
        <div className="mt-1 flex items-center gap-1 text-[9px] text-red-500 font-bold">
          <AlertCircle size={10} /> Конфликт
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
  const [selectedGroup, setSelectedGroup] = useState<string>("Все");
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
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
      setGroups(data.groups || []);
    } catch {
      console.error("Failed to fetch groups");
    }
  }, []);

  const fetchSchedule = useCallback(
    async (id: string) => {
      setIsLoading(true);
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/v1/scheduler/schedule?task_id=${id}`,
        );
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
  }, [fetchTasks, fetchGroups]);

  useEffect(() => {
    if (selectedTaskId) {
      fetchSchedule(selectedTaskId);
    }
  }, [selectedTaskId, fetchSchedule]);

  // Derive weeks from entries
  const availableWeeks = React.useMemo(() => {
    const weekMap = new Map<string, string>();
    entries.forEach((e) => {
      const d = new Date(e.date);
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const weekKey = monday.toISOString().split("T")[0];

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

    if (over && active.id !== over.id) {
      const entryId = active.id;
      const { dayIdx, pairNum, isSidebar } = over.data.current as {
        dayIdx?: number;
        pairNum?: number;
        isSidebar?: boolean;
      };
      const entry = active.data.current as ScheduleEntry;

      if (isSidebar) {
        // Move to sidebar
        unassignEntry(Number(entryId), true);
        return;
      }

      if (dayIdx === undefined || pairNum === undefined) return;

      // Calculate new date based on dayIdx
      // For now, we assume the schedule is for a specific week starting from some Monday
      // We'll find the first Monday of the current task's range
      const currentEntryDate = new Date(entry.date);
      const diff = dayIdx - ((currentEntryDate.getDay() + 6) % 7);
      const newDate = new Date(currentEntryDate);
      newDate.setDate(newDate.getDate() + diff);
      const dateStr = newDate.toISOString().split("T")[0];

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
            }),
          },
        );
        const result = await res.json();

        // Update with backend warning if any
        setEntries((prev) =>
          prev.map((e) =>
            e.id.toString() === entryId.toString()
              ? { ...e, warning: result.warning }
              : e,
          ),
        );
      } catch (e) {
        console.error("Update failed:", e);
      }
    }
  };

  const deleteEntry = useCallback(async (id: number) => {
    if (!confirm("Вы уверены, что хотите удалить эту пару навсегда?")) return;

    setEntries((prev) => prev.filter((e) => e.id !== id));

    try {
      await fetch(`${API_BASE_URL}/api/v1/scheduler/schedule/${id}`, {
        method: "DELETE",
      });
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
        await fetch(`${API_BASE_URL}/api/v1/scheduler/schedule/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            date: null,
            lesson_number: null,
          }),
        });
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
  const filteredUnassigned = unassignedEntries.filter(
    (e) => selectedGroup === "Все" || e.group_name === selectedGroup,
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

        <div className="flex items-center gap-2">
          <Filter size={18} className="text-text-tertiary" />
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
          >
            <option value="Все">Все группы</option>
            {groups.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
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
                          const d = new Date(e.date);
                          const dayNum = (d.getDay() + 6) % 7;

                          // Week filtering
                          const monday = new Date(d);
                          monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
                          const weekKey = monday.toISOString().split("T")[0];

                          return (
                            dayNum === dayIdx &&
                            weekKey === selectedWeek &&
                            e.lesson_number === pair.num &&
                            (selectedGroup === "Все" ||
                              e.group_name === selectedGroup)
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
                    Невыставленные
                  </h2>
                </div>
                <span className="bg-brand/10 text-brand text-xs font-bold px-2 py-0.5 rounded-full">
                  {filteredUnassigned.length}
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
                  filteredUnassigned.map((entry) => (
                    <DraggableCard
                      key={entry.id}
                      entry={entry}
                      selectedGroup={selectedGroup}
                    />
                  ))
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
