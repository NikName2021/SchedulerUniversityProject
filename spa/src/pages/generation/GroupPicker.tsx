import { useState } from "react";
import { Eye, FlaskConical, Search } from "lucide-react";
import type { ExperimentalGroupSelection } from "./types";

interface Props {
  groups: string[];
  selected: string[];
  standaloneCount: number;
  standaloneSelected: boolean;
  experimental: ExperimentalGroupSelection | null;
  expanding: boolean;
  onToggle: (group: string) => void;
  onToggleStandalone: () => void;
  onToggleExperimental: () => void;
  onPreview: (group: string) => void;
}

export function GroupPicker({
  groups,
  selected,
  standaloneCount,
  standaloneSelected,
  experimental,
  expanding,
  onToggle,
  onToggleStandalone,
  onToggleExperimental,
  onPreview,
}: Props) {
  const [query, setQuery] = useState("");
  const filteredGroups = groups.filter((group) =>
    group.toLowerCase().includes(query.toLowerCase()),
  );
  const selectedGroups = new Set(selected);

  return (
    <section className="app-panel generation-groups">
      <div className="app-section generation-groups__header">
        <h2>Учебные группы</h2>
        <div className="app-control-row">
          <button
            type="button"
            className="app-toggle"
            aria-pressed={standaloneSelected}
            onClick={onToggleStandalone}
            disabled={!standaloneCount}
          >
            Только одиночные
          </button>
          <button
            type="button"
            className="app-toggle"
            aria-pressed={Boolean(experimental)}
            onClick={onToggleExperimental}
            disabled={expanding || !standaloneCount}
          >
            <FlaskConical size={14} aria-hidden="true" />
            {expanding ? "Проверяем…" : "С потоками · эксперимент"}
          </button>
        </div>
        <label className="app-search">
          <Search size={16} aria-hidden="true" />
          <input
            className="app-field"
            aria-label="Поиск групп"
            placeholder="Поиск групп"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        {experimental && (
          <p role="status" className="text-sm text-text-secondary">
            {experimental.base_groups.length} основных ·{" "}
            {experimental.joint_groups.length} общих потоков ·{" "}
            {experimental.subgroup_groups.length} подгрупп
          </p>
        )}
      </div>
      <ul className="generation-groups__list">
        {filteredGroups.map((group) => (
          <li
            key={group}
            className={
              selectedGroups.has(group) ? "generation-group--selected" : ""
            }
          >
            <label>
              <input
                type="checkbox"
                checked={selectedGroups.has(group)}
                onChange={() => onToggle(group)}
              />
              {group}
            </label>
            <button
              type="button"
              className="button-icon"
              aria-label={`Просмотреть состав группы ${group}`}
              title={`Просмотреть состав группы ${group}`}
              onClick={() => onPreview(group)}
            >
              <Eye size={16} />
            </button>
          </li>
        ))}
        {!filteredGroups.length && (
          <li className="text-text-secondary">Группы не найдены</li>
        )}
      </ul>
    </section>
  );
}
