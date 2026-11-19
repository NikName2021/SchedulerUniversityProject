import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  ChevronDown,
  Loader2,
  Minus,
  Plus,
  Settings2,
  Zap,
} from "lucide-react";
import {
  checkSubjectRule,
  fetchSubjectRules,
  saveSubjectRule,
} from "../api/subjectRules";
import { useAuth } from "../auth/useAuth";
import {
  SUBJECT_WEEKDAYS,
  applyRulePreset,
  ruleLessonCount,
  ruleValidationError,
  subjectRuleContextKey,
  subjectRuleSummary,
} from "../utils/subjectRules";
import type {
  SubjectRuleCheck,
  SubjectRuleConfig,
  SubjectRuleContext,
  SubjectRuleItem,
} from "../utils/subjectRules";
import "./SubjectRulesPanel.css";

interface RuleWeek {
  id: number;
  sequence_number: number;
  starts_on: string;
  ends_on: string;
}

interface Props {
  summary: Record<string, string[]>;
  isSummaryLoading: boolean;
  groups: string[];
  enabledTypes: string[];
  holidays: string[];
  startDate: string;
  endDate: string;
  weeks: RuleWeek[];
  semester: boolean;
  timePreferences: Record<string, string>;
  onTimePreferenceChange: (
    subject: string,
    preference: SubjectRuleConfig["time_preference"],
  ) => void;
  onSaved: () => Promise<void>;
}

const timeLabels = { morning: "Утро", day: "День", evening: "Вечер" };
const activityLabels = { lec: "Лекция", sem: "Семинар", lab: "Лабораторная" };
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Нет связи с сервером";

export function SubjectRulesPanel(props: Props) {
  const { user } = useAuth();
  const sortedWeeks = [...props.weeks].sort((a, b) =>
    a.starts_on.localeCompare(b.starts_on),
  );
  const contextKey = subjectRuleContextKey({
    groups: props.groups,
    start_date: props.semester
      ? sortedWeeks[0]?.starts_on || ""
      : props.startDate,
    end_date: props.semester
      ? sortedWeeks.at(-1)?.ends_on || ""
      : props.endDate,
    week_ids: props.semester ? sortedWeeks.map((week) => week.id) : [],
    enabled_types: props.enabledTypes,
    holidays: props.holidays,
  });
  const context = useMemo(
    () => JSON.parse(contextKey) as SubjectRuleContext,
    [contextKey],
  );
  return (
    <SubjectRuleList
      key={user?.id}
      {...props}
      context={context}
      sortedWeeks={sortedWeeks}
    />
  );
}

function SubjectRuleList({
  context,
  sortedWeeks,
  ...props
}: Props & { context: SubjectRuleContext; sortedWeeks: RuleWeek[] }) {
  const [active, setActive] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [response, setResponse] = useState<{
    context: SubjectRuleContext;
    reload: number;
    items: SubjectRuleItem[];
    error?: string;
  } | null>(null);
  const [notice, setNotice] = useState<{
    context: SubjectRuleContext;
    message: string;
    error?: boolean;
  } | null>(null);
  const [reload, setReload] = useState(0);
  const currentResponse =
    response?.context === context && response.reload === reload
      ? response
      : null;
  const currentNotice = notice?.context === context ? notice : null;
  const loadError = currentResponse?.error;
  const ready = Boolean(
    context.groups.length &&
    context.enabled_types.length &&
    context.start_date &&
    context.end_date,
  );

  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    fetchSubjectRules(context, controller.signal)
      .then(({ items }) => {
        if (!controller.signal.aborted) setResponse({ context, reload, items });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setResponse({ context, reload, items: [], error: errorText(error) });
      });
    return () => controller.abort();
  }, [context, ready, reload]);

  const itemMap = new Map(
    currentResponse?.items.map((item) => [item.subject, item]),
  );
  const seen = new Set<string>();
  const sections = Object.entries(props.summary)
    .map(
      ([direction, subjects]) =>
        [
          direction,
          subjects.filter((subject) => {
            if (seen.has(subject)) return false;
            seen.add(subject);
            return true;
          }),
        ] as const,
    )
    .filter(([, subjects]) => subjects.length > 0);

  return (
    <section
      className="app-panel app-section subject-rules-panel"
      aria-label="Приоритеты и правила предметов"
    >
      <div className="rule-panel-header">
        <div className="rule-panel-icon">
          <Zap size={20} />
        </div>
        <div>
          <h2>Приоритет предметов</h2>
          <p>Время, дни проведения и состав занятий на неделю</p>
        </div>
      </div>
      <div className="subject-rules-list">
        {currentNotice && (
          <p
            role={currentNotice.error ? "alert" : "status"}
            className={
              currentNotice.error ? "subject-rule-error" : "subject-rule-notice"
            }
          >
            {currentNotice.message}
          </p>
        )}
        {loadError && (
          <div role="alert" className="subject-rule-error">
            {loadError}{" "}
            <button
              type="button"
              onClick={() => setReload((value) => value + 1)}
            >
              Повторить
            </button>
          </div>
        )}
        {!ready ? (
          <p className="subject-rules-empty">
            {props.groups.length === 0
              ? "Выберите группы, чтобы настроить предметы"
              : props.semester
                ? "Выберите учебные недели и типы занятий"
                : "Выберите даты и типы занятий"}
          </p>
        ) : !currentResponse || props.isSummaryLoading ? (
          <p className="subject-rules-empty" role="status">
            <Loader2 size={15} className="animate-spin" /> Загрузка правил
            предметов…
          </p>
        ) : sections.length === 0 ? (
          <p className="subject-rules-empty">
            Для выбранных групп и типов нет предметов
          </p>
        ) : (
          sections.map(([direction, subjects]) => (
            <div className="subject-rule-direction-group" key={direction}>
              <button
                type="button"
                className="rule-direction"
                aria-expanded={!collapsed.includes(direction)}
                onClick={() =>
                  setCollapsed((current) =>
                    current.includes(direction)
                      ? current.filter((value) => value !== direction)
                      : [...current, direction],
                  )
                }
              >
                <strong>{direction}</strong>
                <span>{subjects.length} предметов</span>
                <ChevronDown size={14} />
              </button>
              {!collapsed.includes(direction) &&
                subjects.map((subject) => {
                  const item = itemMap.get(subject);
                  const open = active === subject;
                  const preference = item?.saved
                    ? item.rule.time_preference
                    : props.timePreferences[subject] === "morning" ||
                        props.timePreferences[subject] === "evening"
                      ? (props.timePreferences[
                          subject
                        ] as SubjectRuleConfig["time_preference"])
                      : "day";
                  return (
                    <article className="rule-subject" key={subject}>
                      <div className="rule-subject-heading">
                        <div>
                          <strong>{subject}</strong>
                          <small>
                            {item?.groups.join(", ") || props.groups.join(", ")}
                          </small>
                        </div>
                        {item?.saved ? (
                          <span className="rule-current-time">
                            {timeLabels[preference]}
                          </span>
                        ) : (
                          <select
                            className="rule-current-time"
                            aria-label={`Желаемое время: ${subject}`}
                            value={preference}
                            onChange={(event) =>
                              props.onTimePreferenceChange(
                                subject,
                                event.target
                                  .value as SubjectRuleConfig["time_preference"],
                              )
                            }
                          >
                            {Object.entries(timeLabels).map(
                              ([value, label]) => (
                                <option value={value} key={value}>
                                  {label}
                                </option>
                              ),
                            )}
                          </select>
                        )}
                        <button
                          type="button"
                          className={`rule-edit${open ? " active" : ""}`}
                          aria-label={`Настроить ${subject}`}
                          aria-expanded={open}
                          disabled={!item || Boolean(loadError)}
                          onClick={() => {
                            setActive(open ? null : subject);
                            setNotice(null);
                          }}
                        >
                          <Settings2 size={14} />
                          {open ? "Настройки" : "Настроить"}
                        </button>
                      </div>
                      {item?.mixed && (
                        <p className="rule-help rule-mixed">
                          В группах или неделях заданы разные правила.
                          Сохранение применит новую схему к указанной области.
                        </p>
                      )}
                      {open && item ? (
                        <SubjectRuleEditor
                          key={subject}
                          item={item}
                          context={{ ...context, groups: item.groups }}
                          weeks={sortedWeeks}
                          initialRule={{
                            ...item.rule,
                            time_preference: preference,
                          }}
                          onCancel={() => setActive(null)}
                          onSaved={() => {
                            void props.onSaved().catch(() => {
                              setNotice({
                                context,
                                message:
                                  "Не удалось обновить сведения о недельной нагрузке",
                                error: true,
                              });
                            });
                            setReload((current) => current + 1);
                            setActive(null);
                            setNotice({
                              context,
                              message: `Правило для «${subject}» сохранено`,
                            });
                          }}
                        />
                      ) : (
                        item && (
                          <div className="rule-summary">
                            {item.saved ? (
                              <>
                                <span>{subjectRuleSummary(item.rule)}</span>
                                <span>
                                  {item.rule.weekdays.length
                                    ? item.rule.weekdays
                                        .map((day) => SUBJECT_WEEKDAYS[day])
                                        .join(", ")
                                    : "Любые дни"}{" "}
                                  · {item.rule.days_per_week} дн.
                                </span>
                                <span className="rule-soft">
                                  {item.rule.days_hard
                                    ? "Обязательно"
                                    : "Желательно"}
                                </span>
                              </>
                            ) : (
                              <span>
                                По учебной нагрузке · дни не настроены
                              </span>
                            )}
                          </div>
                        )
                      )}
                    </article>
                  );
                })}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

interface EditorProps {
  item: SubjectRuleItem;
  context: SubjectRuleContext;
  weeks: RuleWeek[];
  initialRule: SubjectRuleConfig;
  onCancel: () => void;
  onSaved: () => void;
}

function SubjectRuleEditor({
  item,
  context,
  weeks,
  initialRule,
  onCancel,
  onSaved,
}: EditorProps) {
  const id = useId();
  const [rule, setRule] = useState<SubjectRuleConfig>(initialRule);
  const [scope, setScope] = useState("selected");
  const [checked, setChecked] = useState<{
    key: string;
    result?: SubjectRuleCheck;
    error?: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const saveController = useRef<AbortController | null>(null);
  const lectureInput = useRef<HTMLInputElement>(null);
  const selectedPreset =
    rule.lectures === 1 && rule.laboratories === 0 ? rule.seminars : 0;
  const localError = ruleValidationError(rule);
  const total = ruleLessonCount(rule);
  const selectedWeek = weeks.find((week) => String(week.id) === scope);
  const effectiveKey = subjectRuleContextKey(
    selectedWeek
      ? {
          ...context,
          start_date: selectedWeek.starts_on,
          end_date: selectedWeek.ends_on,
          week_ids: [selectedWeek.id],
        }
      : context,
  );
  const effectiveContext = useMemo(
    () => JSON.parse(effectiveKey) as SubjectRuleContext,
    [effectiveKey],
  );

  const checkKey = JSON.stringify([effectiveKey, rule, retry]);
  const currentCheck = checked?.key === checkKey ? checked : null;
  const result = currentCheck?.result;
  const checking = !localError && !currentCheck;

  useEffect(() => {
    if (localError) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      checkSubjectRule(effectiveContext, item.subject, rule, controller.signal)
        .then((value) => {
          if (!controller.signal.aborted) {
            setChecked({ key: checkKey, result: value });
            setRequestError(null);
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted)
            setChecked({ key: checkKey, error: errorText(error) });
        });
    }, 450);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [checkKey, rule, effectiveContext, item.subject, localError]);

  useEffect(() => () => saveController.current?.abort(), []);

  const save = async () => {
    if (!result?.can_save || checking || localError || saving) return;
    const controller = new AbortController();
    saveController.current = controller;
    setSaving(true);
    setRequestError(null);
    try {
      const checked = await saveSubjectRule(
        effectiveContext,
        item.subject,
        rule,
        controller.signal,
      );
      if (!controller.signal.aborted && checked.can_save) onSaved();
    } catch (error) {
      if (!controller.signal.aborted) {
        setRequestError(errorText(error));
      }
    } finally {
      if (!controller.signal.aborted) setSaving(false);
    }
  };

  const updateCount = (
    field: "lectures" | "seminars" | "laboratories",
    count: number,
  ) =>
    setRule((current) => {
      const next = {
        ...current,
        [field]: Math.min(14, Math.max(0, Number.isFinite(count) ? count : 0)),
      };
      next.days_per_week = Math.min(
        current.days_per_week,
        Math.max(1, ruleLessonCount(next)),
      );
      return next;
    });
  const firstGroup = item.groups[0];
  const preview =
    result?.preview.filter((entry) => entry.groups.includes(firstGroup)) || [];
  const previewDates = [...new Set(preview.map((entry) => entry.date))].sort();
  const checkError = currentCheck?.error || requestError;
  const errors = localError
    ? [localError]
    : checkError
      ? [checkError]
      : result?.errors || [];

  return (
    <div className="rule-expanded" aria-busy={saving}>
      {errors.length > 0 && (
        <div className="rule-conflict" role="alert">
          <AlertTriangle size={17} />
          <div>
            <strong>
              {localError
                ? "Проверьте настройки"
                : checkError
                  ? "Не удалось проверить правило"
                  : "Выбранные условия несовместимы"}
            </strong>
            {errors.map((error) => (
              <p key={error}>{error}</p>
            ))}
            {checkError && (
              <button
                type="button"
                className="rule-retry"
                onClick={() => {
                  setRequestError(null);
                  setRetry((value) => value + 1);
                }}
              >
                Повторить проверку
              </button>
            )}
          </div>
        </div>
      )}
      <fieldset disabled={saving}>
        <legend className="sr-only">Настройки предмета {item.subject}</legend>
        <div className="rule-section-label">Состав занятий на неделю</div>
        <div className="rule-presets">
          {([1, 2] as const).map((seminars) => (
            <button
              key={seminars}
              type="button"
              aria-pressed={selectedPreset === seminars}
              className={selectedPreset === seminars ? "selected" : ""}
              onClick={() =>
                setRule((current) => applyRulePreset(current, seminars))
              }
            >
              {seminars === 1
                ? "1 лекция + 1 семинар"
                : "1 лекция + 2 семинара"}
            </button>
          ))}
          <button type="button" onClick={() => lectureInput.current?.focus()}>
            Свой вариант
          </button>
        </div>
        <div className="rule-counter-grid">
          {(
            [
              ["lectures", "Лекции"],
              ["seminars", "Семинары"],
              ["laboratories", "Лабораторные"],
            ] as const
          ).map(([field, label]) => (
            <div className="rule-field" key={field}>
              <label htmlFor={`${id}-${field}`}>{label}</label>
              <div className="rule-stepper">
                <button
                  type="button"
                  aria-label={`Уменьшить: ${label}`}
                  disabled={rule[field] <= 0}
                  onClick={() => updateCount(field, rule[field] - 1)}
                >
                  <Minus size={13} />
                </button>
                <input
                  ref={field === "lectures" ? lectureInput : undefined}
                  id={`${id}-${field}`}
                  type="number"
                  min={0}
                  max={14}
                  step={1}
                  value={rule[field]}
                  onChange={(event) =>
                    updateCount(field, Number(event.target.value))
                  }
                />
                <button
                  type="button"
                  aria-label={`Увеличить: ${label}`}
                  disabled={rule[field] >= 14}
                  onClick={() => updateCount(field, rule[field] + 1)}
                >
                  <Plus size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="rule-two-cols">
          <label className="rule-field">
            <span>Учебных дней в неделю</span>
            <select
              value={rule.days_per_week}
              onChange={(event) =>
                setRule({ ...rule, days_per_week: Number(event.target.value) })
              }
            >
              {[1, 2, 3, 4, 5, 6].map((day) => (
                <option value={day} key={day} disabled={day > total}>
                  {day} {day === 1 ? "день" : day < 5 ? "дня" : "дней"}
                </option>
              ))}
            </select>
          </label>
          <label className="rule-field">
            <span>Желаемое время</span>
            <select
              value={rule.time_preference}
              onChange={(event) =>
                setRule({
                  ...rule,
                  time_preference: event.target
                    .value as SubjectRuleConfig["time_preference"],
                })
              }
            >
              {Object.entries(timeLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="rule-section-label" id={`${id}-days`}>
          Дни проведения
        </div>
        <div
          className="rule-weekdays"
          role="group"
          aria-labelledby={`${id}-days`}
        >
          {SUBJECT_WEEKDAYS.map((day, index) => (
            <button
              type="button"
              key={day}
              aria-pressed={rule.weekdays.includes(index)}
              className={rule.weekdays.includes(index) ? "selected" : ""}
              onClick={() =>
                setRule({
                  ...rule,
                  weekdays: rule.weekdays.includes(index)
                    ? rule.weekdays.filter((value) => value !== index)
                    : [...rule.weekdays, index].sort(),
                })
              }
            >
              {day}
            </button>
          ))}
        </div>
        <p className="rule-help">
          {total} пар в неделю · {rule.days_per_week} учебных дней.{" "}
          {rule.weekdays.length === 0
            ? "Дни определит генератор."
            : "Пары и число учебных дней — разные настройки."}
        </p>
        <div className="rule-order">
          <label>
            <input
              type="checkbox"
              checked={rule.lecture_before_practice}
              onChange={(event) =>
                setRule({
                  ...rule,
                  lecture_before_practice: event.target.checked,
                })
              }
            />
            Лекция перед семинарами
          </label>
        </div>
        <div className="rule-two-cols">
          <label className="rule-field">
            <span>Как учитывать дни</span>
            <select
              value={rule.days_hard ? "hard" : "soft"}
              onChange={(event) =>
                setRule({ ...rule, days_hard: event.target.value === "hard" })
              }
            >
              <option value="hard">Обязательно</option>
              <option value="soft">Желательно</option>
            </select>
          </label>
          <label className="rule-field">
            <span>Период действия</span>
            <select
              value={scope}
              onChange={(event) => setScope(event.target.value)}
            >
              <option value="selected">
                {weeks.length
                  ? "Все выбранные недели"
                  : "Текущая учебная неделя"}
              </option>
              {weeks.length > 1 &&
                weeks.map((week) => (
                  <option value={week.id} key={week.id}>
                    Неделя {week.sequence_number} · {week.starts_on}
                  </option>
                ))}
            </select>
          </label>
        </div>
      </fieldset>
      <div className="rule-week-preview">
        <div>
          <CalendarDays size={15} />
          <strong>
            Предварительное распределение{firstGroup ? ` · ${firstGroup}` : ""}
          </strong>
        </div>
        {checking ? (
          <p role="status">
            <Loader2 size={13} className="animate-spin" /> Проверяем доступность
            и нагрузку…
          </p>
        ) : previewDates.length ? (
          <div className="rule-preview-days">
            {previewDates.map((day) => (
              <span key={day}>
                <b>
                  {
                    SUBJECT_WEEKDAYS[
                      (new Date(`${day}T12:00:00`).getDay() + 6) % 7
                    ]
                  }{" "}
                  {day.slice(8, 10)}.{day.slice(5, 7)}
                </b>
                {preview
                  .filter((entry) => entry.date === day)
                  .sort((a, b) => a.lesson_number - b.lesson_number)
                  .map((entry) => (
                    <small key={`${entry.type}:${entry.lesson_number}`}>
                      {entry.lesson_number} пара · {activityLabels[entry.type]}
                    </small>
                  ))}
              </span>
            ))}
          </div>
        ) : (
          <p>Распределение появится после успешной проверки.</p>
        )}
      </div>
      {result?.warnings.map((warning) => (
        <p role="status" className="rule-warning" key={warning}>
          {warning}
        </p>
      ))}
      <p className="rule-help">
        Проверяется выбранный предмет. Совместимость со всем расписанием
        определится при полном расчёте.
        {weeks.length > 0
          ? " При сохранении обновится нагрузка выбранных недель."
          : ""}
      </p>
      <div className="rule-bottom">
        <span role="status">
          {result?.can_save && !checking && !checkError ? (
            <>
              <Check size={13} />
              {total} пар · учебный план не превышен
            </>
          ) : checking ? (
            "Проверка…"
          ) : (
            "Проверьте условия"
          )}
        </span>
        <button
          type="button"
          className="btn-secondary"
          disabled={saving}
          onClick={onCancel}
        >
          Отмена
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={
            saving ||
            checking ||
            !result?.can_save ||
            Boolean(localError) ||
            Boolean(checkError)
          }
          onClick={() => void save()}
        >
          {saving ? (
            <>
              <Loader2 size={12} className="animate-spin" /> Сохраняем…
            </>
          ) : (
            "Сохранить"
          )}
        </button>
      </div>
    </div>
  );
}
