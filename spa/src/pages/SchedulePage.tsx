import React, { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  Calendar,
  Download,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Users,
  UserCheck,
} from "lucide-react";
import {
  DndContext,
  closestCenter,
  pointerWithin,
  KeyboardSensor,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type CollisionDetection,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { createPortal } from "react-dom";
import { API_BASE_URL, apiFetchJson } from "../api/apiConfig";
import {
  collectKnownSubgroups,
  groupLabelIncludesBase,
  groupLabelsOverlap,
} from "../utils/groupSelection";

import { useFeedback } from "../components/feedbackContext";
import { ScheduleCard, type CardActions } from "./schedule/ScheduleCard";
import { ScheduleQuality, type QualityData } from "./schedule/ScheduleQuality";
import { EntryDetailsDrawer } from "./schedule/EntryDetailsDrawer";
import { ScheduleGrid } from "./schedule/ScheduleGrid";
import { ConflictsSidebar } from "./schedule/ConflictsSidebar";
import { UnassignedSidebar } from "./schedule/UnassignedSidebar";
import {
  DAYS,
  PAIRS,
  WEEK_DATE_FORMATTER,
  getSlotKey,
  getWeekDayDate,
  getWeekKey,
  parseLocalDate,
} from "./schedule/week";
import type { ScheduleEntry, ScheduleEntryDetails } from "./schedule/types";
import "./schedule/SchedulePage.css";

interface GenerationTaskSummary {
  id: number;
  created_at: string;
  semester_batch_id: string | null;
  planning_week: {
    id: number;
    sequence_number: number;
    starts_on: string;
    ends_on: string;
    period_id: number;
    period_name: string | null;
  } | null;
}

interface ScheduleSource {
  id: string;
  label: string;
  kind: "task" | "semester";
}

type UnavailableSlot = [string, number];

interface ScheduleAvailability {
  unavailable: {
    teacher: Record<string, UnavailableSlot[]>;
    group: Record<string, UnavailableSlot[]>;
    global: Record<string, UnavailableSlot[]>;
  };
}

const detectDropTarget: CollisionDetection = (args) =>
  args.pointerCoordinates ? pointerWithin(args) : closestCenter(args);

export const SchedulePage: React.FC = () => {
  const { notify, showDialog, download } = useFeedback();
  const { taskId } = useParams<{ taskId?: string }>();
  const [searchParams] = useSearchParams();
  const requestedSemesterBatchId = searchParams.get("semester_batch_id");
  const requestedWeek = searchParams.get("week");
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [tasks, setTasks] = useState<GenerationTaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(
    requestedSemesterBatchId
      ? `semester:${requestedSemesterBatchId}`
      : taskId || null,
  );
  const [selectedGroup, setSelectedGroup] = useState<string>("");
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedTeacherId, setSelectedTeacherId] = useState<string>("");
  const [viewMode, setViewMode] = useState<"group" | "teacher">("group");
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const [applyExtracurricularToStream, setApplyExtracurricularToStream] =
    useState(false);

  const [quality, setQuality] = useState<QualityData | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [conflictsOpen, setConflictsOpen] = useState(false);
  const [entryDetails, setEntryDetails] = useState<ScheduleEntryDetails | null>(
    null,
  );
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [activeEntryId, setActiveEntryId] = useState<number | null>(null);
  const [scheduleAvailability, setScheduleAvailability] =
    useState<ScheduleAvailability | null>(null);

  const calculationTeachers = React.useMemo(() => {
    const teachers = new Map<string, string>();
    entries.forEach((entry) => {
      if (entry.teacher_id && entry.teacher) {
        teachers.set(entry.teacher_id.toString(), entry.teacher);
      }
    });
    return Array.from(teachers, ([id, name]) => ({ id, name })).sort((a, b) =>
      a.name.localeCompare(b.name, "ru"),
    );
  }, [entries]);

  useEffect(() => {
    setSelectedTeacherId((current) =>
      calculationTeachers.some((teacher) => teacher.id === current)
        ? current
        : calculationTeachers[0]?.id || "",
    );
  }, [calculationTeachers]);

  const conflictedEntries = React.useMemo(() => {
    return entries.filter(
      (entry) =>
        entry.warning &&
        (viewMode === "group"
          ? selectedGroup === "Все" ||
            groupLabelIncludesBase(entry.group_name, selectedGroup)
          : entry.teacher_id?.toString() === selectedTeacherId),
    );
  }, [entries, selectedGroup, selectedTeacherId, viewMode]);

  const focusConflict = (entry: ScheduleEntry) => {
    if (entry.date) setSelectedWeek(getWeekKey(entry.date));

    setTimeout(() => {
      const el = document.getElementById(`card-${entry.id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.querySelector<HTMLButtonElement>(".schedule-card__details")?.focus({
          preventScroll: true,
        });
        el.classList.add(
          "ring-4",
          "ring-red-500",
          "ring-offset-2",
          "scale-105",
        );
        setTimeout(() => {
          el.classList.remove(
            "ring-4",
            "ring-red-500",
            "ring-offset-2",
            "scale-105",
          );
        }, 2000);
      }
    }, 150);
  };

  const openEntryDetails = useCallback(
    async (entryId: number) => {
      setDetailsLoading(true);
      try {
        const details = await apiFetchJson<ScheduleEntryDetails>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${entryId}/details`,
          "Не удалось загрузить полную информацию о занятии",
        );
        setEntryDetails(details);
      } catch (error) {
        console.error(error);
        notify("Не удалось загрузить полную информацию о занятии");
      } finally {
        setDetailsLoading(false);
      }
    },
    [notify],
  );

  const sensors = useSensors(
    useSensor(MouseSensor, {
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
      const fetchedTasks = await apiFetchJson<GenerationTaskSummary[]>(
        `${API_BASE_URL}/api/v1/scheduler/tasks`,
        "Не удалось загрузить расчёты",
      );
      setTasks(fetchedTasks);
      setSelectedTaskId((current) => {
        if (current) {
          const selectedTask = fetchedTasks.find(
            (task) => task.id.toString() === current,
          );
          return selectedTask?.semester_batch_id
            ? `semester:${selectedTask.semester_batch_id}`
            : current;
        }
        if (requestedSemesterBatchId)
          return `semester:${requestedSemesterBatchId}`;
        const requestedTask = fetchedTasks.find(
          (task) => task.id === Number(taskId),
        );
        if (requestedTask?.semester_batch_id) {
          return `semester:${requestedTask.semester_batch_id}`;
        }
        return (
          requestedTask?.id.toString() || fetchedTasks[0]?.id.toString() || null
        );
      });
    } catch {
      console.error("Failed to fetch tasks");
    }
  }, [requestedSemesterBatchId, taskId]);

  const fetchGroups = useCallback(async () => {
    if (!selectedTaskId) {
      setGroups([]);
      setSelectedGroup("");
      return;
    }
    try {
      const semesterBatchId = selectedTaskId.startsWith("semester:")
        ? selectedTaskId.slice("semester:".length)
        : null;
      const query = semesterBatchId
        ? `semester_batch_id=${encodeURIComponent(semesterBatchId)}`
        : `task_id=${encodeURIComponent(selectedTaskId)}`;
      const data = await apiFetchJson<{ groups?: string[] }>(
        `${API_BASE_URL}/api/v1/scheduler/groups?${query}`,
        "Не удалось загрузить группы расчёта",
      );
      const fetchedGroups: string[] = data.groups || [];
      setGroups(fetchedGroups);
      setSelectedGroup((current) =>
        current === "Все" || fetchedGroups.includes(current)
          ? current
          : fetchedGroups[0] || "",
      );
    } catch {
      console.error("Failed to fetch groups");
    }
  }, [selectedTaskId]);

  const fetchSchedule = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const semesterBatchId = id.startsWith("semester:")
        ? id.slice("semester:".length)
        : null;
      const url = semesterBatchId
        ? `${API_BASE_URL}/api/v1/scheduler/schedule?semester_batch_id=${encodeURIComponent(semesterBatchId)}`
        : `${API_BASE_URL}/api/v1/scheduler/schedule?task_id=${id}`;
      const data = await apiFetchJson<ScheduleEntry[]>(
        url,
        "Не удалось загрузить расписание",
      );
      setEntries(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleExport = () => {
    if (selectedTaskId) {
      const semesterBatchId = selectedTaskId.startsWith("semester:")
        ? selectedTaskId.slice("semester:".length)
        : null;
      void download(
        semesterBatchId
          ? `${API_BASE_URL}/api/v1/scheduler/export?semester_batch_id=${encodeURIComponent(semesterBatchId)}`
          : `${API_BASE_URL}/api/v1/scheduler/export?task_id=${selectedTaskId}`,
        "schedule.xlsx",
      );
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    void fetchGroups();
  }, [fetchGroups]);

  useEffect(() => {
    if (selectedTaskId) {
      fetchSchedule(selectedTaskId);
    }
  }, [selectedTaskId, fetchSchedule]);

  // Fetch quality when group/task changes
  useEffect(() => {
    if (
      !selectedTaskId ||
      selectedTaskId.startsWith("semester:") ||
      viewMode !== "group" ||
      !selectedGroup ||
      selectedGroup === "Все"
    ) {
      setQuality(null);
      return;
    }
    const fetchQuality = async () => {
      setQualityLoading(true);
      try {
        const data = await apiFetchJson<QualityData>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/quality?task_id=${selectedTaskId}&group_name=${encodeURIComponent(selectedGroup)}`,
          "Не удалось загрузить оценку расписания",
        );
        setQuality(data);
      } catch {
        setQuality(null);
      } finally {
        setQualityLoading(false);
      }
    };
    fetchQuality();
  }, [selectedTaskId, selectedGroup, viewMode, entries.length]);

  // Derive weeks from entries
  const availableWeeks = React.useMemo(() => {
    const weekMap = new Map<string, string>();
    const semesterBatchId = selectedTaskId?.startsWith("semester:")
      ? selectedTaskId.slice("semester:".length)
      : null;
    const planningWeeks = semesterBatchId
      ? tasks
          .filter((task) => task.semester_batch_id === semesterBatchId)
          .map((task) => task.planning_week)
          .filter((week) => week !== null)
      : [];

    const dates =
      planningWeeks.length > 0
        ? planningWeeks.map((week) => week.starts_on)
        : entries.filter((entry) => entry.date).map((entry) => entry.date);

    dates.forEach((dateValue) => {
      const weekKey = getWeekKey(dateValue);
      const monday = parseLocalDate(weekKey);

      if (!weekMap.has(weekKey)) {
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        weekMap.set(
          weekKey,
          `${WEEK_DATE_FORMATTER.format(monday)} — ${WEEK_DATE_FORMATTER.format(sunday)}`,
        );
      }
    });
    return Array.from(weekMap.entries()).sort((a, b) =>
      a[0].localeCompare(b[0]),
    );
  }, [entries, selectedTaskId, tasks]);

  useEffect(() => {
    if (availableWeeks.length === 0) return;
    setSelectedWeek((current) => {
      if (current && availableWeeks.some(([week]) => week === current))
        return current;
      if (
        requestedWeek &&
        availableWeeks.some(([week]) => week === requestedWeek)
      ) {
        return requestedWeek;
      }
      return availableWeeks[0][0];
    });
  }, [availableWeeks, requestedWeek]);

  useEffect(() => {
    if (!selectedWeek) {
      setScheduleAvailability(null);
      return;
    }
    let cancelled = false;
    const loadAvailability = async () => {
      try {
        const endDate = getWeekDayDate(selectedWeek, DAYS.length - 1);
        const data = await apiFetchJson<ScheduleAvailability>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/availability?start_date=${selectedWeek}&end_date=${endDate}`,
          "Не удалось загрузить доступность",
        );
        if (!cancelled) setScheduleAvailability(data);
      } catch (error) {
        console.error(error);
        if (!cancelled) setScheduleAvailability(null);
      }
    };
    void loadAvailability();
    return () => {
      cancelled = true;
    };
  }, [selectedWeek]);

  const scheduleSources = React.useMemo<ScheduleSource[]>(() => {
    const semesterBatches = new Map<string, GenerationTaskSummary[]>();
    const standaloneTasks: GenerationTaskSummary[] = [];
    for (const task of tasks) {
      if (task.semester_batch_id) {
        const batch = semesterBatches.get(task.semester_batch_id) || [];
        batch.push(task);
        semesterBatches.set(task.semester_batch_id, batch);
      } else {
        standaloneTasks.push(task);
      }
    }
    const semesters = Array.from(semesterBatches.entries()).map(
      ([batchId, batch]) => {
        const firstTask = [...batch].sort(
          (left, right) =>
            (left.planning_week?.sequence_number || 0) -
            (right.planning_week?.sequence_number || 0),
        )[0];
        const title = firstTask.planning_week?.period_name || "Учебный период";
        return {
          id: `semester:${batchId}`,
          label: `${title} · ${batch.length} нед.`,
          kind: "semester" as const,
        };
      },
    );
    return [
      ...semesters,
      ...standaloneTasks.map((task) => ({
        id: task.id.toString(),
        label: `Расчёт #${task.id} · ${new Date(task.created_at).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" })}`,
        kind: "task" as const,
      })),
    ];
  }, [tasks]);

  const handleDragStart = (event: DragStartEvent) => {
    const activeId = event.active.id.toString();
    setActiveEntryId(
      activeId.startsWith("card-")
        ? Number(activeId.replace("card-", ""))
        : null,
    );
  };

  const handleDragCancel = () => setActiveEntryId(null);

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveEntryId(null);

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

      const dateStr = getWeekDayDate(selectedWeek, dayIdx);
      if (!availableSlotKeys.has(getSlotKey(dateStr, pairNum))) {
        notify("Этот слот занят группой или преподавателем");
        return;
      }

      const previousEntries = entries;
      // Optimistic update
      setEntries((prev) =>
        prev.map((e) =>
          e.id.toString() === entryId.toString()
            ? { ...e, date: dateStr, lesson_number: pairNum }
            : e,
        ),
      );

      try {
        const result = await apiFetchJson<{ entries?: ScheduleEntry[] }>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${entryId}`,
          "Не удалось перенести занятие",
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
        if (result.entries) {
          setEntries(result.entries);
        }
      } catch (error) {
        setEntries(previousEntries);
        notify(
          error instanceof Error
            ? error.message
            : "Не удалось перенести занятие",
        );
      }
    }
  };

  const deleteEntry = useCallback(
    async (id: number) => {
      const previousEntries = entries;
      setEntries((prev) => prev.filter((e) => e.id !== id));

      try {
        const result = await apiFetchJson<{ entries?: ScheduleEntry[] }>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${id}`,
          "Не удалось удалить занятие",
          {
            method: "DELETE",
          },
        );
        if (result.entries) {
          setEntries(result.entries);
        }
      } catch (error) {
        setEntries(previousEntries);
        notify(
          error instanceof Error ? error.message : "Не удалось удалить занятие",
        );
      }
    },
    [entries, notify],
  );

  const unassignEntry = useCallback(
    async (id: number, skipOptimistic = false) => {
      const previousEntries = entries;
      if (!skipOptimistic) {
        setEntries((prev) =>
          prev.map((e) =>
            e.id === id ? { ...e, date: "", lesson_number: 0 } : e,
          ),
        );
      }

      try {
        const result = await apiFetchJson<{ entries?: ScheduleEntry[] }>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${id}`,
          "Не удалось снять занятие со слота",
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              date: null,
              lesson_number: null,
            }),
          },
        );
        if (result.entries) {
          setEntries(result.entries);
        }
      } catch (error) {
        setEntries(previousEntries);
        notify(
          error instanceof Error
            ? error.message
            : "Не удалось снять занятие со слота",
        );
      }
    },
    [entries, notify],
  );

  const toggleEntryLock = useCallback(
    async (id: number, locked: boolean) => {
      try {
        const result = await apiFetchJson<{ entries?: ScheduleEntry[] }>(
          `${API_BASE_URL}/api/v1/scheduler/schedule/${id}`,
          "Не удалось изменить блокировку",
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_locked: locked }),
          },
        );
        if (result.entries) setEntries(result.entries);
      } catch (error) {
        notify(
          error instanceof Error
            ? error.message
            : "Не удалось изменить блокировку",
        );
      }
    },
    [notify],
  );

  const cardActions = React.useMemo<CardActions>(
    () => ({
      onOpenDetails: openEntryDetails,
      onToggleLock: toggleEntryLock,
      onUnassign: unassignEntry,
      onDelete: (id) =>
        showDialog({
          title: "Удалить занятие?",
          message:
            "Оно будет удалено из расчёта. Это действие нельзя отменить.",
          confirmLabel: "Удалить",
          onConfirm: () => void deleteEntry(id),
        }),
    }),
    [deleteEntry, openEntryDetails, showDialog, toggleEntryLock, unassignEntry],
  );

  const { entriesBySlot, unassignedEntries } = React.useMemo(() => {
    const entriesBySlot = new Map<string, ScheduleEntry[]>();
    const unassignedEntries: ScheduleEntry[] = [];
    for (const entry of entries) {
      if (!entry.date) {
        unassignedEntries.push(entry);
        continue;
      }
      const key = getSlotKey(entry.date.slice(0, 10), entry.lesson_number);
      const slot = entriesBySlot.get(key);
      if (slot) slot.push(entry);
      else entriesBySlot.set(key, [entry]);
    }
    return { entriesBySlot, unassignedEntries };
  }, [entries]);

  const matchesView = useCallback(
    (entry: ScheduleEntry) =>
      viewMode === "group"
        ? selectedGroup === "Все" ||
          groupLabelIncludesBase(entry.group_name, selectedGroup)
        : entry.teacher_id?.toString() === selectedTeacherId,
    [viewMode, selectedGroup, selectedTeacherId],
  );
  const visibleEntriesBySlot = React.useMemo(
    () =>
      new Map(
        Array.from(entriesBySlot, ([key, slot]) => [
          key,
          slot.filter(matchesView),
        ]),
      ),
    [entriesBySlot, matchesView],
  );
  const knownSubgroups = React.useMemo(
    () => collectKnownSubgroups(entries.map((entry) => entry.group_name)),
    [entries],
  );
  const activeEntry = React.useMemo(
    () => entries.find((entry) => entry.id === activeEntryId) || null,
    [activeEntryId, entries],
  );
  const availableSlotKeys = React.useMemo(() => {
    const available = new Set<string>();
    if (!activeEntry || !selectedWeek) return available;

    DAYS.forEach((_day, dayIdx) => {
      const date = getWeekDayDate(selectedWeek, dayIdx);
      PAIRS.forEach((pair) => {
        const slotIsListed = (slots: UnavailableSlot[] | undefined) =>
          slots?.some(
            ([blockedDate, blockedLesson]) =>
              blockedDate === date && blockedLesson === pair.num,
          ) || false;
        const hardUnavailable = scheduleAvailability?.unavailable;
        const violatesAvailability = Boolean(
          hardUnavailable &&
          (slotIsListed(hardUnavailable.global["*"]) ||
            (activeEntry.teacher &&
              slotIsListed(hardUnavailable.teacher[activeEntry.teacher])) ||
            slotIsListed(hardUnavailable.group[activeEntry.group_name])),
        );
        const slotKey = getSlotKey(date, pair.num);
        const hasConflict = entriesBySlot.get(slotKey)?.some((other) => {
          if (other.id === activeEntry.id) return false;
          const sameStream = Boolean(
            activeEntry.source_stream_id &&
            activeEntry.source_stream_id === other.source_stream_id,
          );
          if (sameStream) return false;

          const teacherIsBusy = Boolean(
            activeEntry.teacher_id &&
            activeEntry.teacher_id === other.teacher_id,
          );
          const groupIsBusy = groupLabelsOverlap(
            activeEntry.group_name,
            other.group_name,
            knownSubgroups,
          );
          return teacherIsBusy || groupIsBusy;
        });
        if (!hasConflict && !violatesAvailability) {
          available.add(slotKey);
        }
      });
    });

    return available;
  }, [
    activeEntry,
    entriesBySlot,
    knownSubgroups,
    scheduleAvailability,
    selectedWeek,
  ]);
  const filteredUnassigned = React.useMemo(
    () => unassignedEntries.filter(matchesView),
    [unassignedEntries, matchesView],
  );

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

  return (
    <div className="enterprise-page schedule-workspace">
      <header className="workspace-header">
        <div>
          <h1>Интерактивное расписание</h1>
          <p>Просмотр и ручная корректировка сгенерированного расписания.</p>
        </div>
        <div className="flex gap-3">
          <button onClick={handleExport} className="btn-secondary">
            <Download size={18} />
            Экспорт Excel
          </button>
        </div>
      </header>

      <div className="workspace-toolbar flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <Calendar size={18} className="text-text-tertiary" />
          <select
            aria-label="Расчёт расписания"
            value={selectedTaskId || ""}
            onChange={(e) => {
              setSelectedTaskId(e.target.value);
              setSelectedWeek(null);
            }}
            className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
          >
            <option value="">Выберите расчет...</option>
            {scheduleSources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.kind === "semester" ? "Семестр: " : ""}
                {source.label}
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
                aria-label="Группа"
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
                aria-label="Преподаватель"
                value={selectedTeacherId}
                onChange={(e) => setSelectedTeacherId(e.target.value)}
                className="bg-transparent border-none font-semibold text-text-primary focus:ring-0 cursor-pointer"
              >
                {calculationTeachers.length === 0 && (
                  <option value="">В расчёте нет педагогов</option>
                )}
                {calculationTeachers.map((t) => (
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
                aria-label="Предыдущая учебная неделя"
                title="Предыдущая учебная неделя"
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
                aria-label="Учебная неделя"
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
                aria-label="Следующая учебная неделя"
                title="Следующая учебная неделя"
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

        <button
          type="button"
          aria-expanded={conflictsOpen}
          onClick={() => setConflictsOpen(!conflictsOpen)}
          className={`ml-auto flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all shrink-0 cursor-pointer ${
            conflictsOpen
              ? "bg-red-50 text-red-600 ring-2 ring-red-500/20"
              : "bg-white border border-border-light text-text-secondary hover:bg-gray-50 shadow-sm"
          }`}
        >
          <AlertCircle
            size={16}
            className={
              conflictedEntries.length > 0
                ? "text-red-500 animate-pulse"
                : "text-text-tertiary"
            }
          />
          <span>Конфликты ({conflictedEntries.length})</span>
        </button>
      </div>

      {viewMode === "group" &&
        selectedGroup &&
        selectedGroup !== "Все" &&
        !qualityLoading &&
        quality && <ScheduleQuality quality={quality} />}

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
          collisionDetection={detectDropTarget}
          onDragStart={handleDragStart}
          onDragCancel={handleDragCancel}
          onDragEnd={handleDragEnd}
        >
          <div className="schedule-layout">
            <ScheduleGrid
              selectedWeek={selectedWeek}
              selectedGroup={selectedGroup}
              viewMode={viewMode}
              visibleEntriesBySlot={visibleEntriesBySlot}
              showAvailability={activeEntry !== null}
              availableSlotKeys={availableSlotKeys}
              cardActions={cardActions}
            />

            {conflictsOpen && (
              <ConflictsSidebar
                conflictedEntries={conflictedEntries}
                onSelect={focusConflict}
                onClose={() => setConflictsOpen(false)}
              />
            )}
            <UnassignedSidebar
              groupedUnassigned={groupedUnassigned}
              selectedGroup={selectedGroup}
              viewMode={viewMode}
              applyExtracurricularToStream={applyExtracurricularToStream}
              onApplyToStream={setApplyExtracurricularToStream}
              showAvailability={activeEntry !== null}
              cardActions={cardActions}
            />
          </div>
          {createPortal(
            <DragOverlay dropAnimation={null} zIndex={100}>
              {activeEntry && (
                <ScheduleCard
                  entry={activeEntry}
                  showGroup={selectedGroup === "Все" || viewMode === "teacher"}
                  count={
                    groupedUnassigned.find(
                      (group) => group[0].id === activeEntry.id,
                    )?.length
                  }
                />
              )}
            </DragOverlay>,
            document.body,
          )}
        </DndContext>
      )}
      <EntryDetailsDrawer
        details={entryDetails}
        loading={detailsLoading}
        onClose={() => setEntryDetails(null)}
      />
    </div>
  );
};
