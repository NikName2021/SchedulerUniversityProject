export interface StreamPreview {
  id: number;
  event_name: string;
  stream_type: string;
  teacher: string;
}

export interface RuleProfileOption {
  id: number;
  name: string;
  description: string | null;
  is_default: boolean;
}

export interface PlanningWeek {
  id: number;
  period_id: number;
  sequence_number: number;
  starts_on: string;
  ends_on: string;
  status: string;
}

export interface AcademicPeriod {
  id: number;
  name: string;
  starts_on: string;
  ends_on: string;
  status: string;
  weeks: PlanningWeek[];
}

export interface BatchWeekState {
  week: PlanningWeek;
  taskId: number | null;
  status:
    | "pending"
    | "queued"
    | "running"
    | "success"
    | "partial"
    | "failed"
    | "canceled";
  progress: number;
  error: string | null;
}

export interface WeeklyDemand {
  id: number;
  week_id: number;
  stream_id: number;
  lessons_count: number;
  priority: number;
  event_name: string | null;
  stream_type: string | null;
  teacher_name: string | null;
}

export interface SemesterDistributionResult {
  period_id: number;
  streams_count: number;
  planned_lessons: number;
  published_lessons: number;
  distributed_lessons: number;
  warnings: string[];
  weeks: Array<{
    week_id: number;
    sequence_number: number;
    lessons_count: number;
    streams_count: number;
  }>;
}

export interface ExperimentalGroupSelection {
  base_groups: string[];
  selected_groups: string[];
  joint_groups: string[];
  subgroup_groups: string[];
}
export type GenerationMode = "week" | "semester";
export interface NewPeriod {
  name: string;
  starts_on: string;
  ends_on: string;
}
