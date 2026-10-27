/** Wire types for the leave (ELM) API.
 *
 *  Monetary-style values — leave days — arrive as STRINGS, as Django
 *  serialises Decimal. Parsing them into JS numbers puts float arithmetic on
 *  a half-day balance.
 */

export interface Page<T> {
  results: T[];
  next?: string | null;
  previous?: string | null;
}

export const CATEGORIES = [
  { value: "CL", label: "Casual Leave" },
  { value: "RH", label: "Restricted Holiday" },
  { value: "SCL", label: "Special Casual Leave" },
  { value: "EL", label: "Earned Leave" },
  { value: "COL", label: "Commuted Leave" },
  { value: "VL", label: "Vacation Leave" },
] as const;

export const HALF_DAYS = [
  { value: "none", label: "Full day" },
  { value: "first_half", label: "First half" },
  { value: "second_half", label: "Second half" },
] as const;

export const QUEUE_ROLES = [
  { value: "unit_head", label: "Unit Head" },
  { value: "establishment", label: "Establishment" },
  { value: "dean", label: "Dean" },
  { value: "registrar", label: "Registrar" },
  { value: "director", label: "Director" },
] as const;

export interface LeaveBalance {
  id: number;
  category: string;
  category_label: string;
  year: number;
  entitled: string;
  carried_forward: string;
  used: string;
  adjusted: string;
  available: string;
}

export interface LeaveEvent {
  id: number;
  from_status: string;
  to_status: string;
  actor_role: string;
  outcome: string;
  note: string;
  created_at: string;
}

export interface SubstituteAssignment {
  id: number;
  request: number;
  substitute_user_id: number;
  status: string;
  note: string;
  responded_at: string | null;
}

export interface LeaveRequest {
  id: number;
  applicant_user_id: number;
  category: string;
  category_label: string;
  kind: "application" | "cancellation" | "extension";
  parent: number | null;
  start_date: string;
  end_date: string;
  half_day: string;
  purpose: string;
  station_leave: boolean;
  station_place: string;
  station_purpose: string;
  evidence_reference: string;
  status: string;
  status_label: string;
  current_role: string;
  chargeable_days: string;
  substitute_required: boolean;
  applicant_is_faculty: boolean;
  applicant_is_director: boolean;
  decided_at: string | null;
  decision_note: string;
  is_offline_record: boolean;
  sanction_reference: string;
  resumption_date: string | null;
  resumption_reviewed_at: string | null;
  created_at: string;
  events?: LeaveEvent[];
  substitutes?: SubstituteAssignment[];
}

export interface PolicyRow {
  id: number;
  category: string;
  annual_entitlement: string;
  carries_forward: boolean;
  continuous_counting: boolean;
  half_day_allowed: boolean;
  evidence_may_be_required: boolean;
  is_active: boolean;
}

export interface SlaRow {
  id: number;
  task_class: string;
  reminder_hours: number;
  escalation_hours: number;
}

export interface HolidayRow {
  id?: number;
  date: string;
  name: string;
  kind: "closed" | "restricted";
}

export interface CalendarRow {
  id: number;
  year: number;
  status: string;
  published_at: string | null;
  note: string;
  holidays: HolidayRow[];
}

export interface VacationPeriod {
  id: number;
  start_date: string;
  end_date: string;
  label: string;
  source: string;
  synced_at: string;
}
