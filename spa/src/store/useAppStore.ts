import { create } from "zustand";
import { MockAPI } from "../api/mockService";
import type { Stream } from "../api/mockService";
import { API_BASE_URL, apiFetch } from "../api/apiConfig";
import {
  getSlotsForInterval,
  minutesToTime,
  PAIR_TIMES,
  timeToMinutes,
} from "../utils/scheduleTime";

export { getSlotsForInterval, minutesToTime, PAIR_TIMES, timeToMinutes };

export interface TimeInterval {
  id: string;
  start: string; // "HH:MM"
  end: string; // "HH:MM"
  type: "recurring" | "specific";
  day?: number; // JS weekday (0=Sun, 1=Mon, ..., 6=Sat) for recurring
  date?: string; // "YYYY-MM-DD" for specific
}

export interface TeacherRestrictions {
  mode: "blacklist" | "whitelist";
  specific: string[]; // YYYY-MM-DD-Slot
  recurring: string[]; // Weekday-Slot (e.g. "4-1")
  intervals: TimeInterval[];
}

export interface Teacher {
  id: string;
  name: string;
  dept: string;
  restrictions: TeacherRestrictions;
}

interface AppState {
  // Data
  teachers: Teacher[];
  streams: Stream[];
  isLoading: boolean;
  error: string | null;

  // Selection
  selectedTeacherId: string | null;

  // Job Status
  isGenerating: boolean;
  jobId: string | null;
  progress: number;
  logs: string[];

  // Actions
  fetchInitialData: () => Promise<void>;
  setSelectedTeacherId: (id: string | null) => void;
  updateJobProgress: (jobId: string) => Promise<void>;
  resetJob: () => void;
  saveTeacherRestrictions: (teacherId: string) => Promise<void>;

  // Advanced Actions
  setRestrictionMode: (
    teacherId: string,
    mode: "blacklist" | "whitelist",
  ) => void;
  toggleRestriction: (
    teacherId: string,
    type: "specific" | "recurring",
    key: string,
  ) => void;
  addInterval: (
    teacherId: string,
    intervalData: Omit<TimeInterval, "id">,
  ) => void;
  removeInterval: (teacherId: string, intervalId: string) => void;
  startGeneration: () => Promise<void>;
}

export const useAppStore = create<AppState>((set) => ({
  teachers: [],
  streams: [],
  isLoading: false,
  error: null,

  selectedTeacherId: null,

  isGenerating: false,
  jobId: null,
  progress: 0,
  logs: [],

  fetchInitialData: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiFetch(`${API_BASE_URL}/api/v1/scheduler/teachers`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const payload: unknown = await res.json();
      if (!Array.isArray(payload)) {
        throw new Error("Некорректный ответ сервера");
      }
      const rawTeachers = payload;

      // Parse raw backend data into structured restrictions
      const teachers: Teacher[] = rawTeachers.map(
        (t: { id: string; name: string; dept: string; blocked: unknown }) => {
          let restrictions: TeacherRestrictions = {
            mode: "blacklist",
            specific: [],
            recurring: [],
            intervals: [],
          };
          if (
            t.blocked &&
            typeof t.blocked === "object" &&
            !Array.isArray(t.blocked)
          ) {
            const b = t.blocked as Partial<TeacherRestrictions>;
            restrictions = {
              mode:
                b.mode === "whitelist" || b.mode === "blacklist"
                  ? b.mode
                  : "blacklist",
              specific: Array.isArray(b.specific)
                ? b.specific.filter(
                    (value): value is string => typeof value === "string",
                  )
                : [],
              recurring: Array.isArray(b.recurring)
                ? b.recurring.filter(
                    (value): value is string => typeof value === "string",
                  )
                : [],
              intervals: Array.isArray(b.intervals)
                ? (b.intervals as TimeInterval[])
                : [],
            };
          } else if (Array.isArray(t.blocked)) {
            // Old format migration or simple list
            restrictions.specific = t.blocked as string[];
          }
          return {
            id: t.id,
            name: t.name,
            dept: t.dept,
            restrictions,
          } as Teacher;
        },
      );

      set({
        teachers,
        isLoading: false,
        selectedTeacherId: teachers[0]?.id || null,
      });
    } catch {
      set({
        error: "Не удалось загрузить данные преподавателей",
        isLoading: false,
      });
    }
  },

  setSelectedTeacherId: (id) => set({ selectedTeacherId: id }),

  setRestrictionMode: (teacherId, mode) => {
    set((state) => ({
      teachers: state.teachers.map((t) =>
        t.id === teacherId
          ? { ...t, restrictions: { ...t.restrictions, mode } }
          : t,
      ),
    }));
  },

  toggleRestriction: (teacherId, type, key) => {
    set((state) => ({
      teachers: state.teachers.map((t) => {
        if (t.id !== teacherId) return t;
        const list = [...t.restrictions[type]];
        const index = list.indexOf(key);
        if (index > -1) list.splice(index, 1);
        else list.push(key);

        return {
          ...t,
          restrictions: { ...t.restrictions, [type]: list },
        };
      }),
    }));
  },

  addInterval: (teacherId, intervalData) => {
    set((state) => ({
      teachers: state.teachers.map((t) => {
        if (t.id !== teacherId) return t;

        const interval: TimeInterval = {
          ...intervalData,
          id: Math.random().toString(36).substring(2, 11),
        };

        const newIntervals = [...t.restrictions.intervals, interval];
        const slots = getSlotsForInterval(interval.start, interval.end);

        const newRecurring = [...t.restrictions.recurring];
        const newSpecific = [...t.restrictions.specific];

        for (const slot of slots) {
          if (interval.type === "recurring" && interval.day !== undefined) {
            const key = `${interval.day}-${slot}`;
            if (!newRecurring.includes(key)) newRecurring.push(key);
          } else if (interval.type === "specific" && interval.date) {
            const key = `${interval.date}-${slot}`;
            if (!newSpecific.includes(key)) newSpecific.push(key);
          }
        }

        return {
          ...t,
          restrictions: {
            ...t.restrictions,
            intervals: newIntervals,
            recurring: newRecurring,
            specific: newSpecific,
          },
        };
      }),
    }));
  },

  removeInterval: (teacherId, intervalId) => {
    set((state) => ({
      teachers: state.teachers.map((t) => {
        if (t.id !== teacherId) return t;

        const interval = t.restrictions.intervals.find(
          (i) => i.id === intervalId,
        );
        if (!interval) return t;

        const newIntervals = t.restrictions.intervals.filter(
          (i) => i.id !== intervalId,
        );

        const slotsToRemove = getSlotsForInterval(interval.start, interval.end);

        const newRecurring = t.restrictions.recurring.filter((key) => {
          if (interval.type !== "recurring") return true;
          const parts = key.split("-");
          const d = Number(parts[0]);
          const s = Number(parts[1]);
          return !(d === interval.day && slotsToRemove.includes(s));
        });

        const newSpecific = t.restrictions.specific.filter((key) => {
          if (interval.type !== "specific") return true;
          const parts = key.split("-");
          const dateStr = parts.slice(0, 3).join("-");
          const s = Number(parts[3]);
          return !(dateStr === interval.date && slotsToRemove.includes(s));
        });

        return {
          ...t,
          restrictions: {
            ...t.restrictions,
            intervals: newIntervals,
            recurring: newRecurring,
            specific: newSpecific,
          },
        };
      }),
    }));
  },

  startGeneration: async () => {
    set({ isGenerating: true, progress: 0, logs: ["Инициализация..."] });
    try {
      const { jobId } = await MockAPI.startGeneration();
      set({ jobId });
    } catch {
      set({ error: "Failed to start generation", isGenerating: false });
    }
  },

  updateJobProgress: async (jobId) => {
    try {
      const { progress, logs } = await MockAPI.checkStatus(jobId);
      set({ progress, logs });
      if (progress >= 100) {
        set({ isGenerating: false, jobId: null });
      }
    } catch (err) {
      console.error("Progress update failed", err);
    }
  },

  resetJob: () =>
    set({ isGenerating: false, jobId: null, progress: 0, logs: [] }),

  saveTeacherRestrictions: async (teacherId: string) => {
    const state = useAppStore.getState();
    const teacher = state.teachers.find((t) => t.id === teacherId);
    if (!teacher) return;

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/teachers/${teacherId}/restrictions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ restrictions: teacher.restrictions }),
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        set({
          error:
            payload?.detail || "Не удалось сохранить ограничения преподавателя",
        });
        return;
      }
      set({ error: null });
    } catch (e) {
      console.error("Failed to save restrictions", e);
      set({ error: "Не удалось сохранить ограничения преподавателя" });
    }
  },
}));
