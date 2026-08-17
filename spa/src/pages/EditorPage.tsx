import React, { useState, useEffect, useCallback } from "react";
import { Users, Search, BookOpen, Filter } from "lucide-react";
import { API_BASE_URL, apiFetch } from "../api/apiConfig";

interface StreamItem {
  id: number;
  event_name: string;
  stream_type: string | null;
  is_ignored: boolean;
  teacher: string | null;
  groups: { name: string; size: number }[];
}

const STREAM_TYPES = [
  "Лекция",
  "Семинар",
  "Лабораторная",
  "Зачет",
  "Внеучебное мероприятие",
];

export const EditorPage: React.FC = () => {
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [streams, setStreams] = useState<StreamItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>("Все типы");
  const [error, setError] = useState<string | null>(null);

  const fetchGroups = useCallback(async () => {
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/v1/scheduler/groups`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setGroups(data.groups || []);
    } catch {
      setError("Не удалось загрузить список групп");
    }
  }, []);

  const fetchStreams = useCallback(async (group: string) => {
    setIsLoading(true);
    try {
      const res = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/streams?group_name=${encodeURIComponent(group)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStreams(data);
    } catch {
      setError("Не удалось загрузить учебные потоки");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateStream = useCallback(
    async (id: number, payload: Partial<StreamItem>) => {
      const previous = streams.find((stream) => stream.id === id);
      setError(null);
      // Optimistic UI update
      setStreams((prev) =>
        prev.map((s) => (s.id === id ? { ...s, ...payload } : s)),
      );

      try {
        const response = await apiFetch(
          `${API_BASE_URL}/api/v1/scheduler/streams/${id}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
          },
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
      } catch {
        if (previous) {
          setStreams((current) =>
            current.map((stream) => (stream.id === id ? previous : stream)),
          );
        }
        setError("Изменение не сохранено. Предыдущее значение восстановлено.");
      }
    },
    [streams],
  );

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  useEffect(() => {
    if (selectedGroup) {
      fetchStreams(selectedGroup);
    }
  }, [selectedGroup, fetchStreams]);

  const filteredGroups = groups.filter((g) =>
    g.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredStreams = streams.filter(
    (s) => typeFilter === "Все типы" || s.stream_type === typeFilter,
  );

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
          <h1 className="text-2xl font-bold text-text-primary">Редактор пар</h1>
          <p className="text-text-secondary mt-1 text-sm">
            Уточняйте типы пар и исключайте лишние дисциплины перед генерацией
            расписания.
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
        {/* Left Sidebar: List of groups */}
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
                placeholder="Поиск группы..."
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
            {filteredGroups.map((group) => (
              <button
                key={group}
                onClick={() => setSelectedGroup(group)}
                style={{
                  width: "100%",
                  padding: "0.875rem 1rem",
                  textAlign: "left",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  borderBottom: "1px solid var(--border-light)",
                  backgroundColor:
                    selectedGroup === group ? "#eef2ff" : "transparent",
                  color:
                    selectedGroup === group
                      ? "var(--brand)"
                      : "var(--text-primary)",
                  fontWeight: selectedGroup === group ? 700 : 500,
                  transition: "background-color 0.15s",
                  cursor: "pointer",
                }}
                className="hover:bg-gray-50"
              >
                {group}
              </button>
            ))}
            {filteredGroups.length === 0 && (
              <div
                style={{
                  padding: "2rem 1rem",
                  textAlign: "center",
                  color: "var(--text-tertiary)",
                  fontSize: "0.875rem",
                }}
              >
                Группы не найдены
              </div>
            )}
          </div>
        </div>

        {/* Right Content: Streams Editor */}
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
          {selectedGroup ? (
            <>
              <div
                style={{
                  padding: "1rem 1.25rem",
                  borderBottom: "1px solid var(--border-light)",
                  backgroundColor: "#fafafa",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                  }}
                >
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "8px",
                      backgroundColor: "var(--bg-base)",
                      color: "var(--brand)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <BookOpen size={18} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: "1.125rem", fontWeight: 700 }}>
                      Учебный план: {selectedGroup}
                    </h2>
                    <p
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-tertiary)",
                        marginTop: "0.125rem",
                      }}
                    >
                      Найдено пар: {streams.length}
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      backgroundColor: "white",
                      padding: "0.375rem 0.75rem",
                      borderRadius: "8px",
                      border: "1px solid var(--border-light)",
                    }}
                  >
                    <Filter
                      size={14}
                      style={{ color: "var(--text-secondary)" }}
                    />
                    <select
                      value={typeFilter}
                      onChange={(e) => setTypeFilter(e.target.value)}
                      style={{
                        border: "none",
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        outline: "none",
                        backgroundColor: "transparent",
                      }}
                    >
                      <option>Все типы</option>
                      {STREAM_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div style={{ flex: 1, overflowY: "auto", padding: "0" }}>
                {isLoading ? (
                  <div
                    style={{
                      padding: "3rem",
                      textAlign: "center",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    Загрузка...
                  </div>
                ) : streams.length === 0 ? (
                  <div
                    style={{
                      padding: "3rem",
                      textAlign: "center",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    У этой группы нет пар.
                  </div>
                ) : (
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
                        zIndex: 10,
                        boxShadow: "0 1px 0 var(--border-light)",
                      }}
                    >
                      <tr>
                        <th
                          style={{
                            padding: "1rem 1.25rem",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            textTransform: "uppercase",
                          }}
                        >
                          Дисциплина / Преподаватель
                        </th>
                        <th
                          style={{
                            padding: "1rem 1.25rem",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            textTransform: "uppercase",
                          }}
                        >
                          Группы в потоке
                        </th>
                        <th
                          style={{
                            padding: "1rem 1.25rem",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            textTransform: "uppercase",
                          }}
                        >
                          Тип пары
                        </th>
                        <th
                          style={{
                            padding: "1rem 1.25rem",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            textTransform: "uppercase",
                            textAlign: "right",
                          }}
                        >
                          Статус
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStreams.map((stream) => (
                        <tr
                          key={stream.id}
                          style={{
                            borderBottom: "1px solid var(--border-light)",
                            backgroundColor: stream.is_ignored
                              ? "#fafafa"
                              : "transparent",
                            opacity: stream.is_ignored ? 0.6 : 1,
                            transition: "all 0.2s",
                          }}
                          className="hover:bg-gray-50"
                        >
                          <td style={{ padding: "1rem 1.25rem" }}>
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: "0.875rem",
                                color: "var(--text-primary)",
                                marginBottom: "0.25rem",
                              }}
                            >
                              {stream.event_name}
                            </div>
                            <div
                              style={{
                                fontSize: "0.75rem",
                                color: "var(--text-tertiary)",
                              }}
                            >
                              {stream.teacher || "Не назначен"}
                            </div>
                          </td>
                          <td style={{ padding: "1rem 1.25rem" }}>
                            <div
                              style={{
                                display: "flex",
                                flexWrap: "wrap",
                                gap: "0.25rem",
                              }}
                            >
                              {stream.groups.map((g) => (
                                <span
                                  key={g.name}
                                  style={{
                                    fontSize: "0.65rem",
                                    padding: "0.125rem 0.375rem",
                                    backgroundColor:
                                      g.name === selectedGroup
                                        ? "var(--brand)"
                                        : "var(--bg-base)",
                                    color:
                                      g.name === selectedGroup
                                        ? "white"
                                        : "var(--text-secondary)",
                                    borderRadius: "4px",
                                    fontWeight: 600,
                                  }}
                                >
                                  {g.name}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td style={{ padding: "1rem 1.25rem" }}>
                            <select
                              value={stream.stream_type || "Не указан"}
                              onChange={(e) =>
                                updateStream(stream.id, {
                                  stream_type:
                                    e.target.value === "Не указан"
                                      ? null
                                      : e.target.value,
                                })
                              }
                              disabled={stream.is_ignored}
                              style={{
                                padding: "0.375rem 0.75rem",
                                borderRadius: "6px",
                                border: "1px solid var(--border-light)",
                                fontSize: "0.875rem",
                                color: "var(--text-primary)",
                                outline: "none",
                                cursor: stream.is_ignored
                                  ? "not-allowed"
                                  : "pointer",
                              }}
                            >
                              {STREAM_TYPES.map((t) => (
                                <option key={t} value={t}>
                                  {t}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td
                            style={{
                              padding: "1rem 1.25rem",
                              textAlign: "right",
                            }}
                          >
                            <label
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                cursor: "pointer",
                                gap: "0.5rem",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: "0.75rem",
                                  fontWeight: 600,
                                  color: stream.is_ignored
                                    ? "#ef4444"
                                    : "var(--brand)",
                                }}
                              >
                                {stream.is_ignored
                                  ? "Исключена"
                                  : "В расписании"}
                              </span>
                              <div
                                style={{
                                  width: "36px",
                                  height: "20px",
                                  backgroundColor: stream.is_ignored
                                    ? "#ef4444"
                                    : "var(--brand)",
                                  borderRadius: "100px",
                                  position: "relative",
                                  transition: "background-color 0.2s",
                                }}
                              >
                                <div
                                  style={{
                                    width: "16px",
                                    height: "16px",
                                    backgroundColor: "white",
                                    borderRadius: "50%",
                                    position: "absolute",
                                    top: "2px",
                                    left: stream.is_ignored ? "2px" : "18px",
                                    transition: "left 0.2s",
                                  }}
                                />
                              </div>
                              <input
                                type="checkbox"
                                checked={!stream.is_ignored}
                                onChange={(e) =>
                                  updateStream(stream.id, {
                                    is_ignored: !e.target.checked,
                                  })
                                }
                                style={{ display: "none" }}
                              />
                            </label>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
                Выберите группу слева для редактирования учебного плана
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
