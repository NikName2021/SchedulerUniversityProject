import React, { useCallback, useEffect, useState } from "react";
import { Building2, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { API_BASE_URL } from "../api/apiConfig";

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

export const ReferenceDataPage: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [activityTypes, setActivityTypes] = useState<ActivityType[]>([]);
  const [profiles, setProfiles] = useState<RuleProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
          fetch(`${API_BASE_URL}/api/v1/reference/rooms`),
          fetch(`${API_BASE_URL}/api/v1/reference/activity-types`),
          fetch(`${API_BASE_URL}/api/v1/reference/rule-profiles`),
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

  const createRoom = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    const response = await fetch(`${API_BASE_URL}/api/v1/reference/rooms`, {
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
              <div
                key={profile.id}
                className="rounded-xl border border-border-light p-3"
              >
                <div className="flex justify-between font-bold text-text-primary">
                  <span>{profile.name}</span>
                  {profile.is_default && (
                    <span className="text-xs text-brand">По умолчанию</span>
                  )}
                </div>
                <p className="mt-1 text-xs text-text-secondary">
                  {profile.description ||
                    `${profile.settings.filter((item) => item.enabled).length} активных правил`}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};
