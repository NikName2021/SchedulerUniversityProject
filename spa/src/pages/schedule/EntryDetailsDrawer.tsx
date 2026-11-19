import type React from "react";
import { AlertCircle, X } from "lucide-react";
import { Modal } from "../../components/Modal";
import type { ScheduleEntryDetails } from "./types";
import { PAIRS, parseLocalDate } from "./week";

export const EntryDetailsDrawer: React.FC<{
  details: ScheduleEntryDetails | null;
  loading: boolean;
  onClose: () => void;
}> = ({ details, loading, onClose }) => {
  if (loading && !details) {
    return (
      <div className="fixed bottom-6 right-6 z-[70] flex items-center gap-2 rounded-xl border border-border-light bg-white px-4 py-3 text-xs font-bold text-text-secondary shadow-xl">
        <span className="loading-state__spinner" /> Загружаем занятие…
      </div>
    );
  }
  if (!details) return null;

  return (
    <Modal
      className="app-dialog--drawer"
      label="Полная информация о занятии"
      onClose={onClose}
    >
      <div className="bg-white">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border-light bg-white/95 p-6 backdrop-blur">
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.16em] text-brand">
              {details.stream_type}
            </div>
            <h2 className="mt-2 text-xl font-black leading-tight text-text-primary">
              {details.discipline_name}
            </h2>
          </div>
          <button
            type="button"
            className="button-icon shrink-0"
            title="Закрыть"
            aria-label="Закрыть информацию о занятии"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-6 p-6">
          {details.warning && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <span>{details.warning}</span>
            </div>
          )}

          <section className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-border-light bg-bg-base/40 p-4">
              <div className="text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                Дата и время
              </div>
              <div className="mt-2 text-sm font-extrabold text-text-primary">
                {details.date
                  ? parseLocalDate(details.date).toLocaleDateString("ru-RU")
                  : "Не выставлено"}
              </div>
              <div className="mt-1 text-xs font-semibold text-text-secondary">
                {details.lesson_number
                  ? `${details.lesson_number} пара · ${PAIRS.find((pair) => pair.num === details.lesson_number)?.time || "время не указано"}`
                  : "Пара не назначена"}
              </div>
            </div>
            <div className="rounded-xl border border-border-light bg-bg-base/40 p-4">
              <div className="text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                Преподаватель
              </div>
              <div className="mt-2 text-sm font-extrabold text-text-primary">
                {details.teacher || "Не назначен"}
              </div>
              <div className="mt-1 text-xs font-semibold text-text-secondary">
                Аудитория: {details.room_id || "не назначена"}
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-xs font-black uppercase tracking-wider text-text-tertiary">
              Группы и потоки
            </h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {details.base_groups.map((group) => (
                <span
                  key={group}
                  className="rounded-lg bg-brand px-3 py-1.5 text-xs font-bold text-white"
                >
                  {group}
                </span>
              ))}
              {details.subgroups.map((subgroup) => (
                <span
                  key={subgroup}
                  className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-bold text-violet-700"
                >
                  {subgroup}
                </span>
              ))}
            </div>
            <div className="mt-3 rounded-xl border border-border-light p-4 text-xs font-semibold text-text-secondary">
              <div className="mb-2 font-black text-text-primary">
                Исходная аудитория
              </div>
              {details.audience_labels.join(" · ")}
            </div>
          </section>

          <section className="grid grid-cols-3 gap-3">
            {[
              ["По плану", details.planned_count],
              ["Выставлено", details.scheduled_count],
              ["Осталось", details.unassigned_count],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-border-light p-4 text-center"
              >
                <div className="text-2xl font-black text-text-primary">
                  {value}
                </div>
                <div className="mt-1 text-[10px] font-black uppercase tracking-wider text-text-tertiary">
                  {label}
                </div>
              </div>
            ))}
          </section>

          <section className="rounded-xl border border-border-light bg-bg-base/30 p-4">
            <h3 className="text-xs font-black uppercase tracking-wider text-text-tertiary">
              Служебная информация
            </h3>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs">
              <dt className="font-semibold text-text-tertiary">Занятие</dt>
              <dd className="font-bold text-text-primary">#{details.id}</dd>
              <dt className="font-semibold text-text-tertiary">Расчёт</dt>
              <dd className="font-bold text-text-primary">
                #{details.task_id || "—"}
              </dd>
              <dt className="font-semibold text-text-tertiary">Поток</dt>
              <dd className="font-bold text-text-primary">
                #{details.source_stream_id || "—"}
              </dd>
              <dt className="font-semibold text-text-tertiary">Статус</dt>
              <dd className="font-bold text-text-primary">
                {details.is_locked ? "Зафиксировано" : "Можно перемещать"}
              </dd>
            </dl>
          </section>
        </div>
      </div>
    </Modal>
  );
};
