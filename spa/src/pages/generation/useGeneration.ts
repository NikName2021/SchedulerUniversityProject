import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { API_BASE_URL, apiFetchJson } from "../../api/apiConfig";
import { isActiveTask, usePolling } from "../../hooks/usePolling";
import {
  getStandaloneGroups,
  isStandaloneGroupName,
} from "../../utils/groupSelection";
import type {
  AcademicPeriod,
  BatchWeekState,
  ExperimentalGroupSelection,
  GenerationMode,
  NewPeriod,
  PlanningWeek,
  RuleProfileOption,
  SemesterDistributionResult,
  StreamPreview,
  WeeklyDemand,
} from "./types";

export function useGeneration() {
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
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [ruleProfileId, setRuleProfileId] = useState<number | null>(null);
  const [generationMode, setGenerationMode] = useState<GenerationMode>("week");
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
  const [newPeriod, setNewPeriod] = useState<NewPeriod>({
    name: "",
    starts_on: "",
    ends_on: "",
  });
  const [status, setStatus] = useState<{
    type: "success" | "warning" | "error";
    msg: string;
  } | null>(null);

  const [previewGroup, setPreviewGroup] = useState<string | null>(null);
  const [previewStreams, setPreviewStreams] = useState<StreamPreview[]>([]);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [experimentalSelection, setExperimentalSelection] =
    useState<ExperimentalGroupSelection | null>(null);
  const [isExpandingGroups, setIsExpandingGroups] = useState(false);

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

  const fetchSubjectSummary = useCallback(
    async (signal: AbortSignal) => {
      setIsSummaryLoading(true);
      try {
        const data = await apiFetchJson<Record<string, string[]>>(
          `${API_BASE_URL}/api/v1/scheduler/subjects-summary`,
          "Не удалось загрузить сводку дисциплин",
          {
            method: "POST",
            signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              groups: selectedGroups,
              types: enabledTypes,
            }),
          },
        );
        if (!signal.aborted) setSubjectSummary(data);
      } catch {
        if (!signal.aborted) setSubjectSummary({});
      } finally {
        if (!signal.aborted) setIsSummaryLoading(false);
      }
    },
    [selectedGroups, enabledTypes],
  );

  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [groupsData, profilesData, periodsData] = await Promise.all([
        apiFetchJson<{ groups?: string[] }>(
          `${API_BASE_URL}/api/v1/scheduler/groups`,
          "Не удалось загрузить группы",
        ),
        apiFetchJson<RuleProfileOption[]>(
          `${API_BASE_URL}/api/v1/reference/rule-profiles`,
          "Не удалось загрузить профили правил",
        ).catch(() => []),
        apiFetchJson<AcademicPeriod[]>(
          `${API_BASE_URL}/api/v1/planning/periods`,
          "Не удалось загрузить учебные периоды",
        ).catch(() => []),
      ]);

      setGroups(groupsData.groups || []);
      // If no inherited groups, don't auto-select all
      if (!inheritedData?.groups) {
        setSelectedGroups([]);
      }
      setPeriods(periodsData);
      if (periodsData.length > 0) {
        const firstPeriod = periodsData[0];
        setSelectedPeriodId((current) => current || firstPeriod.id);
        setSelectedWeekIds((current) =>
          current.length > 0
            ? current
            : firstPeriod.weeks.map((week) => week.id),
        );
      }
      setRuleProfileId(
        profilesData.find((item) => item.is_default)?.id ||
          profilesData[0]?.id ||
          null,
      );
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось загрузить данные для расчёта",
      });
    } finally {
      setIsLoading(false);
    }
  }, [inheritedData]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    const controller = new AbortController();
    if (selectedGroups.length && enabledTypes.length) {
      void fetchSubjectSummary(controller.signal);
    } else {
      setSubjectSummary({});
      setIsSummaryLoading(false);
    }
    return () => controller.abort();
  }, [selectedGroups, enabledTypes, fetchSubjectSummary]);

  const selectedPeriod = periods.find(
    (period) => period.id === selectedPeriodId,
  );
  const loadDemandCounts = useCallback(
    async (
      weeks: PlanningWeek[],
      selectLoadedWeeks = true,
      signal?: AbortSignal,
    ) => {
      if (weeks.length === 0) {
        setDemandCounts({});
        return;
      }
      try {
        const responses = await Promise.all(
          weeks.map(async (week) => {
            const payload = await apiFetchJson<{
              demands: Array<{ lessons_count: number }>;
            }>(
              `${API_BASE_URL}/api/v1/planning/weeks/${week.id}/demands`,
              "Не удалось загрузить нагрузку по неделям",
              { signal },
            );
            return [
              week.id,
              payload.demands.reduce(
                (total, demand) => total + Math.max(0, demand.lessons_count),
                0,
              ),
            ] as const;
          }),
        );
        if (signal?.aborted) return;
        setDemandCounts(Object.fromEntries(responses));
        if (selectLoadedWeeks)
          setSelectedWeekIds(
            responses
              .filter(([, lessonsCount]) => lessonsCount > 0)
              .map(([weekId]) => weekId),
          );
      } catch (error) {
        if (signal?.aborted) return;
        setStatus({
          type: "error",
          msg:
            error instanceof Error
              ? error.message
              : "Не удалось загрузить нагрузку по неделям",
        });
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    if (selectedPeriod)
      void loadDemandCounts(selectedPeriod.weeks, true, controller.signal);
    return () => controller.abort();
  }, [selectedPeriod, loadDemandCounts]);

  usePolling(
    batchWeeks.some((item) => item.taskId && isActiveTask(item.status)),
    async (signal) => {
      const tasks = await apiFetchJson<
        Array<{
          id: number;
          status: BatchWeekState["status"];
          progress_percent: number;
          error_message: string | null;
        }>
      >(
        `${API_BASE_URL}/api/v1/scheduler/tasks`,
        "Не удалось обновить прогресс расчётов",
        { signal },
      );
      if (signal.aborted) return;
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
    },
  );

  const handleToggleGroup = (group: string) => {
    setExperimentalSelection(null);
    setSelectedGroups((prev) =>
      prev.includes(group) ? prev.filter((g) => g !== group) : [...prev, group],
    );
  };

  const handleToggleType = (type: string) => {
    setEnabledTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  };

  const previewRequest = useRef<AbortController | null>(null);
  useEffect(() => () => previewRequest.current?.abort(), []);

  const closePreview = () => {
    previewRequest.current?.abort();
    setPreviewGroup(null);
    setIsPreviewLoading(false);
  };

  const handlePreviewGroup = async (group: string) => {
    previewRequest.current?.abort();
    const controller = new AbortController();
    previewRequest.current = controller;
    setPreviewGroup(group);
    setPreviewStreams([]);
    setIsPreviewLoading(true);
    try {
      const data = await apiFetchJson<
        Array<StreamPreview & { is_ignored: boolean }>
      >(
        `${API_BASE_URL}/api/v1/scheduler/streams?group_name=${encodeURIComponent(group)}`,
        "Не удалось загрузить потоки группы",
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      // Only show active (not ignored) streams
      setPreviewStreams(data.filter((s) => !s.is_ignored));
    } catch (error) {
      if (controller.signal.aborted) return;
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось загрузить потоки группы",
      });
    } finally {
      if (!controller.signal.aborted) setIsPreviewLoading(false);
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
    setStatus(null);
    try {
      const period = await apiFetchJson<AcademicPeriod>(
        `${API_BASE_URL}/api/v1/planning/periods`,
        "Не удалось создать период",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...newPeriod,
            period_type: "semester",
            create_weeks: true,
          }),
        },
      );
      setPeriods((current) => [period, ...current]);
      setSelectedPeriodId(period.id);
      setSelectedWeekIds(period.weeks.map((week) => week.id));
      setNewPeriod({ name: "", starts_on: "", ends_on: "" });
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error ? error.message : "Не удалось создать период",
      });
    }
  };

  const distributeSemesterDemands = async () => {
    if (!selectedPeriod || selectedGroups.length === 0) return;
    setIsPreparingDemands(true);
    setStatus(null);
    try {
      const payload = await apiFetchJson<SemesterDistributionResult>(
        `${API_BASE_URL}/api/v1/planning/periods/${selectedPeriod.id}/demands/distribute`,
        "Не удалось распределить семестровую нагрузку",
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
      if (!Array.isArray(payload?.weeks) || !Array.isArray(payload.warnings)) {
        throw new Error("Не удалось распределить семестровую нагрузку");
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
      const resultMessage = `Распределено ${payload.distributed_lessons} из ${payload.planned_lessons} пар по ${payload.weeks.filter((week) => week.lessons_count > 0).length} неделям`;
      setStatus(
        payload.warnings.length > 0
          ? {
              type: "warning",
              msg: `${resultMessage}. ${payload.warnings.join("; ")}`,
            }
          : { type: "success", msg: resultMessage },
      );
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
          const payload = await apiFetchJson<{ task_id?: number }>(
            `${API_BASE_URL}/api/v1/scheduler/generate`,
            "Не удалось поставить неделю в очередь",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(
                buildCalculationPayload(week, semesterBatchId),
              ),
            },
          );
          if (!payload?.task_id) {
            throw new Error("Не удалось поставить неделю в очередь");
          }
          return {
            week,
            taskId: payload.task_id,
            status: "queued",
            progress: 0,
            error: null,
          };
        } catch (error) {
          return {
            week,
            taskId: null,
            status: "failed",
            progress: 100,
            error:
              error instanceof Error
                ? error.message
                : "Не удалось поставить неделю в очередь",
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
    setStatus(null);
    try {
      const payload = await apiFetchJson<{ task_id?: number }>(
        `${API_BASE_URL}/api/v1/scheduler/tasks/${item.taskId}/retry`,
        "Не удалось повторить расчёт недели",
        { method: "POST" },
      );
      const taskId = payload?.task_id;
      if (!taskId) throw new Error("Не удалось повторить расчёт недели");
      setBatchWeeks((current) =>
        current.map((week) =>
          week.week.id === item.week.id
            ? { ...week, taskId, status: "queued", progress: 0, error: null }
            : week,
        ),
      );
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось повторить расчёт недели",
      });
    }
  };

  const openWeeklyDemandEditor = async (week: PlanningWeek) => {
    setStatus(null);
    try {
      const payload = await apiFetchJson<{ demands: WeeklyDemand[] }>(
        `${API_BASE_URL}/api/v1/planning/weeks/${week.id}/demands`,
        "Не удалось загрузить недельную нагрузку",
      );
      if (!Array.isArray(payload?.demands)) {
        throw new Error("Не удалось загрузить недельную нагрузку");
      }
      setWeeklyDemands(payload.demands);
      setEditingWeek(week);
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось загрузить недельную нагрузку",
      });
    }
  };

  const saveWeeklyDemands = async () => {
    if (!editingWeek) return;
    setIsSavingDemands(true);
    setStatus(null);
    try {
      await apiFetchJson(
        `${API_BASE_URL}/api/v1/planning/weeks/${editingWeek.id}/demands`,
        "Не удалось сохранить недельную нагрузку",
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
      setEditingWeek(null);
      setStatus({ type: "success", msg: "Недельная нагрузка сохранена" });
      if (selectedPeriod) await loadDemandCounts(selectedPeriod.weeks);
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось сохранить недельную нагрузку",
      });
    } finally {
      setIsSavingDemands(false);
    }
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
      await apiFetchJson(
        `${API_BASE_URL}/api/v1/scheduler/generate`,
        "Не удалось отправить задачу",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildCalculationPayload()),
        },
      );

      setStatus({
        type: "success",
        msg: "Задача на генерацию успешно отправлена!",
      });
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось отправить задачу",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const standaloneGroups = getStandaloneGroups(groups);
  const onlyStandaloneGroupsSelected =
    standaloneGroups.length > 0 &&
    selectedGroups.length === standaloneGroups.length &&
    standaloneGroups.every((group) => selectedGroups.includes(group));

  const toggleStandaloneGroups = () => {
    setExperimentalSelection(null);
    setSelectedGroups(onlyStandaloneGroupsSelected ? [] : standaloneGroups);
  };

  const toggleExperimentalGroups = async () => {
    if (experimentalSelection) {
      setExperimentalSelection(null);
      setSelectedGroups([]);
      return;
    }
    const requestedGroups = selectedGroups.filter(isStandaloneGroupName);
    const baseGroups =
      requestedGroups.length > 0 ? requestedGroups : standaloneGroups;
    if (baseGroups.length === 0) return;

    setIsExpandingGroups(true);
    try {
      const payload = await apiFetchJson<ExperimentalGroupSelection>(
        `${API_BASE_URL}/api/v1/scheduler/groups/selection-preview`,
        "Не удалось определить связанные потоки",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ groups: baseGroups }),
        },
      );
      if (!Array.isArray(payload?.selected_groups)) {
        throw new Error("Не удалось определить связанные потоки");
      }
      setExperimentalSelection(payload);
      setSelectedGroups(payload.selected_groups);
      setStatus({
        type: "success",
        msg: `Экспериментальный выбор: ${payload.base_groups.length} основных групп, ${payload.joint_groups.length} общих потоков и ${payload.subgroup_groups.length} подгрупп`,
      });
    } catch (error) {
      setStatus({
        type: "error",
        msg:
          error instanceof Error
            ? error.message
            : "Не удалось определить связанные потоки",
      });
    } finally {
      setIsExpandingGroups(false);
    }
  };

  const selectPeriod = (id: number) => {
    setSelectedPeriodId(id);
    setSelectedWeekIds([]);
    setDemandCounts({});
    setDistributionResult(null);
    setBatchWeeks([]);
  };

  return {
    groups,
    selectedGroups,
    holidays,
    startDate,
    setStartDate,
    endDate,
    setEndDate,
    newHoliday,
    setNewHoliday,
    isLoading,
    isGenerating,
    generationMode,
    setGenerationMode,
    periods,
    selectedPeriod,
    selectedWeekIds,
    setSelectedWeekIds,
    demandCounts,
    isPreparingDemands,
    distributionResult,
    batchWeeks,
    editingWeek,
    setEditingWeek,
    weeklyDemands,
    setWeeklyDemands,
    isSavingDemands,
    newPeriod,
    setNewPeriod,
    status,
    previewGroup,
    previewStreams,
    isPreviewLoading,
    experimentalSelection,
    isExpandingGroups,
    enabledTypes,
    subjectSummary,
    subjectPriorities,
    setSubjectPriorities,
    isSummaryLoading,
    standaloneGroups,
    onlyStandaloneGroupsSelected,
    loadDemandCounts,
    handlePreviewGroup,
    closePreview,
    handleToggleGroup,
    handleToggleType,
    handleAddHoliday,
    handleRemoveHoliday,
    selectPeriod,
    createAcademicPeriod,
    distributeSemesterDemands,
    retryBatchWeek,
    openWeeklyDemandEditor,
    saveWeeklyDemands,
    handleStartGeneration,
    toggleStandaloneGroups,
    toggleExperimentalGroups,
  };
}
