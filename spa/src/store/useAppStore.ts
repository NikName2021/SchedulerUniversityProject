import { create } from 'zustand';
import { MockAPI } from '../api/mockService';
import type { Teacher, Stream } from '../api/mockService';

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
  toggleBlockedSlot: (teacherId: string, slotKey: string) => void;
  startGeneration: () => Promise<void>;
  updateJobProgress: (jobId: string) => Promise<void>;
  resetJob: () => void;
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
      const [teachers, streams] = await Promise.all([
        MockAPI.getTeachers(),
        MockAPI.getStreams()
      ]);
      set({ 
        teachers, 
        streams, 
        isLoading: false,
        selectedTeacherId: teachers[0]?.id || null 
      });
    } catch {
      set({ error: 'Failed to fetch initial data', isLoading: false });
    }
  },

  setSelectedTeacherId: (id) => set({ selectedTeacherId: id }),

  toggleBlockedSlot: (teacherId, slotKey) => {
    set((state) => ({
      teachers: state.teachers.map((t) => {
        if (t.id === teacherId) {
          const newBlocked = t.blocked.includes(slotKey)
            ? t.blocked.filter((s) => s !== slotKey)
            : [...t.blocked, slotKey];
          return { ...t, blocked: newBlocked };
        }
        return t;
      })
    }));
  },

  startGeneration: async () => {
    set({ isGenerating: true, progress: 0, logs: ['Инициализация...'] });
    try {
      const { jobId } = await MockAPI.startGeneration();
      set({ jobId });
    } catch {
      set({ error: 'Failed to start generation', isGenerating: false });
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
      console.error('Progress update failed', err);
    }
  },

  resetJob: () => set({ isGenerating: false, jobId: null, progress: 0, logs: [] })
}));
