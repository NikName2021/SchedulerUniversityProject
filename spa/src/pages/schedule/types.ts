export interface ScheduleEntry {
  id: number;
  task_id: number | null;
  source_stream_id: number | null;
  group_name: string;
  event_name: string;
  stream_type: string;
  teacher: string | null;
  teacher_id: number | null;
  room_id: string | null;
  date: string;
  lesson_number: number;
  warning: string | null;
  is_locked: boolean;
}

export interface ScheduleEntryDetails {
  id: number;
  task_id: number | null;
  semester_batch_id: string | null;
  planning_week_id: number | null;
  source_stream_id: number | null;
  event_name: string;
  discipline_name: string;
  stream_type: string;
  teacher: string | null;
  audience_label: string;
  audience_labels: string[];
  base_groups: string[];
  subgroups: string[];
  date: string | null;
  lesson_number: number | null;
  room_id: string | null;
  is_locked: boolean;
  warning: string | null;
  scheduled_count: number;
  unassigned_count: number;
  planned_count: number;
}

export type ScheduleView = "group" | "teacher";
