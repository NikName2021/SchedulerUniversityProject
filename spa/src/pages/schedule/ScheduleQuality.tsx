import { useState } from "react";
import { BarChart3, ChevronDown } from "lucide-react";

interface QualityDetail {
  score: number;
  max: number;
  [key: string]: unknown;
}
export interface QualityData {
  score: number;
  grade: string;
  total_entries: number;
  assigned_entries: number;
  details: Record<string, QualityDetail>;
  recommendations: string[];
}

const indicators = [
  ["windows", "Окна"],
  ["late_lessons", "Поздние пары"],
  ["balance", "Равномерность"],
  ["lunch", "Обед"],
  ["progress", "Порядок лекций и семинаров"],
  ["availability", "Доступность"],
] as const;

export function ScheduleQuality({ quality }: { quality: QualityData }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="app-panel schedule-quality">
      <button
        type="button"
        className="schedule-quality__toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <BarChart3 size={18} aria-hidden="true" />
        <span>
          <strong>
            Качество расписания: {quality.score}/100 · {quality.grade}
          </strong>
          <small>
            {quality.assigned_entries} из {quality.total_entries} пар выставлено
          </small>
        </span>
        <ChevronDown size={18} aria-hidden="true" />
      </button>
      {open && (
        <div className="app-section">
          <dl className="schedule-quality__indicators">
            {indicators.map(([key, label]) => {
              const detail = quality.details[key];
              if (!detail) return null;
              return (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>
                    {detail.score}/{detail.max}
                    <progress
                      value={detail.max > 0 ? detail.score / detail.max : 1}
                      max={1}
                      aria-label={label}
                    />
                  </dd>
                </div>
              );
            })}
          </dl>
          {quality.recommendations.length > 0 && (
            <div className="notice notice--warning">
              <strong>Рекомендации</strong>
              <ul className="list-disc pl-4">
                {quality.recommendations.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
