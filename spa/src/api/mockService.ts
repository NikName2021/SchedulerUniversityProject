// Имитация сетевой задержки Backend
const delay = (ms: number) => new Promise(res => setTimeout(res, ms));

export interface Teacher {
  id: string;
  name: string;
  dept: string;
  blocked: string[];
}

export interface Stream {
  id: number;
  name: string;
  groups: string[];
}

export const MockAPI = {
  // 1. Потоки
  getStreams: async (): Promise<Stream[]> => {
    await delay(300);
    return [
      { id: 1, name: "ИТ-Инженерия", groups: ["ИТ-1", "ИТ-2"] },
      { id: 2, name: "Прикладная математика", groups: ["ПМ-1", "ПМ-2", "ПМ-3"] }
    ];
  },
  
  // 2. Преподаватели
  getTeachers: async (): Promise<Teacher[]> => {
    await delay(400);
    return [
       { id: '1', name: "Иванов А.С.", dept: "Высшая математика", blocked: ["ЧТ-1", "ЧТ-2"] },
       { id: '2', name: "Петров В.М.", dept: "Кафедра математики", blocked: [] },
       { id: '3', name: "Сидорова Е.Ю.", dept: "Кафедра физики", blocked: [] },
       { id: '4', name: "Козлов Д.А.", dept: "Кафедра ИИ", blocked: ["СБ-1", "СБ-2", "СБ-3", "СБ-4", "СБ-5", "СБ-6"] }
    ];
  },
  
  // 3. Расписание (Генерация алгоритма)
  startGeneration: async () => {
    await delay(800);
    return { jobId: "task_" + Math.random().toString(36).substr(2, 9) };
  },

  checkStatus: async (jobId: string) => {
    await delay(300);
    console.log(`Checking status for ${jobId}`);
    // Простая имитация прогресса: возвращает текущий процент и логи
    // В реальном приложении это был бы опрос Redis через FastAPI
    return {
      progress: Math.min(100, (Date.now() % 10000) / 100), // Имитируем рост прогресса каждые 10 сек
      status: "processing",
      logs: [
        "Загрузка данных из PostgreSQL... OK",
        "Инициализация модели орто-маршрутизации (OR-Tools)... OK",
        "Добавление мягких ограничений... OK",
        "Оптимизация... В процессе"
      ]
    };
  }
};
