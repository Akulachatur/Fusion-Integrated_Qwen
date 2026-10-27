/** Data access for the leave module.
 *
 *  Every mutation invalidates the whole key, because a decision on one request
 *  changes the queue, the balance and the employee's history at once.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { http } from "../../../lib/http";
import type {
  CalendarRow, HolidayRow, LeaveBalance, LeaveRequest, Page, PolicyRow, SlaRow,
  SubstituteAssignment, VacationPeriod,
} from "./types";

const KEY = "leave";

export const keys = {
  balances: (year?: number) => [KEY, "balances", year] as const,
  requests: (filters?: unknown) => [KEY, "requests", filters] as const,
  request: (id: number) => [KEY, "request", id] as const,
  substitutes: () => [KEY, "substitutes"] as const,
  approvals: (role?: string) => [KEY, "approvals", role] as const,
  policy: () => [KEY, "policy"] as const,
  sla: () => [KEY, "sla"] as const,
  calendars: () => [KEY, "calendars"] as const,
  vacation: () => [KEY, "vacation"] as const,
  records: (userId?: number) => [KEY, "records", userId] as const,
};

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: [KEY] });
}

// -- Employee ------------------------------------------------------------------
export function useMyBalances(year?: number) {
  return useQuery({
    queryKey: keys.balances(year),
    queryFn: async () =>
      (await http.get<Page<LeaveBalance>>("/leave/balances",
        { params: year ? { year } : undefined })).data,
    staleTime: 30_000,
  });
}

export function useMyRequests(filters?: { kind?: string; status?: string }) {
  return useQuery({
    queryKey: keys.requests(filters),
    queryFn: async () =>
      (await http.get<Page<LeaveRequest>>("/leave/requests", { params: filters })).data,
    staleTime: 15_000,
  });
}

export function useMyRequest(id: number | undefined) {
  return useQuery({
    queryKey: keys.request(id ?? 0),
    queryFn: async () => (await http.get<LeaveRequest>(`/leave/requests/${id}`)).data,
    enabled: id != null,
  });
}

export function useSubmitLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<LeaveRequest>("/leave/requests", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useWithdraw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      (await http.post<LeaveRequest>(`/leave/requests/${id}/withdraw`, {})).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCancelLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, note }: { id: number; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/requests/${id}/cancel`,
        { note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useExtendLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, new_end_date, substitute_user_id, purpose }:
      { id: number; new_end_date: string; substitute_user_id?: number | null;
        purpose?: string }) =>
      (await http.post<LeaveRequest>(`/leave/requests/${id}/extend`,
        { new_end_date, substitute_user_id: substitute_user_id ?? null,
          purpose: purpose ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSubmitResumption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, resumption_date, note }: {
      id: number; resumption_date: string; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/requests/${id}/resume`,
        { resumption_date, note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useNominateReplacement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, substitute_user_id }: {
      id: number; substitute_user_id: number }) =>
      (await http.post<LeaveRequest>(`/leave/requests/${id}/nominate-replacement`,
        { substitute_user_id })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSubstituteQueue() {
  return useQuery({
    queryKey: keys.substitutes(),
    queryFn: async () => (await http.get<Page<SubstituteAssignment>>(
      "/leave/substitute-requests")).data,
    staleTime: 15_000,
  });
}

export function useRespondSubstitute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept, note }: {
      id: number; accept: boolean; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/substitute-requests/${id}/respond`,
        { accept, note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Approvals -----------------------------------------------------------------
export function useApprovals(role?: string) {
  return useQuery({
    queryKey: keys.approvals(role),
    queryFn: async () => (await http.get<Page<LeaveRequest>>("/leave/approvals",
      { params: role ? { role } : undefined })).data,
    staleTime: 15_000,
  });
}

export function useUnitHeadDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, decision, note }: {
      id: number; decision: string; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/approvals/${id}/unit-head`,
        { decision, note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useRouteApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, note }: { id: number; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/approvals/${id}/route`,
        { note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useFinalDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, approve, note }: {
      id: number; approve: boolean; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/approvals/${id}/decision`,
        { approve, note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useReviewResumption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, note }: { id: number; note?: string }) =>
      (await http.post<LeaveRequest>(`/leave/approvals/${id}/resumption-review`,
        { note: note ?? "" })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

// -- Administration ------------------------------------------------------------
export function usePolicy() {
  return useQuery({
    queryKey: keys.policy(),
    queryFn: async () => (await http.get<Page<PolicyRow>>("/leave/policy")).data,
  });
}

export function useSetPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<PolicyRow>("/leave/policy", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSetHierarchy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { category: string; steps: unknown[] }) =>
      (await http.post("/leave/hierarchy", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useSla() {
  return useQuery({
    queryKey: keys.sla(),
    queryFn: async () => (await http.get<Page<SlaRow>>("/leave/sla")).data,
  });
}

export function useSetSla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { task_class: string; reminder_hours: number;
      escalation_hours: number }) =>
      (await http.post<SlaRow>("/leave/sla", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useCalendars() {
  return useQuery({
    queryKey: keys.calendars(),
    queryFn: async () => (await http.get<Page<CalendarRow>>("/leave/calendars")).data,
  });
}

export function usePublishCalendar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { year: number; note?: string;
      holidays: HolidayRow[] }) =>
      (await http.post<CalendarRow>("/leave/calendars",
        { year: body.year, note: body.note ?? "",
          holidays: body.holidays })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useVacationPeriods() {
  return useQuery({
    queryKey: keys.vacation(),
    queryFn: async () =>
      (await http.get<Page<VacationPeriod>>("/leave/vacation-periods")).data,
  });
}

export function useSyncVacation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (periods: { start_date: string; end_date: string;
      label?: string }[]) =>
      (await http.post<{ synced: number }>("/leave/vacation-periods",
        { periods })).data,
    onSuccess: () => invalidateAll(qc),
  });
}

export function useRecords(userId: number | undefined) {
  return useQuery({
    queryKey: keys.records(userId),
    queryFn: async () => (await http.get<Page<LeaveRequest>>("/leave/records",
      { params: { user_id: userId } })).data,
    enabled: Number.isFinite(userId),
  });
}

export function useRecordOffline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      (await http.post<LeaveRequest>("/leave/records", body)).data,
    onSuccess: () => invalidateAll(qc),
  });
}
