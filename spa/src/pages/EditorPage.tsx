import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { API_BASE_URL, apiFetchJson } from "../api/apiConfig";
import "./EditorPage.css";

interface StreamItem {
  id: number;
  event_name: string;
  stream_type: string | null;
  is_ignored: boolean;
  teacher: string | null;
  groups: { name: string; size: number }[];
}

const streamTypes = [
  "Лекция",
  "Семинар",
  "Лабораторная",
  "Зачет",
  "Внеучебное мероприятие",
];

export function EditorPage() {
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [streams, setStreams] = useState<StreamItem[]>([]);
  const [loadedGroup, setLoadedGroup] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<ReadonlySet<number>>(new Set());
  const updates = useRef(new Map<number, AbortController>());

  useEffect(() => {
    const controller = new AbortController();
    void apiFetchJson<{ groups: string[] }>(
      `${API_BASE_URL}/api/v1/scheduler/groups`,
      "Не удалось загрузить список групп",
      { signal: controller.signal },
    )
      .then(({ groups }) => {
        if (!controller.signal.aborted) setGroups(groups);
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedGroup) return;
    const controller = new AbortController();
    void apiFetchJson<StreamItem[]>(
      `${API_BASE_URL}/api/v1/scheduler/streams?group_name=${encodeURIComponent(selectedGroup)}`,
      "Не удалось загрузить учебные потоки",
      { signal: controller.signal },
    )
      .then((items) => {
        if (!controller.signal.aborted) setStreams(items);
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) {
          setStreams([]);
          setError(error.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadedGroup(selectedGroup);
      });
    return () => controller.abort();
  }, [selectedGroup]);

  useEffect(() => {
    const pending = updates.current;
    return () => pending.forEach((controller) => controller.abort());
  }, []);

  const updateStream = async (
    stream: StreamItem,
    patch: Partial<Pick<StreamItem, "stream_type" | "is_ignored">>,
  ) => {
    if (updates.current.has(stream.id)) return;
    const controller = new AbortController();
    const update = (values: Partial<StreamItem>) => {
      setStreams((current) =>
        current.map((item) =>
          item.id === stream.id ? { ...item, ...values } : item,
        ),
      );
    };
    updates.current.set(stream.id, controller);
    setSaving(new Set(updates.current.keys()));
    setError(null);
    update(patch);

    try {
      await apiFetchJson(
        `${API_BASE_URL}/api/v1/scheduler/streams/${stream.id}`,
        "Не удалось сохранить изменение",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
          signal: controller.signal,
        },
      );
      if (!controller.signal.aborted) update(patch);
    } catch (error) {
      if (!controller.signal.aborted) {
        update(stream);
        setError(
          error instanceof Error
            ? error.message
            : "Не удалось сохранить изменение",
        );
      }
    } finally {
      updates.current.delete(stream.id);
      if (!controller.signal.aborted)
        setSaving(new Set(updates.current.keys()));
    }
  };

  const filteredGroups = groups.filter((group) =>
    group.toLowerCase().includes(query.toLowerCase()),
  );
  const filteredStreams = streams.filter(
    (stream) => !typeFilter || stream.stream_type === typeFilter,
  );

  return (
    <div className="enterprise-page">
      <header className="workspace-header">
        <div>
          <h1>Редактор учебных потоков</h1>
          <p>Уточняйте типы пар и выбирайте занятия для расчёта.</p>
        </div>
      </header>
      {error && (
        <p className="notice notice--danger" role="alert">
          {error}
        </p>
      )}
      <div className="editor-layout">
        <aside className="app-panel editor-groups" aria-label="Учебные группы">
          <label className="app-search">
            <Search size={16} aria-hidden="true" />
            <input
              className="app-field"
              type="search"
              aria-label="Поиск групп"
              placeholder="Поиск групп"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <ul>
            {filteredGroups.map((group) => (
              <li key={group}>
                <button
                  type="button"
                  aria-pressed={selectedGroup === group}
                  onClick={() => {
                    setSelectedGroup(group);
                    if (selectedGroup !== group) {
                      setLoadedGroup(null);
                      setError(null);
                    }
                  }}
                >
                  {group}
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <section className="app-panel editor-streams">
          {selectedGroup ? (
            <>
              <div className="app-section app-section--header">
                <h2>{selectedGroup}</h2>
                <label className="app-field-label">
                  Тип занятия
                  <select
                    className="app-field"
                    value={typeFilter}
                    onChange={(event) => setTypeFilter(event.target.value)}
                  >
                    <option value="">Все типы</option>
                    {streamTypes.map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </select>
                </label>
              </div>
              {loadedGroup !== selectedGroup ? (
                <p className="loading-state" role="status">
                  Загрузка учебных потоков…
                </p>
              ) : filteredStreams.length ? (
                <div className="app-table-scroll">
                  <table className="app-table editor-table">
                    <thead>
                      <tr>
                        <th scope="col">Дисциплина / Преподаватель</th>
                        <th scope="col">Группы в потоке</th>
                        <th scope="col">Тип пары</th>
                        <th scope="col">Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredStreams.map((stream) => {
                        const pending = saving.has(stream.id);
                        return (
                          <tr key={stream.id}>
                            <th scope="row">
                              <strong>{stream.event_name}</strong>
                              <small>{stream.teacher || "Не назначен"}</small>
                            </th>
                            <td>
                              <ul className="app-control-row">
                                {stream.groups.map(({ name }) => (
                                  <li
                                    className={
                                      name === selectedGroup
                                        ? "editor-group--current"
                                        : undefined
                                    }
                                    key={name}
                                  >
                                    {name}
                                  </li>
                                ))}
                              </ul>
                            </td>
                            <td>
                              <select
                                className="app-field"
                                aria-label={`Тип пары: ${stream.event_name}`}
                                value={stream.stream_type || ""}
                                disabled={pending || stream.is_ignored}
                                onChange={(event) =>
                                  void updateStream(stream, {
                                    stream_type: event.target.value || null,
                                  })
                                }
                              >
                                <option value="">Не указан</option>
                                {stream.stream_type &&
                                  !streamTypes.includes(stream.stream_type) && (
                                    <option>{stream.stream_type}</option>
                                  )}
                                {streamTypes.map((type) => (
                                  <option key={type}>{type}</option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <label className="editor-table__status">
                                <input
                                  type="checkbox"
                                  aria-label={`Включить в расписание: ${stream.event_name}`}
                                  checked={!stream.is_ignored}
                                  disabled={pending}
                                  onChange={(event) =>
                                    void updateStream(stream, {
                                      is_ignored: !event.target.checked,
                                    })
                                  }
                                />
                                {stream.is_ignored
                                  ? "Исключена"
                                  : "В расписании"}
                              </label>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="app-section text-text-secondary">
                  Нет пар, соответствующих фильтру.
                </p>
              )}
            </>
          ) : (
            <p className="app-section text-text-secondary">
              Выберите группу для просмотра пар.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
