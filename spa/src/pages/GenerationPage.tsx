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
} from "lucide-react";
import { API_BASE_URL } from "../api/apiConfig";

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
      const res = await fetch(
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
      const [groupsRes, statsRes, profilesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/scheduler/groups`),
        fetch(`${API_BASE_URL}/api/v1/scheduler/stats`),
        fetch(`${API_BASE_URL}/api/v1/reference/rule-profiles`),
      ]);

      const groupsData = await groupsRes.json();
      const statsData = await statsRes.json();
      const profilesData = profilesRes.ok ? await profilesRes.json() : [];

      setGroups(groupsData.groups || []);
      // If no inherited groups, don't auto-select all
      if (!inheritedData?.groups) {
        setSelectedGroups([]);
      }
      setStats(statsData);
      setRuleProfiles(profilesData);
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
      const res = await fetch(
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

  const handleStartGeneration = async () => {
    setIsGenerating(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          groups: selectedGroups,
          holidays: holidays,
          start_date: startDate,
          end_date: endDate,
          settings: {
            enabled_types: enabledTypes,
            priorities: subjectPriorities,
            rule_profile_id: ruleProfileId,
            created_at: new Date().toISOString(),
          },
        }),
      });

      if (res.ok) {
        setStatus({
          type: "success",
          msg: "Задача на генерацию успешно отправлена!",
        });
      } else {
        setStatus({ type: "error", msg: "Ошибка при отправке задачи." });
      }
    } catch {
      setStatus({ type: "error", msg: "Не удалось связаться с сервером." });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExport = () => {
    window.open(`${API_BASE_URL}/api/v1/scheduler/export`, "_blank");
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
              fontSize: "2rem",
              fontWeight: 900,
              color: "var(--text-primary)",
              letterSpacing: "-0.02em",
            }}
          >
            Генератор расписания
          </h1>
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
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <div
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

      <section className="flex items-center justify-between rounded-2xl border border-border-light bg-white px-5 py-4 shadow-sm">
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
          className="min-w-64 rounded-xl border border-border-light bg-white px-4 py-2.5 text-sm font-bold text-text-primary outline-none focus:border-brand"
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
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, 1fr)",
          gap: "2rem",
        }}
      >
        {/* Left Column: Group Selection */}
        <div style={{ gridColumn: "span 4" }}>
          <div
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
          style={{
            gridColumn: "span 8",
            display: "flex",
            flexDirection: "column",
            gap: "2rem",
          }}
        >
          {/* Global Type Filter */}
          <div
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

            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
              {ALL_TYPES.map((type) => (
                <button
                  key={type}
                  onClick={() => handleToggleType(type)}
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
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "2rem",
            }}
          >
            {/* Semester Dates */}
            <div
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
                  <Clock size={20} />
                </div>
                <h3 style={{ fontWeight: 800 }}>Интервал семестра</h3>
              </div>

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
            </div>

            {/* Holidays */}
            <div
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
                  Запуск
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
                  Расчет {selectedGroups.length} групп с учетом выбранных типов
                  пар.
                </p>

                <button
                  disabled={
                    selectedGroups.length === 0 ||
                    isGenerating ||
                    enabledTypes.length === 0
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
                      enabledTypes.length === 0
                        ? "not-allowed"
                        : "pointer",
                    backgroundColor:
                      selectedGroups.length === 0 ||
                      isGenerating ||
                      enabledTypes.length === 0
                        ? "rgba(255,255,255,0.1)"
                        : "var(--brand)",
                    color:
                      selectedGroups.length === 0 ||
                      isGenerating ||
                      enabledTypes.length === 0
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
                  {isGenerating ? "Расчет..." : "Начать расчет"}
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
