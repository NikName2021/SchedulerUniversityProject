import React, { useCallback, useEffect, useState } from "react";
import {
  Building2,
  CheckCircle2,
  ChevronRight,
  CircleOff,
  Loader2,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react";
import { API_BASE_URL, apiFetch } from "../api/apiConfig";

interface RoomFeature {
  id: number;
  code: string;
  name: string;
}

interface Room {
  id: number;
  code: string;
  name: string | null;
  building_name: string | null;
  capacity: number;
  room_type: string;
  is_active: boolean;
  features: RoomFeature[];
}

interface ActivityType {
  id: number;
  code: string;
  name: string;
  room_type: string | null;
  is_shared_for_groups: boolean;
  is_active: boolean;
}

interface RuleProfile {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
  settings: Array<{ id: number; rule_code: string; enabled: boolean }>;
}

type RuleRuntimeState =
  | "active"
  | "disabled"
  | "temporarily_disabled"
  | "not_implemented";

interface RuleDescription {
  code: string;
  name: string;
  description: string;
  category: string;
  configured_enabled: boolean;
  effective_enabled: boolean;
  is_hard: boolean;
  weight: number;
  configurable: boolean;
  runtime_state: RuleRuntimeState;
  runtime_note: string | null;
}

interface RuleProfileDetails {
  profile: RuleProfile;
  rules: RuleDescription[];
}

const runtimeLabels: Record<RuleRuntimeState, string> = {
  active: "Применяется",
  disabled: "Отключено в профиле",
  temporarily_disabled: "Временно отключено",
  not_implemented: "Еще не подключено",
};

const runtimeStyles: Record<RuleRuntimeState, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  disabled: "border-gray-200 bg-gray-50 text-gray-500",
  temporarily_disabled: "border-amber-200 bg-amber-50 text-amber-700",
  not_implemented: "border-slate-200 bg-slate-50 text-slate-600",
};

export const ReferenceDataPage: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [activityTypes, setActivityTypes] = useState<ActivityType[]>([]);
  const [profiles, setProfiles] = useState<RuleProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openedProfile, setOpenedProfile] = useState<RuleProfile | null>(null);
  const [profileDetails, setProfileDetails] =
    useState<RuleProfileDetails | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [form, setForm] = useState({
    code: "",
    capacity: 30,
    room_type: "mixed",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [roomsResponse, typesResponse, profilesResponse] =
        await Promise.all([
          apiFetch(`${API_BASE_URL}/api/v1/reference/rooms`),
          apiFetch(`${API_BASE_URL}/api/v1/reference/activity-types`),
          apiFetch(`${API_BASE_URL}/api/v1/reference/rule-profiles`),
        ]);
      if (!roomsResponse.ok || !typesResponse.ok || !profilesResponse.ok) {
        throw new Error("Не удалось загрузить справочники");
      }
      setRooms(await roomsResponse.json());
      setActivityTypes(await typesResponse.json());
      setProfiles(await profilesResponse.json());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Ошибка загрузки",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!openedProfile) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenedProfile(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [openedProfile]);

  const openProfile = async (profile: RuleProfile) => {
    setOpenedProfile(profile);
    setProfileDetails(null);
    setProfileError(null);
    setProfileLoading(true);
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/v1/reference/rule-profiles/${profile.id}/details`,
      );
      if (!response.ok) throw new Error("Не удалось загрузить правила профиля");
      setProfileDetails(await response.json());
    } catch (requestError) {
      setProfileError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось загрузить правила профиля",
      );
    } finally {
      setProfileLoading(false);
    }
  };

  const createRoom = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    const response = await apiFetch(`${API_BASE_URL}/api/v1/reference/rooms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, is_active: true, feature_ids: [] }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setError(payload.detail || "Не удалось создать аудиторию");
      return;
    }
    setForm({ code: "", capacity: 30, room_type: "mixed" });
    await load();
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-text-secondary">
        Загрузка базовых данных…
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-text-primary">
            Базовые данные
          </h1>
          <p className="mt-1 text-sm font-medium text-text-secondary">
            Аудитории, виды занятий и профили правил генератора.
          </p>
        </div>
        <button
          onClick={() => void load()}
          className="flex items-center gap-2 rounded-xl border border-border-light bg-white px-4 py-2 text-sm font-bold text-text-secondary hover:text-brand"
        >
          <RefreshCw size={16} /> Обновить
        </button>
      </header>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="overflow-hidden rounded-2xl border border-border-light bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-border-light px-5 py-4 font-extrabold text-text-primary">
            <Building2 size={19} className="text-brand" /> Аудитории
          </div>
          <div className="divide-y divide-border-light">
            {rooms.map((room) => (
              <div
                key={room.id}
                className="grid grid-cols-[1fr_auto_auto] items-center gap-4 px-5 py-4"
              >
                <div>
                  <div className="font-extrabold text-text-primary">
                    {room.code}
                    {room.name ? ` · ${room.name}` : ""}
                  </div>
                  <div className="mt-1 text-xs text-text-secondary">
                    {room.building_name || "Корпус не указан"} ·{" "}
                    {room.features.map((item) => item.name).join(", ") ||
                      "без оснащения"}
                  </div>
                </div>
                <span className="rounded-lg bg-bg-base px-3 py-1 text-xs font-bold text-text-secondary">
                  {room.room_type}
                </span>
                <span className="text-sm font-black text-brand">
                  {room.capacity} мест
                </span>
              </div>
            ))}
          </div>
        </div>

        <form
          onSubmit={createRoom}
          className="h-fit space-y-4 rounded-2xl border border-border-light bg-white p-5 shadow-sm"
        >
          <h2 className="flex items-center gap-2 font-extrabold text-text-primary">
            <Plus size={18} className="text-brand" /> Новая аудитория
          </h2>
          <label className="block text-xs font-bold text-text-secondary">
            Код
            <input
              required
              value={form.code}
              onChange={(event) =>
                setForm({ ...form, code: event.target.value })
              }
              className="mt-1 w-full rounded-xl border border-border-light px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </label>
          <label className="block text-xs font-bold text-text-secondary">
            Вместимость
            <input
              required
              min={0}
              type="number"
              value={form.capacity}
              onChange={(event) =>
                setForm({ ...form, capacity: Number(event.target.value) })
              }
              className="mt-1 w-full rounded-xl border border-border-light px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </label>
          <label className="block text-xs font-bold text-text-secondary">
            Тип
            <select
              value={form.room_type}
              onChange={(event) =>
                setForm({ ...form, room_type: event.target.value })
              }
              className="mt-1 w-full rounded-xl border border-border-light bg-white px-3 py-2 text-sm outline-none focus:border-brand"
            >
              <option value="mixed">Универсальная</option>
              <option value="lec">Лекционная</option>
              <option value="sem">Семинарская</option>
              <option value="lab">Лаборатория</option>
            </select>
          </label>
          <button className="w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-extrabold text-white shadow-sm hover:opacity-90">
            Добавить
          </button>
        </form>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-2xl border border-border-light bg-white p-5 shadow-sm">
          <h2 className="mb-4 font-extrabold text-text-primary">
            Виды занятий
          </h2>
          <div className="flex flex-wrap gap-2">
            {activityTypes.map((item) => (
              <span
                key={item.id}
                className="rounded-xl border border-border-light bg-bg-base px-3 py-2 text-xs font-bold text-text-secondary"
              >
                {item.name}
                {item.is_shared_for_groups ? " · общий поток" : ""}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border-light bg-white p-5 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 font-extrabold text-text-primary">
            <ShieldCheck size={18} className="text-brand" /> Профили правил
          </h2>
          <div className="space-y-3">
            {profiles.map((profile) => (
              <button
                type="button"
                key={profile.id}
                onClick={() => void openProfile(profile)}
                className="group w-full rounded-xl border border-border-light p-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/40"
              >
                <div className="flex items-center justify-between gap-3 font-bold text-text-primary">
                  <span>{profile.name}</span>
                  <span className="flex items-center gap-3">
                    {profile.is_default && (
                      <span className="text-xs text-brand">По умолчанию</span>
                    )}
                    <ChevronRight
                      size={17}
                      className="text-text-tertiary transition-transform group-hover:translate-x-0.5 group-hover:text-brand"
                    />
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-secondary">
                  {profile.description ||
                    `${profile.settings.filter((item) => item.enabled).length} активных правил`}
                </p>
                <p className="mt-2 text-xs font-bold text-brand">
                  Посмотреть используемые правила
                </p>
              </button>
            ))}
          </div>
        </div>
      </section>

      {openedProfile && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-slate-950/35"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setOpenedProfile(null);
          }}
        >
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="rule-profile-title"
            className="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl"
          >
            <header className="border-b border-border-light px-6 py-5 sm:px-8">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-xs font-extrabold uppercase tracking-wide text-brand">
                    <ShieldCheck size={17} /> Профиль правил
                  </div>
                  <h2
                    id="rule-profile-title"
                    className="text-2xl font-black text-text-primary"
                  >
                    {openedProfile.name}
                  </h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    {openedProfile.description || "Описание профиля не указано"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpenedProfile(null)}
                  aria-label="Закрыть описание профиля"
                  className="rounded-xl border border-border-light p-2 text-text-secondary hover:bg-bg-base hover:text-text-primary"
                >
                  <X size={20} />
                </button>
              </div>

              {profileDetails && (
                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-bg-light px-4 py-3">
                    <div className="text-2xl font-black text-text-primary">
                      {
                        profileDetails.rules.filter(
                          (rule) => rule.effective_enabled,
                        ).length
                      }
                    </div>
                    <div className="text-xs font-bold text-text-secondary">
                      применяются сейчас
                    </div>
                  </div>
                  <div className="rounded-xl bg-bg-light px-4 py-3">
                    <div className="text-2xl font-black text-text-primary">
                      {
                        profileDetails.rules.filter((rule) => rule.is_hard)
                          .length
                      }
                    </div>
                    <div className="text-xs font-bold text-text-secondary">
                      жестких правил
                    </div>
                  </div>
                  <div className="col-span-2 rounded-xl bg-blue-50 px-4 py-3 sm:col-span-1">
                    <div className="flex items-center gap-2 font-black text-brand">
                      <SlidersHorizontal size={18} /> Просмотр
                    </div>
                    <div className="mt-1 text-xs font-bold text-blue-700/75">
                      Настройка профилей будет добавлена позже
                    </div>
                  </div>
                </div>
              )}
            </header>

            <div className="flex-1 overflow-y-auto px-6 py-5 sm:px-8">
              {profileLoading && (
                <div className="flex items-center justify-center gap-3 py-20 font-bold text-text-secondary">
                  <Loader2 size={22} className="animate-spin text-brand" />
                  Загружаем правила…
                </div>
              )}

              {profileError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 font-semibold text-red-700">
                  {profileError}
                </div>
              )}

              {profileDetails && (
                <div className="space-y-4">
                  {profileDetails.rules.map((rule) => (
                    <article
                      key={rule.code}
                      className={`rounded-2xl border p-4 ${
                        rule.effective_enabled
                          ? "border-border-light bg-white"
                          : "border-gray-200 bg-gray-50/60"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="mb-1 text-[11px] font-extrabold uppercase tracking-wide text-text-tertiary">
                            {rule.category} · {rule.code}
                          </div>
                          <h3 className="font-extrabold text-text-primary">
                            {rule.name}
                          </h3>
                        </div>
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-extrabold ${runtimeStyles[rule.runtime_state]}`}
                        >
                          {rule.runtime_state === "active" ? (
                            <CheckCircle2 size={14} />
                          ) : rule.runtime_state === "temporarily_disabled" ? (
                            <TriangleAlert size={14} />
                          ) : (
                            <CircleOff size={14} />
                          )}
                          {runtimeLabels[rule.runtime_state]}
                        </span>
                      </div>

                      <p className="mt-2 text-sm leading-6 text-text-secondary">
                        {rule.description}
                      </p>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="inline-flex items-center gap-1 rounded-lg bg-bg-light px-2.5 py-1 text-xs font-bold text-text-secondary">
                          {rule.is_hard ? (
                            <LockKeyhole size={13} />
                          ) : (
                            <SlidersHorizontal size={13} />
                          )}
                          {rule.is_hard
                            ? "Жесткое правило"
                            : "Критерий качества"}
                        </span>
                        {!rule.is_hard && rule.configurable && (
                          <span className="rounded-lg bg-bg-light px-2.5 py-1 text-xs font-bold text-text-secondary">
                            Вес: {rule.weight} из 10
                          </span>
                        )}
                        {!rule.configurable && (
                          <span className="rounded-lg bg-blue-50 px-2.5 py-1 text-xs font-bold text-brand">
                            Системное
                          </span>
                        )}
                      </div>

                      {rule.runtime_note && (
                        <p className="mt-3 rounded-xl bg-bg-light px-3 py-2 text-xs font-semibold text-text-secondary">
                          {rule.runtime_note}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
};
