import { Layers, X } from "lucide-react";
import { DraggableCard, type CardActions } from "./ScheduleCard";
import { SidebarDroppable } from "./DropTargets";
import type { ScheduleEntry, ScheduleView } from "./types";

interface Props {
  groupedUnassigned: ScheduleEntry[][];
  selectedGroup: string;
  viewMode: ScheduleView;
  applyExtracurricularToStream: boolean;
  onApplyToStream: (enabled: boolean) => void;
  showAvailability: boolean;
  cardActions: CardActions;
}

export function UnassignedSidebar({
  groupedUnassigned,
  selectedGroup,
  viewMode,
  applyExtracurricularToStream,
  onApplyToStream,
  showAvailability,
  cardActions,
}: Props) {
  const academicUnassigned = groupedUnassigned.filter(
    (group) => group[0].stream_type !== "Внеучебное мероприятие",
  );
  const extracurricularUnassigned = groupedUnassigned.filter(
    (group) => group[0].stream_type === "Внеучебное мероприятие",
  );
  return (
    <div className="schedule-sidebar">
      <div className="p-3 border-b border-border-light bg-bg-base/20 flex items-center justify-between">
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
        {groupedUnassigned.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-text-tertiary gap-2 py-20 text-center">
            <X size={32} opacity={0.3} />
            <p className="text-xs font-medium">Нет невыставленных пар</p>
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
                actions={cardActions}
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
                    onChange={(e) => onApplyToStream(e.target.checked)}
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
                    actions={cardActions}
                  />
                ))}
              </>
            )}
          </>
        )}
      </SidebarDroppable>

      <div className="p-3 bg-orange-50 border-t border-orange-100 rounded-b-2xl">
        <p className="text-[10px] text-orange-700 leading-relaxed font-medium">
          {showAvailability
            ? "Жёлтым отмечены свободные слоты для группы и преподавателя."
            : "Перетащите карточки отсюда в сетку расписания, чтобы назначить им время и день."}
        </p>
      </div>
    </div>
  );
}
