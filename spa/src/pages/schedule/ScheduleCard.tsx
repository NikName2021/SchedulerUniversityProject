import { memo } from "react";
import { useDraggable } from "@dnd-kit/core";
import {
  AlertCircle,
  GripVertical,
  Lock,
  MapPin,
  Trash2,
  Unlock,
  User,
  X,
} from "lucide-react";
import type { ScheduleEntry, ScheduleView } from "./types";

export interface CardActions {
  onOpenDetails: (id: number) => void;
  onToggleLock: (id: number, locked: boolean) => void;
  onUnassign: (id: number) => void;
  onDelete: (id: number) => void;
}

function cardType(type: string) {
  const name = type.toLowerCase();
  if (name.includes("лекция") || name.includes("lecture")) return "lecture";
  if (name.includes("лабораторная") || name.includes("lab")) return "lab";
  return "practice";
}

interface CardProps {
  entry: ScheduleEntry;
  showGroup: boolean;
  count?: number;
}

function CardContent({ entry, showGroup, count }: CardProps) {
  return (
    <>
      {count !== undefined && count > 1 && (
        <span className="schedule-card__count">{count}</span>
      )}
      <div className="schedule-card__metadata">
        <span>
          <MapPin size={12} aria-hidden="true" />
          {entry.room_id || "—"}
        </span>
        <span>
          <User size={12} aria-hidden="true" />
          {entry.teacher || "—"}
        </span>
        {showGroup && <strong>{entry.group_name}</strong>}
      </div>
      {entry.warning && (
        <p className="schedule-card__warning">
          <AlertCircle size={12} aria-hidden="true" />
          {entry.warning}
        </p>
      )}
    </>
  );
}

export function ScheduleCard(props: CardProps) {
  return (
    <div
      className={`schedule-card schedule-card--${cardType(props.entry.stream_type)} schedule-card--overlay`}
      aria-hidden="true"
    >
      <strong>{props.entry.event_name}</strong>
      <CardContent {...props} />
    </div>
  );
}

interface DraggableProps extends Omit<CardProps, "showGroup"> {
  selectedGroup: string;
  viewMode: ScheduleView;
  actions: CardActions;
}

export const DraggableCard = memo(function DraggableCard({
  entry,
  selectedGroup,
  viewMode,
  count,
  actions,
}: DraggableProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, isDragging } =
    useDraggable({
      id: `card-${entry.id}`,
      disabled: entry.is_locked,
    });
  const lockLabel = entry.is_locked ? "Разблокировать" : "Зафиксировать";
  const removeLabel = entry.date
    ? "Убрать в невыставленные"
    : "Удалить занятие";

  return (
    <article
      id={`card-${entry.id}`}
      ref={setNodeRef}
      className={`schedule-card schedule-card--${cardType(entry.stream_type)}${isDragging ? " schedule-card--dragging" : ""}${entry.warning ? " schedule-card--conflict" : ""}`}
    >
      <div className="schedule-card__toolbar">
        {entry.is_locked ? (
          <Lock size={14} aria-label="Занятие зафиксировано" />
        ) : (
          <button
            type="button"
            className="schedule-card__handle"
            ref={setActivatorNodeRef}
            {...listeners}
            {...attributes}
            aria-label={`Переместить: ${entry.event_name}`}
            title="Переместить занятие"
          >
            <GripVertical size={16} aria-hidden="true" />
          </button>
        )}
        <div className="schedule-card__actions">
          <button
            type="button"
            title={lockLabel}
            aria-label={`${lockLabel}: ${entry.event_name}`}
            onClick={() => actions.onToggleLock(entry.id, !entry.is_locked)}
          >
            {entry.is_locked ? <Unlock size={14} /> : <Lock size={14} />}
          </button>
          <button
            type="button"
            title={removeLabel}
            aria-label={`${removeLabel}: ${entry.event_name}`}
            onClick={() =>
              entry.date
                ? actions.onUnassign(entry.id)
                : actions.onDelete(entry.id)
            }
          >
            {entry.date ? <X size={14} /> : <Trash2 size={14} />}
          </button>
        </div>
      </div>
      <button
        type="button"
        className="schedule-card__details"
        onClick={() => actions.onOpenDetails(entry.id)}
      >
        {entry.event_name}
      </button>
      <CardContent
        entry={entry}
        showGroup={selectedGroup === "Все" || viewMode === "teacher"}
        count={count}
      />
    </article>
  );
});
