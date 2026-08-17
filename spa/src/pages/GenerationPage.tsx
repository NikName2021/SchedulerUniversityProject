import React, { useState, useEffect, useCallback } from "react";
import {
  Zap,
  Users,
  Calendar,
  Info,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  X,
  Search,
  Filter,
  Settings2,
  Download,
  CalendarRange,
  Layers3,
  RefreshCcw,
  RotateCcw,
} from "lucide-react";
import { API_BASE_URL, apiFetch, openDownload } from "../api/apiConfig";

interface Stats {
  total_streams: number;
  active_streams: number;
  ignored_streams: number;
  total_groups: number;
  total_teachers: number;
}

interface StreamPreview {
  id: number;
  event_name: string;
  stream_type: string;
  teacher: string;
}

interface RuleProfileOption {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
}

interface PlanningWeek {
  id: number;
  period_id: number;
  sequence_number: number;
  starts_on: string;
  ends_on: string;
  status: string;
}

interface AcademicPeriod {
  id: number;
  name: string;
  starts_on: string;
  ends_on: string;
  status: string;
  weeks: PlanningWeek[];
}

interface BatchWeekState {
  week: PlanningWeek;
  taskId: number | null;
  status:
    | "pending"
    | "queued"
    | "running"
    | "success"
    | "partial"
    | "failed"
    | "canceled";
  progress: number;
  error: string | null;
}

interface WeeklyDemand {
  id: number;
  week_id: number;
  stream_id: number;
  lessons_count: number;
  priority: number;
  event_name: string | null;
  stream_type: string | null;
  teacher_name: string | null;
}

interface SemesterDistributionResult {
  period_id: number;
  streams_count: number;
  planned_lessons: number;
  published_lessons: number;
  distributed_lessons: number;
  weeks: Array<{
    week_id: number;
    sequence_number: number;
    lessons_count: number;
    streams_count: number;
  }>;
}

const ALL_TYPES = [
  "Лекция",
  "Семинар",
  "Лабораторная",
  "Зачет",
  "Внеучебное мероприятие",
];

import { useLocation } from "react-router-dom";

export const GenerationPage: React.FC = () => {
  const location = useLocation();
  const inheritedData = location.state as {
    groups?: string[];
    holidays?: string[];
    settings?: {
      enabled_types?: string[];
      priorities?: Record<string, string>;
    };
    start_date?: string;
    end_date?: string;
  } | null;

  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>(
    inheritedData?.groups || [],
  );
  const [holidays, setHolidays] = useState<string[]>(
    inheritedData?.holidays || [],
  );
  const [startDate, setStartDate] = useState<string>(
    inheritedData?.start_date?.split("T")[0] || "2025-09-01",
  );
  const [endDate, setEndDate] = useState<string>(
    inheritedData?.end_date?.split("T")[0] || "2025-09-07",
  );
  const [newHoliday, setNewHoliday] = useState("");
  const [, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [ruleProfiles, setRuleProfiles] = useState<RuleProfileOption[]>([]);
  const [ruleProfileId, setRuleProfileId] = useState<number | null>(null);
  const [generationMode, setGenerationMode] = useState<"week" | "semester">(
    "week",
  );
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [selectedWeekIds, setSelectedWeekIds] = useState<number[]>([]);
  const [demandCounts, setDemandCounts] = useState<Record<number, number>>({});
  const [isPreparingDemands, setIsPreparingDemands] = useState(false);
  const [distributionResult, setDistributionResult] =
    useState<SemesterDistributionResult | null>(null);
  const [batchWeeks, setBatchWeeks] = useState<BatchWeekState[]>([]);
  const [editingWeek, setEditingWeek] = useState<PlanningWeek | null>(null);
  const [weeklyDemands, setWeeklyDemands] = useState<WeeklyDemand[]>([]);
  const [isSavingDemands, setIsSavingDemands] = useState(false);
  const [demandSearch, setDemandSearch] = useState("");
  const [newPeriod, setNewPeriod] = useState({
    name: "",
    starts_on: "",
    ends_on: "",
  });
  const [status, setStatus] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [previewGroup, setPreviewGroup] = useState<string | null>(null);
  const [previewStreams, setPreviewStreams] = useState<StreamPreview[]>([]);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Filter types
  const [enabledTypes, setEnabledTypes] = useState<string[]>(
    inheritedData?.settings?.enabled_types || [
      "Лекция",
      "Семинар",
      "Лабораторная",
    ],
  );

  // Subject priorities
  const [subjectSummary, setSubjectSummary] = useState<
    Record<string, string[]>
  >({});
  const [subjectPriorities, setSubjectPriorities] = useState<
    Record<string, string>
  >(inheritedData?.settings?.priorities || {});
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);
  const [expandedDirections, setExpandedDirections] = useState<string[]>([]);

  const fetchSubjectSummary = useCallback(async () => {
    setIsSummaryLoading(true);
    try {
      const groupsParam = encodeURIComponent(selectedGroups.join(","));
      const typesParam = encodeURIComponent(enabledTypes.join(","));
      const res = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/subjects-summary?groups=${groupsParam}&types=${typesParam}`,
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to fetch summary");
      }
      const data = await res.json();
      setSubjectSummary(data);
      // Auto-expand all directions
      setExpandedDirections(Object.keys(data));
    } catch {
      console.error("Subject summary error");
      setSubjectSummary({});
    } finally {
      setIsSummaryLoading(false);
    }
  }, [selectedGroups, enabledTypes]);

  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [groupsRes, statsRes, profilesRes, periodsRes] = await Promise.all([
        apiFetch(`${API_BASE_URL}/api/v1/scheduler/groups`),
        apiFetch(`${API_BASE_URL}/api/v1/scheduler/stats`),
        apiFetch(`${API_BASE_URL}/api/v1/reference/rule-profiles`),
        apiFetch(`${API_BASE_URL}/api/v1/planning/periods`),
      ]);

      const groupsData = await groupsRes.json();
      const statsData = await statsRes.json();
      const profilesData = profilesRes.ok ? await profilesRes.json() : [];
      const periodsData = periodsRes.ok ? await periodsRes.json() : [];

      setGroups(groupsData.groups || []);
      // If no inherited groups, don't auto-select all
      if (!inheritedData?.groups) {
        setSelectedGroups([]);
      }
      setStats(statsData);
      setRuleProfiles(profilesData);
      setPeriods(periodsData);
      if (periodsData.length > 0) {
        const firstPeriod = periodsData[0] as AcademicPeriod;
        setSelectedPeriodId((current) => current || firstPeriod.id);
        setSelectedWeekIds((current) =>
          current.length > 0
            ? current
            : firstPeriod.weeks.map((week) => week.id),
        );
      }
      setRuleProfileId(
        profilesData.find((item: RuleProfileOption) => item.is_default)?.id ||
          profilesData[0]?.id ||
          null,
      );
    } catch {
      console.error("Failed to fetch generation data");
    } finally {
      setIsLoading(false);
    }
  }, [inheritedData]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    if (selectedGroups.length > 0 && enabledTypes.length > 0) {
      fetchSubjectSummary();
    } else {
      setSubjectSummary({});
    }
  }, [selectedGroups, enabledTypes, fetchSubjectSummary]);

  const selectedPeriod = periods.find(
    (period) => period.id === selectedPeriodId,
  );
  const hasDistributedDemand = Object.values(demandCounts).some(
    (lessonsCount) => lessonsCount > 0,
  );

  const loadDemandCounts = useCallback(async (weeks: PlanningWeek[]) => {
    if (weeks.length === 0) {
      setDemandCounts({});
      return;
    }
    const responses = await Promise.all(
      weeks.map(async (week) => {
        const response = await apiFetch(
          `${API_BASE_URL}/api/v1/planning/weeks/${week.id}/demands`,
        );
        if (!response.ok) return [week.id, 0] as const;
        const payload = (await response.json()) as {
          demands: Array<{ lessons_count: number }>;
        };
        return [
          week.id,
          payload.demands.reduce(
            (total, demand) => total + Math.max(0, demand.lessons_count),
            0,
          ),
        ] as const;
      }),
    );
    setDemandCounts(Object.fromEntries(responses));
    setSelectedWeekIds(
      responses
        .filter(([, lessonsCount]) => lessonsCount > 0)
        .map(([weekId]) => weekId),
    );
  }, []);

  useEffect(() => {
    if (selectedPeriod) void loadDemandCounts(selectedPeriod.weeks);
  }, [selectedPeriod, loadDemandCounts]);

  useEffect(() => {
    const active = batchWeeks.some(
      (item) => item.taskId && ["queued", "running"].includes(item.status),
    );
    if (!active) return;
    const interval = window.setInterval(async () => {
      const response = await apiFetch(`${API_BASE_URL}/api/v1/scheduler/tasks`);
      if (!response.ok) return;
      const tasks = (await response.json()) as Array<{
        id: number;
        status: BatchWeekState["status"];
        progress_percent: number;
        error_message: string | null;
      }>;
      const byId = new Map(tasks.map((task) => [task.id, task]));
      setBatchWeeks((current) =>
        current.map((item) => {
          const task = item.taskId ? byId.get(item.taskId) : undefined;
          return task
            ? {
                ...item,
                status: task.status,
                progress: task.progress_percent,
                error: task.error_message,
              }
            : item;
        }),
      );
    }, 3000);
    return () => window.clearInterval(interval);
  }, [batchWeeks]);

  const handleToggleGroup = (group: string) => {
    setSelectedGroups((prev) =>
      prev.includes(group) ? prev.filter((g) => g !== group) : [...prev, group],
    );
  };

  const handleToggleType = (type: string) => {
    setEnabledTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  };

  const handlePreviewGroup = async (group: string) => {
    setPreviewGroup(group);
    setIsPreviewLoading(true);
    try {
      const res = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/streams?group_name=${encodeURIComponent(group)}`,
      );
      const data = await res.json();
      // Only show active (not ignored) streams
      setPreviewStreams(
        data.filter((s: { is_ignored: boolean }) => !s.is_ignored),
      );
    } catch {
      console.error("Preview failed");
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleAddHoliday = () => {
    if (newHoliday && !holidays.includes(newHoliday)) {
      setHolidays([...holidays, newHoliday]);
      setNewHoliday("");
    }
  };

  const handleRemoveHoliday = (h: string) => {
    setHolidays(holidays.filter((item) => item !== h));
  };

  const createAcademicPeriod = async () => {
    if (!newPeriod.name || !newPeriod.starts_on || !newPeriod.ends_on) return;
    const response = await apiFetch(`${API_BASE_URL}/api/v1/planning/periods`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...newPeriod,
        period_type: "semester",
        create_weeks: true,
      }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setStatus({
        type: "error",
        msg: payload.detail || "Не удалось создать период",
      });
      return;
    }
    const period = (await response.json()) as AcademicPeriod;
    setPeriods((current) => [period, ...current]);
    setSelectedPeriodId(period.id);
    setSelectedWeekIds(period.weeks.map((week) => week.id));
    setNewPeriod({ name: "", starts_on: "", ends_on: "" });
  };

  const distributeSemesterDemands = async () => {
    if (!selectedPeriod || selectedGroups.length === 0) return;
    setIsPreparingDemands(true);
    setStatus(null);
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/v1/planning/periods/${selectedPeriod.id}/demands/distribute`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            groups: selectedGroups,
            enabled_types: enabledTypes,
            holidays,
          }),
        },
      );
      const payload = (await response.json()) as
        | SemesterDistributionResult
        | { detail?: string };
      if (!response.ok || !("weeks" in payload)) {
        throw new Error(
          "detail" in payload && payload.detail
            ? payload.detail
            : "Не удалось распределить семестровую нагрузку",
        );
      }
      setDistributionResult(payload);
      setDemandCounts(
        Object.fromEntries(
          payload.weeks.map((week) => [week.week_id, week.lessons_count]),
        ),
      );
      setSelectedWeekIds(
        payload.weeks
          .filter((week) => week.lessons_count > 0)
          .map((week) => week.week_id),
      );
      setStatus({
        type: "success",
        msg: `Распределено ${payload.distributed_lessons} пар по ${payload.weeks.filter((week) => week.lessons_count > 0).length} неделям`,
      });
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Ошибка распределения нагрузки",
      });
    } finally {
      setIsPreparingDemands(false);
    }
  };

  const getSelectedSemesterWeeks = () =>
    selectedPeriod?.weeks.filter(
      (week) => selectedWeekIds.includes(week.id) && demandCounts[week.id] > 0,
    ) || [];

  const buildCalculationPayload = (
    week?: PlanningWeek,
    semesterBatchId?: string,
  ) => ({
    groups: selectedGroups,
    holidays,
    ...(week
      ? {
          planning_week_id: week.id,
          semester_batch_id: semesterBatchId,
        }
      : { start_date: startDate, end_date: endDate }),
    settings: {
      enabled_types: enabledTypes,
      priorities: subjectPriorities,
      rule_profile_id: ruleProfileId,
      ...(selectedPeriod ? { semester_period_id: selectedPeriod.id } : {}),
      created_at: new Date().toISOString(),
    },
  });

  const handleSemesterStart = async () => {
    if (!selectedPeriod) {
      setStatus({ type: "error", msg: "Выберите учебный период" });
      return;
    }
    const weeks = getSelectedSemesterWeeks();
    if (weeks.length === 0) {
      setStatus({
        type: "error",
        msg: "Сначала распределите семестровую нагрузку",
      });
      return;
    }
    setIsGenerating(true);
    setStatus(null);
    const semesterBatchId = crypto.randomUUID();
    setBatchWeeks(
      weeks.map((week) => ({
        week,
        taskId: null,
        status: "pending",
        progress: 0,
        error: null,
      })),
    );
    const results = await Promise.all(
      weeks.map(async (week): Promise<BatchWeekState> => {
        try {
          const response = await apiFetch(
            `${API_BASE_URL}/api/v1/scheduler/generate`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(
                buildCalculationPayload(week, semesterBatchId),
              ),
            },
          );
          const payload = (await response.json()) as {
            task_id?: number;
            detail?: string;
          };
          if (!response.ok || !payload.task_id) {
            return {
              week,
              taskId: null,
              status: "failed",
              progress: 100,
              error: payload.detail || "Не удалось поставить неделю в очередь",
            };
          }
          return {
            week,
            taskId: payload.task_id,
            status: "queued",
            progress: 0,
            error: null,
          };
        } catch {
          return {
            week,
            taskId: null,
            status: "failed",
            progress: 100,
            error: "Нет связи с сервером",
          };
        }
      }),
    );
    setBatchWeeks(results);
    const queued = results.filter((item) => item.taskId).length;
    setStatus({
      type: queued > 0 ? "success" : "error",
      msg: `В очередь поставлено ${queued} из ${weeks.length} недель`,
    });
    setIsGenerating(false);
  };

  const retryBatchWeek = async (item: BatchWeekState) => {
    if (!item.taskId) return;
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/scheduler/tasks/${item.taskId}/retry`,
      { method: "POST" },
    );
    const payload = (await response.json()) as {
      task_id?: number;
      detail?: string;
    };
    if (!response.ok || !payload.task_id) {
      setStatus({ type: "error", msg: payload.detail || "Retry не выполнен" });
      return;
    }
    setBatchWeeks((current) =>
      current.map((week) =>
        week.week.id === item.week.id
          ? {
              ...week,
              taskId: payload.task_id!,
              status: "queued",
              progress: 0,
              error: null,
            }
          : week,
      ),
    );
  };

  const openWeeklyDemandEditor = async (week: PlanningWeek) => {
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/planning/weeks/${week.id}/demands`,
    );
    if (!response.ok) {
      setStatus({
        type: "error",
        msg: "Не удалось загрузить недельную нагрузку",
      });
      return;
    }
    const payload = (await response.json()) as { demands: WeeklyDemand[] };
    setWeeklyDemands(payload.demands);
    setDemandSearch("");
    setEditingWeek(week);
  };

  const saveWeeklyDemands = async () => {
    if (!editingWeek) return;
    setIsSavingDemands(true);
    const response = await apiFetch(
      `${API_BASE_URL}/api/v1/planning/weeks/${editingWeek.id}/demands`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          demands: weeklyDemands.map((item) => ({
            stream_id: item.stream_id,
            lessons_count: item.lessons_count,
            priority: item.priority,
          })),
        }),
      },
    );
    setIsSavingDemands(false);
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setStatus({
        type: "error",
        msg: payload.detail || "Нагрузка не сохранена",
      });
      return;
    }
    if (selectedPeriod) await loadDemandCounts(selectedPeriod.weeks);
    setEditingWeek(null);
    setStatus({ type: "success", msg: "Недельная нагрузка сохранена" });
  };

  const handleStartGeneration = async () => {
    if (generationMode === "semester") {
      await handleSemesterStart();
      return;
    }
    const horizonDays =
      Math.floor(
        (new Date(endDate).getTime() - new Date(startDate).getTime()) /
          86_400_000,
      ) + 1;
    if (horizonDays > 14) {
      setStatus({
        type: "error",
        msg: "Один расчет ограничен 14 днями. Создайте отдельный расчет для каждой учебной недели.",
      });
      return;
    }
    setIsGenerating(true);
    setStatus(null);
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/v1/scheduler/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildCalculationPayload()),
      });

      if (res.ok) {
        setStatus({
          type: "success",
          msg: "Задача на генерацию успешно отправлена!",
        });
      } else {
        const payload = (await res.json()) as { detail?: string };
        setStatus({
          type: "error",
          msg: payload.detail || "Ошибка при отправке задачи.",
        });
      }
    } catch {
      setStatus({ type: "error", msg: "Не удалось связаться с сервером." });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExport = () => {
    openDownload(`${API_BASE_URL}/api/v1/scheduler/export`);
  };

  const filteredGroups = groups.filter((g) =>
    g.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Apply type filter to preview
  const displayPreviewStreams = previewStreams.filter((s) =>
    enabledTypes.includes(s.stream_type),
  );

  if (isLoading)
    return (
      <div
        style={{
          padding: "5rem",
          textAlign: "center",
          color: "var(--text-secondary)",
        }}
      >
        Загрузка параметров генерации...
      </div>
    );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
        paddingBottom: "2rem",
      }}
      className="enterprise-page generation-workspace animate-fade-in"
    >
      <header className="workspace-header calc-header">
        <div>
          <h2
            className="calc-header__title"
            style={{
              fontSize: "2rem",
              fontWeight: 900,
              color: "var(--text-primary)",
              letterSpacing: "-0.02em",
            }}
          >
            Генератор расписания
          </h2>
          <p
            style={{
              color: "var(--text-secondary)",
              marginTop: "0.25rem",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            Настройка фильтров и запуск алгоритма планирования.
          </p>
        </div>
        <div
          className="calc-summary"
          style={{ display: "flex", gap: "0.75rem" }}
        >
          <div
            className="calc-summary__item"
            style={{
              backgroundColor: "white",
              border: "1px solid var(--border-light)",
              borderRadius: "12px",
              padding: "0.5rem 1rem",
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              boxShadow: "var(--shadow-subtle)",
            }}
          >
            <span
              style={{
                fontSize: "0.625rem",
                fontWeight: 800,
                color: "var(--text-tertiary)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Групп
            </span>
            <span
              style={{
                fontSize: "1.125rem",
                fontWeight: 900,
                color: "var(--brand)",
              }}
            >
              {selectedGroups.length}
            </span>
          </div>
          <div
            className="calc-summary__item"
            style={{
              backgroundColor: "white",
              border: "1px solid var(--border-light)",
              borderRadius: "12px",
              padding: "0.5rem 1rem",
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              boxShadow: "var(--shadow-subtle)",
            }}
          >
            <span
              style={{
                fontSize: "0.625rem",
                fontWeight: 800,
                color: "var(--text-tertiary)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Типов
            </span>
            <span
              style={{
                fontSize: "1.125rem",
                fontWeight: 900,
                color: "#f59e0b",
              }}
            >
              {enabledTypes.length}
            </span>
          </div>
          <button
            onClick={handleExport}
            className="btn-secondary calc-summary__export"
            style={{
              backgroundColor: "white",
              color: "var(--text-primary)",
              padding: "0.5rem 1rem",
              borderRadius: "12px",
              fontWeight: 800,
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              border: "1px solid var(--border-light)",
              cursor: "pointer",
              transition: "all 0.2s",
              boxShadow: "var(--shadow-sm)",
              fontSize: "0.875rem",
            }}
          >
            <Download size={18} />
            Excel
          </button>
        </div>
      </header>

      <section className="calc-mode-switch">
        <button
          onClick={() => setGenerationMode("week")}
          className={`calc-mode-switch__button ${
            generationMode === "week" ? "calc-mode-switch__button--active" : ""
          }`}
        >
          <CalendarRange size={19} /> Одна неделя
        </button>
        <button
          onClick={() => setGenerationMode("semester")}
          className={`calc-mode-switch__button ${
            generationMode === "semester"
              ? "calc-mode-switch__button--active"
              : ""
          }`}
        >
          <Layers3 size={19} /> Весь семестр по неделям
        </button>
      </section>

      <section className="calc-rule-profile">
        <div>
          <h2 className="text-sm font-extrabold text-text-primary">
            Профиль правил
          </h2>
          <p className="mt-1 text-xs text-text-secondary">
            Определяет жесткие ограничения и веса критериев качества.
          </p>
        </div>
        <select
          value={ruleProfileId ?? ""}
          onChange={(event) => setRuleProfileId(Number(event.target.value))}
          className="calc-rule-profile__select"
        >
          {ruleProfiles.map((profile) => (
            <option key={profile.id} value={profile.id}>
              {profile.name}
              {profile.is_default ? " (по умолчанию)" : ""}
            </option>
          ))}
        </select>
      </section>

      <div
        className="calc-layout"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, 1fr)",
          gap: "2rem",
        }}
      >
        {/* Left Column: Group Selection */}
        <div className="calc-sidebar" style={{ gridColumn: "span 4" }}>
          <div
            className="calc-panel calc-group-panel"
            style={{
              backgroundColor: "white",
              borderRadius: "20px",
              border: "1px solid var(--border-light)",
              boxShadow: "var(--shadow-md)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
              height: "600px",
            }}
          >
            <div
              style={{
                padding: "1.25rem",
                borderBottom: "1px solid var(--border-light)",
                backgroundColor: "#fafafa",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1rem",
                }}
              >
                <h3
                  style={{
                    fontWeight: 800,
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontSize: "0.9375rem",
                  }}
                >
                  <Users size={18} style={{ color: "var(--brand)" }} /> Группы
                </h3>
                <button
                  onClick={() =>
                    setSelectedGroups(
                      selectedGroups.length === groups.length
                        ? []
                        : [...groups],
                    )
                  }
                  style={{
                    fontSize: "0.625rem",
                    fontWeight: 900,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--brand)",
                    cursor: "pointer",
                    border: "none",
                    background: "none",
                  }}
                >
                  {selectedGroups.length === groups.length ? "Сбросить" : "Все"}
                </button>
              </div>
              <div style={{ position: "relative" }}>
                <Search
                  size={14}
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
                    backgroundColor: "white",
                    border: "1px solid var(--border-light)",
                    borderRadius: "10px",
                    padding: "0.625rem 0.75rem 0.625rem 2.25rem",
                    fontSize: "0.875rem",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
              {filteredGroups.map((group) => (
                <div
                  key={group}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                    padding: "0.75rem",
                    borderRadius: "10px",
                    cursor: "pointer",
                    backgroundColor: selectedGroups.includes(group)
                      ? "rgba(79, 70, 229, 0.05)"
                      : "transparent",
                    transition: "all 0.2s",
                  }}
                  onClick={() => handleToggleGroup(group)}
                  className="group-item"
                >
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "6px",
                      border: `2px solid ${selectedGroups.includes(group) ? "var(--brand)" : "#d1d5db"}`,
                      backgroundColor: selectedGroups.includes(group)
                        ? "var(--brand)"
                        : "white",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {selectedGroups.includes(group) && (
                      <CheckCircle2 size={12} color="white" />
                    )}
                  </div>
                  <span
                    style={{
                      flex: 1,
                      fontSize: "0.875rem",
                      fontWeight: 700,
                      color: selectedGroups.includes(group)
                        ? "var(--brand)"
                        : "var(--text-primary)",
                    }}
                  >
                    {group}
                  </span>
                  <button
                    aria-label={`Просмотреть состав группы ${group}`}
                    title={`Просмотреть состав группы ${group}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePreviewGroup(group);
                    }}
                    style={{
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                      padding: "0.25rem",
                      color: "var(--text-tertiary)",
                    }}
                    className="preview-btn"
                  >
                    <Eye size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Filters & Preview */}
        <div
          className="calc-main"
          style={{
            gridColumn: "span 8",
            display: "flex",
            flexDirection: "column",
            gap: "2rem",
          }}
        >
          {/* Global Type Filter */}
          <div
            className="calc-panel calc-types-panel"
            style={{
              backgroundColor: "white",
              borderRadius: "20px",
              border: "1px solid var(--border-light)",
              boxShadow: "var(--shadow-md)",
              padding: "1.5rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                marginBottom: "1.5rem",
              }}
            >
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(245, 158, 11, 0.1)",
                  color: "#f59e0b",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Settings2 size={20} />
              </div>
              <div>
                <h3 style={{ fontWeight: 800 }}>Типы занятий для генерации</h3>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    fontWeight: 600,
                  }}
                >
                  Выберите, какие типы пар нужно включить в этот расчет
                </p>
              </div>
            </div>

            <div
              className="calc-type-list"
              style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}
            >
              {ALL_TYPES.map((type) => (
                <button
                  key={type}
                  onClick={() => handleToggleType(type)}
                  className={`calc-type-button ${enabledTypes.includes(type) ? "calc-type-button--active" : ""}`}
                  style={{
                    padding: "0.625rem 1rem",
                    borderRadius: "12px",
                    border: `2px solid ${enabledTypes.includes(type) ? "#f59e0b" : "var(--border-light)"}`,
                    backgroundColor: enabledTypes.includes(type)
                      ? "rgba(245, 158, 11, 0.05)"
                      : "white",
                    color: enabledTypes.includes(type)
                      ? "#b45309"
                      : "var(--text-secondary)",
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* Subject Priorities Grouped by Direction */}
          <div
            className="calc-panel calc-priorities-panel"
            style={{
              backgroundColor: "white",
              borderRadius: "20px",
              border: "1px solid var(--border-light)",
              boxShadow: "var(--shadow-md)",
              padding: "1.5rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                marginBottom: "1.5rem",
              }}
            >
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(79, 70, 229, 0.1)",
                  color: "var(--brand)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Zap size={20} />
              </div>
              <div>
                <h3 style={{ fontWeight: 800 }}>Приоритет предметов</h3>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    fontWeight: 600,
                  }}
                >
                  Настройте желаемое время для каждого предмета (
                  {Object.values(subjectSummary).flat().length} дисциплин)
                </p>
              </div>
            </div>

            {isSummaryLoading ? (
              <div
                style={{
                  padding: "2rem",
                  textAlign: "center",
                  color: "var(--text-tertiary)",
                }}
              >
                Загрузка списка предметов...
              </div>
            ) : Object.keys(subjectSummary).length > 0 ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "1rem",
                  maxHeight: "500px",
                  overflowY: "auto",
                  paddingRight: "0.5rem",
                }}
              >
                {Object.entries(subjectSummary).map(([direction, subjects]) => (
                  <div
                    key={direction}
                    style={{
                      border: "1px solid var(--border-light)",
                      borderRadius: "12px",
                      overflow: "hidden",
                      flexShrink: 0,
                    }}
                  >
                    <div
                      onClick={() =>
                        setExpandedDirections((prev) =>
                          prev.includes(direction)
                            ? prev.filter((d) => d !== direction)
                            : [...prev, direction],
                        )
                      }
                      style={{
                        padding: "0.75rem 1rem",
                        backgroundColor: "#fafafa",
                        cursor: "pointer",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 900,
                          color: "var(--text-primary)",
                        }}
                      >
                        {direction}
                      </span>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-tertiary)",
                        }}
                      >
                        {subjects.length} предметов
                      </span>
                    </div>
                    {expandedDirections.includes(direction) && (
                      <div
                        style={{
                          padding: "0.75rem",
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.75rem",
                        }}
                      >
                        {Array.isArray(subjects) &&
                          subjects.map((subj) => {
                            const currentPref =
                              subjectPriorities[subj] || "day";
                            return (
                              <div
                                key={subj}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  gap: "1rem",
                                  padding: "0.5rem",
                                  borderBottom: "1px solid #f3f4f6",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    fontWeight: 700,
                                    color: "var(--text-primary)",
                                    flex: 1,
                                    whiteSpace: "nowrap",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                  }}
                                  title={subj}
                                >
                                  {subj}
                                </span>

                                <div
                                  style={{
                                    display: "flex",
                                    backgroundColor: "#f3f4f6",
                                    padding: "0.25rem",
                                    borderRadius: "8px",
                                    gap: "0.125rem",
                                  }}
                                >
                                  {[
                                    {
                                      id: "morning",
                                      label: "Утро",
                                      color: "var(--brand)",
                                    },
                                    {
                                      id: "day",
                                      label: "День",
                                      color: "var(--text-secondary)",
                                    },
                                    {
                                      id: "evening",
                                      label: "Вечер",
                                      color: "#f59e0b",
                                    },
                                  ].map((opt) => (
                                    <button
                                      key={opt.id}
                                      onClick={() =>
                                        setSubjectPriorities((prev) => ({
                                          ...prev,
                                          [subj]: opt.id,
                                        }))
                                      }
                                      style={{
                                        padding: "0.25rem 0.625rem",
                                        borderRadius: "6px",
                                        fontSize: "0.625rem",
                                        fontWeight: 800,
                                        border: "none",
                                        cursor: "pointer",
                                        backgroundColor:
                                          currentPref === opt.id
                                            ? "white"
                                            : "transparent",
                                        color:
                                          currentPref === opt.id
                                            ? opt.color
                                            : "var(--text-tertiary)",
                                        boxShadow:
                                          currentPref === opt.id
                                            ? "0 2px 4px rgba(0,0,0,0.05)"
                                            : "none",
                                        transition: "all 0.15s",
                                      }}
                                    >
                                      {opt.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "2rem",
                  textAlign: "center",
                  color: "var(--text-tertiary)",
                  fontSize: "0.875rem",
                }}
              >
                Выберите группы, чтобы увидеть список предметов
              </div>
            )}
          </div>

          {/* Preview Section */}
          <div
            className="calc-panel calc-preview-panel"
            style={{
              backgroundColor: "white",
              borderRadius: "20px",
              border: "1px solid var(--border-light)",
              boxShadow: "var(--shadow-md)",
              overflow: "hidden",
              opacity: previewGroup ? 1 : 0.6,
            }}
          >
            <div
              style={{
                padding: "1.5rem",
                borderBottom: "1px solid var(--border-light)",
                backgroundColor: "#fafafa",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div
                style={{ display: "flex", alignItems: "center", gap: "1rem" }}
              >
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "12px",
                    backgroundColor: "white",
                    border: "1px solid var(--border-light)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "var(--shadow-subtle)",
                  }}
                >
                  <Filter size={24} style={{ color: "var(--brand)" }} />
                </div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: "1.125rem" }}>
                    План: {previewGroup || "—"}
                  </h3>
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      fontWeight: 600,
                    }}
                  >
                    {displayPreviewStreams.length} пар с учетом фильтров типов
                  </p>
                </div>
              </div>
              {previewGroup && (
                <button
                  onClick={() => setPreviewGroup(null)}
                  style={{
                    padding: "0.5rem",
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                    color: "var(--text-tertiary)",
                  }}
                >
                  <X size={20} />
                </button>
              )}
            </div>

            <div
              style={{
                minHeight: "300px",
                maxHeight: "300px",
                overflowY: "auto",
              }}
            >
              {isPreviewLoading ? (
                <div
                  style={{
                    padding: "5rem",
                    textAlign: "center",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "1rem",
                  }}
                >
                  <Clock
                    size={32}
                    style={{
                      color: "var(--brand)",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                  <span
                    style={{ fontWeight: 700, color: "var(--text-secondary)" }}
                  >
                    Загрузка...
                  </span>
                </div>
              ) : displayPreviewStreams.length > 0 ? (
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    textAlign: "left",
                  }}
                >
                  <thead
                    style={{
                      position: "sticky",
                      top: 0,
                      backgroundColor: "white",
                      boxShadow: "0 1px 0 var(--border-light)",
                      zIndex: 10,
                    }}
                  >
                    <tr>
                      <th
                        style={{
                          padding: "1rem 1.5rem",
                          fontSize: "0.625rem",
                          fontWeight: 900,
                          textTransform: "uppercase",
                          color: "var(--text-tertiary)",
                        }}
                      >
                        Дисциплина
                      </th>
                      <th
                        style={{
                          padding: "1rem 1.5rem",
                          fontSize: "0.625rem",
                          fontWeight: 900,
                          textTransform: "uppercase",
                          color: "var(--text-tertiary)",
                        }}
                      >
                        Тип
                      </th>
                      <th
                        style={{
                          padding: "1rem 1.5rem",
                          fontSize: "0.625rem",
                          fontWeight: 900,
                          textTransform: "uppercase",
                          color: "var(--text-tertiary)",
                        }}
                      >
                        Преподаватель
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayPreviewStreams.map((s) => (
                      <tr
                        key={s.id}
                        style={{ borderTop: "1px solid var(--border-light)" }}
                      >
                        <td
                          style={{
                            padding: "1rem 1.5rem",
                            fontWeight: 700,
                            fontSize: "0.875rem",
                          }}
                        >
                          {s.event_name}
                        </td>
                        <td style={{ padding: "1rem 1.5rem" }}>
                          <span
                            style={{
                              fontSize: "0.625rem",
                              fontWeight: 900,
                              padding: "0.25rem 0.5rem",
                              borderRadius: "4px",
                              backgroundColor: "#f3f4f6",
                              color: "var(--text-secondary)",
                              textTransform: "uppercase",
                            }}
                          >
                            {s.stream_type}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: "1rem 1.5rem",
                            fontSize: "0.875rem",
                            color: "var(--text-secondary)",
                            fontWeight: 600,
                          }}
                        >
                          {s.teacher || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div
                  style={{
                    padding: "5rem",
                    textAlign: "center",
                    color: "var(--text-tertiary)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "1rem",
                  }}
                >
                  <Info size={48} style={{ opacity: 0.1 }} />
                  <span style={{ fontWeight: 700 }}>
                    {previewGroup
                      ? "Нет пар, соответствующих фильтрам"
                      : "Выберите группу для проверки состава пар"}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div
            className="calc-bottom-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "2rem",
            }}
          >
            {/* Semester Dates */}
            <div
              className="calc-panel calc-period-panel"
              style={{
                backgroundColor: "white",
                borderRadius: "20px",
                border: "1px solid var(--border-light)",
                boxShadow: "var(--shadow-md)",
                padding: "1.5rem",
                gridColumn:
                  generationMode === "semester" ? "1 / -1" : undefined,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginBottom: "1.5rem",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "10px",
                    backgroundColor: "rgba(79, 70, 229, 0.1)",
                    color: "var(--brand)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Clock size={20} />
                </div>
                <h3 style={{ fontWeight: 800 }}>
                  {generationMode === "week"
                    ? "Учебная неделя"
                    : "Учебный период"}
                </h3>
              </div>

              {generationMode === "week" ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "1rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.5rem",
                    }}
                  >
                    <label
                      style={{
                        fontSize: "0.625rem",
                        fontWeight: 800,
                        color: "var(--text-tertiary)",
                        textTransform: "uppercase",
                      }}
                    >
                      Начало
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      style={{
                        backgroundColor: "#f9fafb",
                        border: "1px solid var(--border-light)",
                        borderRadius: "10px",
                        padding: "0.625rem 0.75rem",
                        fontSize: "0.875rem",
                        outline: "none",
                        fontWeight: 600,
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.5rem",
                    }}
                  >
                    <label
                      style={{
                        fontSize: "0.625rem",
                        fontWeight: 800,
                        color: "var(--text-tertiary)",
                        textTransform: "uppercase",
                      }}
                    >
                      Конец
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      style={{
                        backgroundColor: "#f9fafb",
                        border: "1px solid var(--border-light)",
                        borderRadius: "10px",
                        padding: "0.625rem 0.75rem",
                        fontSize: "0.875rem",
                        outline: "none",
                        fontWeight: 600,
                      }}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {periods.length > 0 && (
                    <select
                      value={selectedPeriodId ?? ""}
                      onChange={(event) => {
                        const periodId = Number(event.target.value);
                        const period = periods.find(
                          (item) => item.id === periodId,
                        );
                        setSelectedPeriodId(periodId);
                        setSelectedWeekIds(
                          period?.weeks.map((week) => week.id) || [],
                        );
                        setBatchWeeks([]);
                      }}
                      className="w-full rounded-xl border border-border-light bg-white px-3 py-2.5 text-sm font-bold text-text-primary outline-none focus:border-brand"
                    >
                      {periods.map((period) => (
                        <option key={period.id} value={period.id}>
                          {period.name} · {period.starts_on} — {period.ends_on}
                        </option>
                      ))}
                    </select>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      value={newPeriod.name}
                      onChange={(event) =>
                        setNewPeriod({ ...newPeriod, name: event.target.value })
                      }
                      placeholder="Название нового семестра"
                      className="col-span-2 rounded-xl border border-border-light px-3 py-2 text-sm outline-none focus:border-brand"
                    />
                    <input
                      type="date"
                      value={newPeriod.starts_on}
                      onChange={(event) =>
                        setNewPeriod({
                          ...newPeriod,
                          starts_on: event.target.value,
                        })
                      }
                      className="rounded-xl border border-border-light px-3 py-2 text-sm outline-none focus:border-brand"
                    />
                    <input
                      type="date"
                      value={newPeriod.ends_on}
                      onChange={(event) =>
                        setNewPeriod({
                          ...newPeriod,
                          ends_on: event.target.value,
                        })
                      }
                      className="rounded-xl border border-border-light px-3 py-2 text-sm outline-none focus:border-brand"
                    />
                  </div>
                  <button
                    onClick={() => void createAcademicPeriod()}
                    disabled={
                      !newPeriod.name ||
                      !newPeriod.starts_on ||
                      !newPeriod.ends_on
                    }
                    className="w-full rounded-xl border border-brand/20 bg-brand/5 px-3 py-2 text-xs font-extrabold text-brand disabled:opacity-40"
                  >
                    Создать период и недели
                  </button>
                </div>
              )}
            </div>

            {generationMode === "semester" && selectedPeriod && (
              <div className="semester-command-center col-span-2 rounded-[20px] border border-border-light bg-white p-6 shadow-md">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="flex items-center gap-2 font-extrabold text-text-primary">
                      <Layers3 size={19} className="text-brand" /> Недельные
                      расчеты
                    </h3>
                    <p className="mt-1 text-xs font-semibold text-text-secondary">
                      В очереди одновременно выполняются не более двух
                      solver-задач.
                    </p>
                  </div>
                </div>

                <div className="semester-command-center__steps mb-5 grid gap-3 md:grid-cols-3">
                  <div
                    className={`rounded-xl border p-4 ${
                      selectedGroups.length > 0
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-amber-200 bg-amber-50"
                    }`}
                  >
                    <div className="text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                      Шаг 1 · Группы
                    </div>
                    <div className="mt-1 text-sm font-extrabold text-text-primary">
                      {selectedGroups.length > 0
                        ? `Выбрано: ${selectedGroups.length}`
                        : "Группы не выбраны"}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border-light bg-bg-base p-4">
                    <div className="text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                      Шаг 2 · Нагрузка
                    </div>
                    <div className="mt-1 text-sm font-extrabold text-text-primary">
                      {hasDistributedDemand
                        ? "Распределена"
                        : "Нужно распределить"}
                    </div>
                  </div>
                  <div className="rounded-xl border border-border-light bg-bg-base p-4">
                    <div className="text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                      Шаг 3 · Запуск
                    </div>
                    <div className="mt-1 text-sm font-extrabold text-text-primary">
                      {selectedWeekIds.length > 0
                        ? `${selectedWeekIds.length} недель готово`
                        : "Ожидает распределения"}
                    </div>
                  </div>
                </div>

                <div className="semester-command-center__action mb-5 rounded-2xl border-2 border-brand/20 bg-brand/5 p-5">
                  {selectedGroups.length === 0 && (
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
                      <div>
                        <div className="text-sm font-extrabold text-amber-900">
                          Сначала выберите учебные группы
                        </div>
                        <div className="mt-1 text-xs font-semibold text-amber-700">
                          Можно выбрать нужные группы выше или сразу выбрать
                          все.
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedGroups([...groups])}
                        className="rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-extrabold text-white shadow-sm hover:bg-amber-600"
                      >
                        Выбрать все группы
                      </button>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => void distributeSemesterDemands()}
                    disabled={
                      isPreparingDemands ||
                      selectedGroups.length === 0 ||
                      enabledTypes.length === 0
                    }
                    className="semester-command-center__distribute flex w-full items-center justify-center gap-3 rounded-xl bg-brand px-5 py-4 text-sm font-black text-white shadow-lg shadow-brand/20 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
                  >
                    <RefreshCcw
                      size={18}
                      className={isPreparingDemands ? "animate-spin" : ""}
                    />
                    {isPreparingDemands
                      ? "Распределяем нагрузку..."
                      : hasDistributedDemand
                        ? "Перераспределить нагрузку по семестру"
                        : "Распределить нагрузку по семестру"}
                  </button>
                  <p className="mt-3 text-center text-xs font-semibold text-text-secondary">
                    Общая нагрузка будет разделена между неделями с учетом
                    доступности преподавателей, сроков дисциплин и праздников.
                  </p>
                </div>

                {distributionResult && (
                  <div className="semester-command-center__result mb-5 grid gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-bold text-emerald-900 sm:grid-cols-3">
                    <div>План: {distributionResult.planned_lessons} пар</div>
                    <div>
                      Уже опубликовано: {distributionResult.published_lessons}
                    </div>
                    <div>
                      Распределено: {distributionResult.distributed_lessons}
                    </div>
                  </div>
                )}

                {batchWeeks.length > 0 && (
                  <div className="mb-5 rounded-xl border border-brand/10 bg-brand/5 p-4">
                    <div className="mb-2 flex justify-between text-xs font-extrabold text-brand">
                      <span>Прогресс семестра</span>
                      <span>
                        {
                          batchWeeks.filter((item) =>
                            [
                              "success",
                              "partial",
                              "failed",
                              "canceled",
                            ].includes(item.status),
                          ).length
                        }
                        /{batchWeeks.length} недель
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-white">
                      <div
                        className="h-full rounded-full bg-brand transition-all"
                        style={{
                          width: `${batchWeeks.length ? batchWeeks.reduce((sum, item) => sum + item.progress, 0) / batchWeeks.length : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                {hasDistributedDemand ? (
                  <>
                    <div className="mb-3 flex justify-end">
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedWeekIds(() => {
                            const readyWeekIds = selectedPeriod.weeks
                              .filter((week) => demandCounts[week.id] > 0)
                              .map((week) => week.id);
                            return selectedWeekIds.length ===
                              readyWeekIds.length
                              ? []
                              : readyWeekIds;
                          })
                        }
                        className="rounded-xl border border-border-light bg-white px-3 py-2 text-xs font-extrabold text-text-secondary hover:text-brand"
                      >
                        {selectedWeekIds.length ===
                        selectedPeriod.weeks.filter(
                          (week) => demandCounts[week.id] > 0,
                        ).length
                          ? "Снять выбор недель"
                          : "Выбрать все недели"}
                      </button>
                    </div>
                    <div className="grid max-h-80 gap-2 overflow-y-auto md:grid-cols-2">
                      {selectedPeriod.weeks.map((week) => {
                        const batch = batchWeeks.find(
                          (item) => item.week.id === week.id,
                        );
                        const ready = Boolean(demandCounts[week.id]);
                        return (
                          <label
                            key={week.id}
                            className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition-all ${
                              selectedWeekIds.includes(week.id)
                                ? "border-brand/30 bg-brand/5"
                                : "border-border-light bg-white opacity-60"
                            }`}
                          >
                            <input
                              type="checkbox"
                              disabled={!ready}
                              checked={selectedWeekIds.includes(week.id)}
                              onChange={() =>
                                setSelectedWeekIds((current) =>
                                  current.includes(week.id)
                                    ? current.filter((id) => id !== week.id)
                                    : [...current, week.id],
                                )
                              }
                              className="h-4 w-4 accent-brand disabled:opacity-30"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="text-xs font-extrabold text-text-primary">
                                Неделя {week.sequence_number}
                              </div>
                              <div className="mt-0.5 text-[11px] text-text-secondary">
                                {week.starts_on} — {week.ends_on}
                              </div>
                            </div>
                            <div className="text-right">
                              <div
                                className={`text-[10px] font-extrabold ${
                                  ready ? "text-emerald-600" : "text-amber-600"
                                }`}
                              >
                                {ready
                                  ? `${demandCounts[week.id]} пар`
                                  : "0 пар после распределения"}
                              </div>
                              {ready && !batch && (
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.preventDefault();
                                    void openWeeklyDemandEditor(week);
                                  }}
                                  className="mt-1 text-[10px] font-extrabold text-brand hover:underline"
                                >
                                  Настроить
                                </button>
                              )}
                              {batch && (
                                <div className="mt-1 flex items-center justify-end gap-1 text-[10px] font-bold text-text-secondary">
                                  {batch.status} · {batch.progress}%
                                  {batch.status === "failed" &&
                                    batch.taskId && (
                                      <button
                                        type="button"
                                        title={batch.error || "Повторить"}
                                        onClick={(event) => {
                                          event.preventDefault();
                                          void retryBatchWeek(batch);
                                        }}
                                        className="ml-1 rounded p-1 text-red-500 hover:bg-red-50"
                                      >
                                        <RotateCcw size={11} />
                                      </button>
                                    )}
                                </div>
                              )}
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border-light bg-bg-base px-6 py-10 text-center">
                    <Layers3
                      size={36}
                      className="mx-auto mb-3 text-text-tertiary opacity-50"
                    />
                    <div className="font-extrabold text-text-primary">
                      Недельный план появится после распределения
                    </div>
                    <div className="mt-1 text-xs font-semibold text-text-secondary">
                      Не нужно настраивать {selectedPeriod.weeks.length} недель
                      вручную.
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Holidays */}
            <div
              className="calc-panel calc-holidays-panel"
              style={{
                backgroundColor: "white",
                borderRadius: "20px",
                border: "1px solid var(--border-light)",
                boxShadow: "var(--shadow-md)",
                padding: "1.5rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginBottom: "1.5rem",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "10px",
                    backgroundColor: "rgba(249, 115, 22, 0.1)",
                    color: "#f97316",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Calendar size={20} />
                </div>
                <h3 style={{ fontWeight: 800 }}>Праздники</h3>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  marginBottom: "1.5rem",
                }}
              >
                <input
                  type="date"
                  value={newHoliday}
                  onChange={(e) => setNewHoliday(e.target.value)}
                  style={{
                    flex: 1,
                    backgroundColor: "#f9fafb",
                    border: "1px solid var(--border-light)",
                    borderRadius: "10px",
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.875rem",
                    outline: "none",
                  }}
                />
                <button
                  onClick={handleAddHoliday}
                  style={{
                    backgroundColor: "#f97316",
                    color: "white",
                    borderRadius: "10px",
                    padding: "0 1rem",
                    fontWeight: 800,
                    fontSize: "0.75rem",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  +
                </button>
              </div>

              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                  maxHeight: "100px",
                  overflowY: "auto",
                }}
              >
                {holidays.map((h) => (
                  <div
                    key={h}
                    style={{
                      backgroundColor: "rgba(249, 115, 22, 0.1)",
                      color: "#ea580c",
                      padding: "0.375rem 0.75rem",
                      borderRadius: "8px",
                      fontSize: "0.75rem",
                      fontWeight: 800,
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      border: "1px solid rgba(249, 115, 22, 0.2)",
                    }}
                  >
                    {h}
                    <button
                      onClick={() => handleRemoveHoliday(h)}
                      style={{
                        border: "none",
                        background: "none",
                        color: "#f97316",
                        cursor: "pointer",
                      }}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Card */}
            <div
              className="calc-action-panel"
              style={{
                backgroundColor: "var(--text-primary)",
                borderRadius: "20px",
                boxShadow: "0 20px 40px rgba(0,0,0,0.2)",
                padding: "2rem",
                color: "white",
                position: "relative",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div style={{ position: "relative", zIndex: 1 }}>
                <h3
                  style={{
                    fontSize: "1.25rem",
                    fontWeight: 900,
                    marginBottom: "0.5rem",
                  }}
                >
                  {generationMode === "semester"
                    ? "Запуск семестра"
                    : "Запуск недели"}
                </h3>
                <p
                  style={{
                    fontSize: "0.75rem",
                    opacity: 0.6,
                    fontWeight: 500,
                    marginBottom: "2rem",
                    lineHeight: 1.5,
                  }}
                >
                  {generationMode === "semester"
                    ? `${selectedWeekIds.length} недель для ${selectedGroups.length} групп будут рассчитаны отдельными безопасными задачами.`
                    : `Расчет ${selectedGroups.length} групп с учетом выбранных типов пар.`}
                </p>

                <button
                  disabled={
                    selectedGroups.length === 0 ||
                    isGenerating ||
                    enabledTypes.length === 0 ||
                    (generationMode === "semester" &&
                      (!selectedPeriod || selectedWeekIds.length === 0))
                  }
                  onClick={handleStartGeneration}
                  style={{
                    width: "100%",
                    padding: "1rem",
                    borderRadius: "12px",
                    border: "none",
                    fontWeight: 900,
                    fontSize: "0.875rem",
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "0.75rem",
                    cursor:
                      selectedGroups.length === 0 ||
                      isGenerating ||
                      enabledTypes.length === 0 ||
                      (generationMode === "semester" &&
                        (!selectedPeriod || selectedWeekIds.length === 0))
                        ? "not-allowed"
                        : "pointer",
                    backgroundColor:
                      selectedGroups.length === 0 ||
                      isGenerating ||
                      enabledTypes.length === 0 ||
                      (generationMode === "semester" &&
                        (!selectedPeriod || selectedWeekIds.length === 0))
                        ? "rgba(255,255,255,0.1)"
                        : "var(--brand)",
                    color:
                      selectedGroups.length === 0 ||
                      isGenerating ||
                      enabledTypes.length === 0 ||
                      (generationMode === "semester" &&
                        (!selectedPeriod || selectedWeekIds.length === 0))
                        ? "rgba(255,255,255,0.3)"
                        : "white",
                    boxShadow: isGenerating
                      ? "none"
                      : "0 8px 24px rgba(79, 70, 229, 0.4)",
                    transition: "all 0.2s",
                  }}
                >
                  {isGenerating ? (
                    <Clock
                      size={18}
                      style={{ animation: "spin 1s linear infinite" }}
                    />
                  ) : (
                    <Zap size={18} />
                  )}
                  {isGenerating
                    ? "Постановка в очередь..."
                    : generationMode === "semester"
                      ? "Запустить выбранные недели"
                      : "Начать расчет недели"}
                </button>

                {status && (
                  <div
                    style={{
                      marginTop: "1rem",
                      padding: "0.75rem",
                      borderRadius: "10px",
                      fontSize: "0.75rem",
                      fontWeight: 800,
                      backgroundColor:
                        status.type === "success"
                          ? "rgba(34, 197, 94, 0.2)"
                          : "rgba(239, 68, 68, 0.2)",
                      color: status.type === "success" ? "#4ade80" : "#f87171",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    {status.type === "success" ? (
                      <CheckCircle2 size={14} />
                    ) : (
                      <AlertCircle size={14} />
                    )}
                    {status.msg}
                  </div>
                )}
              </div>
              <Zap
                size={120}
                style={{
                  position: "absolute",
                  right: "-20px",
                  bottom: "-20px",
                  opacity: 0.05,
                  transform: "rotate(15deg)",
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {editingWeek && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-6 backdrop-blur-sm">
          <div className="flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-light px-6 py-5">
              <div>
                <h2 className="text-lg font-black text-text-primary">
                  Нагрузка недели {editingWeek.sequence_number}
                </h2>
                <p className="mt-1 text-xs font-semibold text-text-secondary">
                  {editingWeek.starts_on} — {editingWeek.ends_on} · нулевое
                  значение исключает поток из этой недели
                </p>
              </div>
              <button
                onClick={() => setEditingWeek(null)}
                className="rounded-xl p-2 text-text-secondary hover:bg-bg-base hover:text-text-primary"
              >
                <X size={20} />
              </button>
            </div>
            <div className="border-b border-border-light px-6 py-4">
              <div className="relative">
                <Search
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
                />
                <input
                  value={demandSearch}
                  onChange={(event) => setDemandSearch(event.target.value)}
                  placeholder="Поиск дисциплины или преподавателя"
                  className="w-full rounded-xl border border-border-light py-2.5 pl-9 pr-3 text-sm outline-none focus:border-brand"
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-3">
              <table className="w-full border-collapse text-left">
                <thead className="sticky top-0 bg-white text-[10px] font-black uppercase text-text-tertiary">
                  <tr>
                    <th className="border-b border-border-light py-3 pr-4">
                      Поток
                    </th>
                    <th className="border-b border-border-light px-3 py-3">
                      Тип
                    </th>
                    <th className="w-32 border-b border-border-light px-3 py-3">
                      Занятий
                    </th>
                    <th className="w-32 border-b border-border-light pl-3 py-3">
                      Приоритет
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {weeklyDemands
                    .filter((item) => {
                      const query = demandSearch.toLowerCase();
                      return (
                        !query ||
                        (item.event_name || "").toLowerCase().includes(query) ||
                        (item.teacher_name || "").toLowerCase().includes(query)
                      );
                    })
                    .map((item) => (
                      <tr
                        key={item.stream_id}
                        className="border-b border-border-light/70"
                      >
                        <td className="py-3 pr-4">
                          <div className="text-sm font-extrabold text-text-primary">
                            {item.event_name || `Поток ${item.stream_id}`}
                          </div>
                          <div className="mt-0.5 text-[11px] text-text-secondary">
                            {item.teacher_name || "Преподаватель не назначен"}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-xs font-bold text-text-secondary">
                          {item.stream_type || "—"}
                        </td>
                        <td className="px-3 py-3">
                          <input
                            type="number"
                            min={0}
                            max={14}
                            value={item.lessons_count}
                            onChange={(event) =>
                              setWeeklyDemands((current) =>
                                current.map((demand) =>
                                  demand.stream_id === item.stream_id
                                    ? {
                                        ...demand,
                                        lessons_count: Math.max(
                                          0,
                                          Number(event.target.value),
                                        ),
                                      }
                                    : demand,
                                ),
                              )
                            }
                            className="w-20 rounded-lg border border-border-light px-2 py-1.5 text-sm font-bold outline-none focus:border-brand"
                          />
                        </td>
                        <td className="pl-3 py-3">
                          <input
                            type="number"
                            min={1}
                            max={10}
                            value={item.priority}
                            onChange={(event) =>
                              setWeeklyDemands((current) =>
                                current.map((demand) =>
                                  demand.stream_id === item.stream_id
                                    ? {
                                        ...demand,
                                        priority: Math.min(
                                          10,
                                          Math.max(
                                            1,
                                            Number(event.target.value),
                                          ),
                                        ),
                                      }
                                    : demand,
                                ),
                              )
                            }
                            className="w-20 rounded-lg border border-border-light px-2 py-1.5 text-sm font-bold outline-none focus:border-brand"
                          />
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-border-light px-6 py-4">
              <span className="text-xs font-semibold text-text-secondary">
                Активно потоков:{" "}
                {weeklyDemands.filter((item) => item.lessons_count > 0).length}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setEditingWeek(null)}
                  className="rounded-xl border border-border-light px-4 py-2.5 text-sm font-extrabold text-text-secondary"
                >
                  Отмена
                </button>
                <button
                  onClick={() => void saveWeeklyDemands()}
                  disabled={isSavingDemands}
                  className="rounded-xl bg-brand px-5 py-2.5 text-sm font-extrabold text-white disabled:opacity-50"
                >
                  {isSavingDemands ? "Сохранение…" : "Сохранить нагрузку"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fadeIn 0.4s ease-out forwards; }
        .group-item:hover .preview-btn { opacity: 1 !important; }
        .preview-btn { opacity: 0; transition: opacity 0.2s; }
      `,
        }}
      />
    </div>
  );
};
