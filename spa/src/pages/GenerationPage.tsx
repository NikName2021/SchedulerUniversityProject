import { CalendarRange, Download, Layers3, Plus, X, Zap } from "lucide-react";
import { API_BASE_URL } from "../api/apiConfig";
import { SubjectRulesPanel } from "../components/SubjectRulesPanel";
import { useFeedback } from "../components/feedbackContext";
import { GroupPicker } from "./generation/GroupPicker";
import { SemesterPlan } from "./generation/SemesterPlan";
import { StreamPreview } from "./generation/StreamPreview";
import { WeeklyDemandDialog } from "./generation/WeeklyDemandDialog";
import { useGeneration } from "./generation/useGeneration";
import "./generation/GenerationPage.css";

const activityTypes = [
  "Лекция",
  "Семинар",
  "Лабораторная",
  "Зачет",
  "Внеучебное мероприятие",
];

export function GenerationPage() {
  const { download } = useFeedback();
  const generation = useGeneration();
  const {
    generationMode,
    selectedPeriod,
    selectedWeekIds,
    selectedGroups,
    enabledTypes,
    startDate,
    endDate,
    newPeriod,
    status,
    editingWeek,
  } = generation;
  const semester = generationMode === "semester";
  const canGenerate = Boolean(
    selectedGroups.length &&
    enabledTypes.length &&
    (semester
      ? selectedPeriod &&
        selectedWeekIds.some((id) => generation.demandCounts[id] > 0)
      : startDate && endDate && startDate <= endDate),
  );

  return (
    <div className="enterprise-page generation-workspace">
      <header className="workspace-header">
        <div>
          <h1>Генератор расписания</h1>
          <p>Настройте состав занятий и период расчёта.</p>
        </div>
        <button
          className="btn-secondary"
          type="button"
          onClick={() =>
            void download(
              `${API_BASE_URL}/api/v1/scheduler/export`,
              "schedule.xlsx",
            )
          }
        >
          <Download size={16} /> Экспорт Excel
        </button>
      </header>
      {status && !editingWeek && (
        <p
          className={`notice notice--${status.type === "error" ? "danger" : status.type}`}
          role={status.type === "error" ? "alert" : "status"}
        >
          {status.msg}
        </p>
      )}
      {generation.isLoading ? (
        <p className="loading-state" role="status">
          Загрузка параметров генерации…
        </p>
      ) : (
        <>
          <div
            className="app-control-row"
            role="group"
            aria-label="Режим расчёта"
          >
            <button
              className="app-toggle"
              type="button"
              aria-pressed={!semester}
              onClick={() => generation.setGenerationMode("week")}
            >
              <CalendarRange size={17} /> Одна неделя
            </button>
            <button
              className="app-toggle"
              type="button"
              aria-pressed={semester}
              onClick={() => generation.setGenerationMode("semester")}
            >
              <Layers3 size={17} /> Весь семестр по неделям
            </button>
          </div>
          <div className="generation-layout">
            <GroupPicker
              groups={generation.groups}
              selected={selectedGroups}
              standaloneCount={generation.standaloneGroups.length}
              standaloneSelected={generation.onlyStandaloneGroupsSelected}
              experimental={generation.experimentalSelection}
              expanding={generation.isExpandingGroups}
              onToggle={generation.handleToggleGroup}
              onToggleStandalone={generation.toggleStandaloneGroups}
              onToggleExperimental={() =>
                void generation.toggleExperimentalGroups()
              }
              onPreview={(group) => void generation.handlePreviewGroup(group)}
            />
            <div className="generation-main">
              <section className="app-panel app-section">
                <h2>Типы занятий для генерации</h2>
                <div className="app-control-row">
                  {activityTypes.map((type) => (
                    <button
                      className="app-toggle"
                      type="button"
                      key={type}
                      aria-pressed={enabledTypes.includes(type)}
                      onClick={() => generation.handleToggleType(type)}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </section>
              <SubjectRulesPanel
                summary={generation.subjectSummary}
                isSummaryLoading={generation.isSummaryLoading}
                groups={selectedGroups}
                enabledTypes={enabledTypes}
                holidays={generation.holidays}
                startDate={startDate}
                endDate={endDate}
                weeks={
                  semester
                    ? selectedPeriod?.weeks.filter((week) =>
                        selectedWeekIds.includes(week.id),
                      ) || []
                    : []
                }
                semester={semester}
                timePreferences={generation.subjectPriorities}
                onTimePreferenceChange={(subject, preference) =>
                  generation.setSubjectPriorities((current) => ({
                    ...current,
                    [subject]: preference,
                  }))
                }
                onSaved={async () => {
                  if (semester && selectedPeriod)
                    await generation.loadDemandCounts(
                      selectedPeriod.weeks,
                      false,
                    );
                }}
              />
              <StreamPreview
                group={generation.previewGroup}
                streams={generation.previewStreams.filter((stream) =>
                  enabledTypes.includes(stream.stream_type),
                )}
                loading={generation.isPreviewLoading}
                onClose={generation.closePreview}
              />
              <div className="generation-period-grid">
                <section className="app-panel app-section">
                  <h2>{semester ? "Учебный период" : "Даты расчёта"}</h2>
                  {semester ? (
                    <>
                      {generation.periods.length > 0 && (
                        <label className="app-field-label">
                          Семестр
                          <select
                            className="app-field"
                            value={selectedPeriod?.id ?? ""}
                            onChange={(event) =>
                              generation.selectPeriod(
                                Number(event.target.value),
                              )
                            }
                          >
                            {generation.periods.map((period) => (
                              <option key={period.id} value={period.id}>
                                {period.name} · {period.starts_on} —{" "}
                                {period.ends_on}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <form
                        className="generation-fields"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void generation.createAcademicPeriod();
                        }}
                      >
                        <label className="app-field-label">
                          Название нового семестра
                          <input
                            className="app-field"
                            required
                            value={newPeriod.name}
                            onChange={(event) =>
                              generation.setNewPeriod({
                                ...newPeriod,
                                name: event.target.value,
                              })
                            }
                          />
                        </label>
                        <div className="generation-date-fields">
                          <label className="app-field-label">
                            Начало семестра
                            <input
                              className="app-field"
                              type="date"
                              required
                              value={newPeriod.starts_on}
                              onChange={(event) =>
                                generation.setNewPeriod({
                                  ...newPeriod,
                                  starts_on: event.target.value,
                                })
                              }
                            />
                          </label>
                          <label className="app-field-label">
                            Конец семестра
                            <input
                              className="app-field"
                              type="date"
                              min={newPeriod.starts_on || undefined}
                              required
                              value={newPeriod.ends_on}
                              onChange={(event) =>
                                generation.setNewPeriod({
                                  ...newPeriod,
                                  ends_on: event.target.value,
                                })
                              }
                            />
                          </label>
                        </div>
                        <button
                          className="btn-secondary justify-self-start"
                          type="submit"
                        >
                          Создать период и недели
                        </button>
                      </form>
                    </>
                  ) : (
                    <div className="generation-date-fields">
                      <label className="app-field-label">
                        Начало
                        <input
                          className="app-field"
                          type="date"
                          value={startDate}
                          onChange={(event) =>
                            generation.setStartDate(event.target.value)
                          }
                        />
                      </label>
                      <label className="app-field-label">
                        Конец
                        <input
                          className="app-field"
                          type="date"
                          min={startDate || undefined}
                          value={endDate}
                          onChange={(event) =>
                            generation.setEndDate(event.target.value)
                          }
                        />
                      </label>
                    </div>
                  )}
                </section>
                <section className="app-panel app-section">
                  <h2>Праздники</h2>
                  <form
                    className="app-control-row items-end"
                    onSubmit={(event) => {
                      event.preventDefault();
                      generation.handleAddHoliday();
                    }}
                  >
                    <label className="app-field-label">
                      Нерабочая дата
                      <input
                        className="app-field"
                        type="date"
                        required
                        value={generation.newHoliday}
                        onChange={(event) =>
                          generation.setNewHoliday(event.target.value)
                        }
                      />
                    </label>
                    <button className="btn-secondary" type="submit">
                      <Plus size={16} /> Добавить
                    </button>
                  </form>
                  <ul className="app-control-row">
                    {generation.holidays.map((day) => (
                      <li key={day} className="generation-holiday">
                        <time dateTime={day}>{day}</time>
                        <button
                          className="button-icon"
                          type="button"
                          aria-label={`Удалить праздник ${day}`}
                          onClick={() => generation.handleRemoveHoliday(day)}
                        >
                          <X size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
              {semester && selectedPeriod && (
                <SemesterPlan
                  period={selectedPeriod}
                  counts={generation.demandCounts}
                  selected={selectedWeekIds}
                  distribution={generation.distributionResult}
                  batch={generation.batchWeeks}
                  busy={generation.isPreparingDemands}
                  canDistribute={Boolean(
                    selectedGroups.length && enabledTypes.length,
                  )}
                  onDistribute={() =>
                    void generation.distributeSemesterDemands()
                  }
                  onSelect={generation.setSelectedWeekIds}
                  onEdit={(week) =>
                    void generation.openWeeklyDemandEditor(week)
                  }
                  onRetry={(item) => void generation.retryBatchWeek(item)}
                />
              )}
              <section className="app-panel app-section generation-launch">
                <h2>{semester ? "Запуск семестра" : "Запуск недели"}</h2>
                <p className="text-text-secondary">
                  Выбрано групп: {selectedGroups.length} · Типов занятий:{" "}
                  {enabledTypes.length}
                  {semester
                    ? ` · Недель с нагрузкой: ${selectedWeekIds.filter((id) => generation.demandCounts[id] > 0).length}`
                    : ""}
                </p>
                <button
                  type="button"
                  className="btn-primary justify-self-start"
                  disabled={!canGenerate || generation.isGenerating}
                  onClick={() => void generation.handleStartGeneration()}
                >
                  <Zap size={16} />{" "}
                  {generation.isGenerating
                    ? "Постановка в очередь…"
                    : semester
                      ? "Запустить выбранные недели"
                      : "Начать расчёт недели"}
                </button>
              </section>
            </div>
          </div>
        </>
      )}
      {editingWeek && (
        <WeeklyDemandDialog
          week={editingWeek}
          demands={generation.weeklyDemands}
          saving={generation.isSavingDemands}
          error={status?.type === "error" ? status.msg : undefined}
          onClose={() => generation.setEditingWeek(null)}
          onSave={() => void generation.saveWeeklyDemands()}
          onChange={(id, patch) =>
            generation.setWeeklyDemands((current) =>
              current.map((item) =>
                item.stream_id === id ? { ...item, ...patch } : item,
              ),
            )
          }
        />
      )}
    </div>
  );
}
