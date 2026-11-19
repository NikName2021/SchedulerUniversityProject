import { memo } from "react";
import { DraggableCard, type CardActions } from "./ScheduleCard";
import { DroppableCell } from "./DropTargets";
import {
  DAYS,
  PAIRS,
  getSlotKey,
  getWeekDayDate,
  WEEK_DATE_FORMATTER,
  parseLocalDate,
} from "./week";
import type { ScheduleEntry, ScheduleView } from "./types";

interface Props {
  selectedWeek: string | null;
  selectedGroup: string;
  viewMode: ScheduleView;
  visibleEntriesBySlot: Map<string, ScheduleEntry[]>;
  showAvailability: boolean;
  availableSlotKeys: Set<string>;
  cardActions: CardActions;
}

export const ScheduleGrid = memo(function ScheduleGrid({
  selectedWeek,
  selectedGroup,
  viewMode,
  visibleEntriesBySlot,
  showAvailability,
  availableSlotKeys,
  cardActions,
}: Props) {
  const weekDates = DAYS.map((_, index) =>
    selectedWeek ? getWeekDayDate(selectedWeek, index) : "",
  );
  return (
    <div
      className="schedule-grid app-panel app-table-scroll"
      role="region"
      aria-label="Сетка расписания"
      tabIndex={0}
    >
      <table className="w-full border-collapse min-w-[900px] table-fixed">
        <thead>
          <tr className="border-b border-border-light bg-bg-base/30">
            <th className="p-4 text-left text-xs font-bold text-text-tertiary uppercase w-24">
              Пара
            </th>
            {DAYS.map((day, dayIdx) => (
              <th
                key={day}
                className="p-4 text-center text-xs font-bold text-text-tertiary uppercase border-l border-border-light"
              >
                {day}
                {selectedWeek && (
                  <time
                    dateTime={weekDates[dayIdx]}
                    className="block mt-1 text-sm font-semibold text-text-primary normal-case"
                  >
                    {WEEK_DATE_FORMATTER.format(
                      parseLocalDate(weekDates[dayIdx]),
                    )}
                  </time>
                )}
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
                const slotKey = selectedWeek
                  ? getSlotKey(weekDates[dayIdx], pair.num)
                  : "";
                const dayEntries = visibleEntriesBySlot.get(slotKey) || [];

                return (
                  <DroppableCell
                    key={day}
                    dayIdx={dayIdx}
                    pairNum={pair.num}
                    showAvailability={showAvailability}
                    isAvailable={availableSlotKeys.has(slotKey)}
                  >
                    {dayEntries.map((entry) => (
                      <DraggableCard
                        key={entry.id}
                        entry={entry}
                        selectedGroup={selectedGroup}
                        viewMode={viewMode}
                        actions={cardActions}
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
  );
});
