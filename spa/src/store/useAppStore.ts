import { create } from "zustand";
import { MockAPI } from "../api/mockService";
import type { Stream } from "../api/mockService";
import { API_BASE_URL } from "../api/apiConfig";

export interface TeacherRestrictions {
  mode: "blacklist" | "whitelist";
  specific: string[]; // YYYY-MM-DD-Slot
  recurring: string[]; // Weekday-Slot (e.g. "4-1")
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
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/scheduler/teachers`);
      const rawTeachers = await res.json();

      // Parse raw backend data into structured restrictions
      const teachers: Teacher[] = rawTeachers.map(
        (t: { id: string; name: string; dept: string; blocked: unknown }) => {
          let restrictions: TeacherRestrictions = {
            mode: "blacklist",
            specific: [],
            recurring: [],
          };
          if (t.blocked && !Array.isArray(t.blocked)) {
            // Already structured
            restrictions = t.blocked as TeacherRestrictions;
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
      set({ error: "Failed to fetch initial data", isLoading: false });
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
      await fetch(
        `${API_BASE_URL}/api/v1/scheduler/teachers/${teacherId}/restrictions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ restrictions: teacher.restrictions }),
        },
      );
    } catch (e) {
      console.error("Failed to save restrictions", e);
    }
  },
}));
