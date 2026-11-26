import { AlertCircle, X } from "lucide-react";
import type { ScheduleEntry } from "./types";
import { DAYS, parseLocalDate } from "./week";

const getEntryDayName = (dateStr: string) => {
  const d = parseLocalDate(dateStr);
  if (isNaN(d.getTime())) return "";
  const dayNum = (d.getDay() + 6) % 7;
  return DAYS[dayNum] ?? "ВС";
};

const formatDateReadable = (dateStr: string) => {
  const d = parseLocalDate(dateStr);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
};

export function ConflictsSidebar({
  conflictedEntries,
  onSelect,
  onClose,
}: {
  conflictedEntries: ScheduleEntry[];
  onSelect: (entry: ScheduleEntry) => void;
  onClose: () => void;
}) {
  return (
    <div className="schedule-sidebar animate-fade-in">
      <div className="p-3 border-b border-border-light bg-red-50/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle size={18} className="text-red-500" />
          <h2 className="font-bold text-text-primary text-sm">
            Конфликты ({conflictedEntries.length})
          </h2>
        </div>
        <button
          type="button"
          aria-label="Закрыть список конфликтов"
          onClick={onClose}
          className="p-1 hover:bg-black/5 rounded text-text-secondary cursor-pointer"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {conflictedEntries.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-text-tertiary gap-2 py-20 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center font-bold text-lg">
              ✓
            </div>
            <p className="text-xs font-semibold text-emerald-600">
              Конфликты не обнаружены
            </p>
            <p className="text-[10px] text-text-secondary px-4">
              Расписание составлено корректно!
            </p>
          </div>
        ) : (
          conflictedEntries.map((entry) => {
            const dayName = entry.date ? getEntryDayName(entry.date) : "";
            const formattedDate = entry.date
              ? formatDateReadable(entry.date)
              : "";
            return (
              <button
                type="button"
                key={entry.id}
                onClick={() => onSelect(entry)}
                className="w-full text-left p-3 bg-red-50/30 border border-red-100 hover:border-red-300 rounded-xl transition-all cursor-pointer group flex flex-col gap-2 relative shadow-sm hover:shadow"
              >
                <div className="flex justify-between items-start">
                  <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full uppercase">
                    {entry.stream_type}
                  </span>
                  {entry.date ? (
                    <span className="text-[10px] text-text-secondary font-medium">
                      {dayName} {formattedDate}, {entry.lesson_number} пара
                    </span>
                  ) : (
                    <span className="text-[10px] text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full font-bold">
                      Не выставлен
                    </span>
                  )}
                </div>
                <div className="text-xs font-extrabold text-text-primary group-hover:text-brand transition-colors line-clamp-1">
                  {entry.event_name}
                </div>
                {entry.warning && (
                  <div className="text-[10px] text-red-600 bg-white/60 p-2 rounded border border-red-100 leading-normal font-medium flex gap-1 items-start">
                    <AlertCircle size={10} className="shrink-0 mt-0.5" />
                    <span>{entry.warning}</span>
                  </div>
                )}
                <div className="flex justify-between items-center mt-1 text-[9px] text-text-secondary font-semibold border-t border-red-50/50 pt-2">
                  <span>Препод: {entry.teacher || "—"}</span>
                  <span className="text-brand font-bold group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5">
                    Перейти →
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>

      <div className="p-3 bg-red-50/40 border-t border-red-100 rounded-b-2xl">
        <p className="text-[10px] text-red-700 leading-relaxed font-semibold">
          Нажмите на конфликт, чтобы автоматически сфокусироваться и подсветить
          занятие в сетке.
        </p>
      </div>
    </div>
  );
}
