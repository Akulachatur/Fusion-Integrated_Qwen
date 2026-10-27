import { useState } from "react";
import {
  Badge, Button, Card, Container, Divider, Group, NumberInput, Stack,
  Text, Textarea,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { FaClipboardList, FaPlus } from "react-icons/fa";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "../../../lib/http";
import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { FormModal } from "../../../ui/components/FormModal";
import { PageHeader } from "../../../ui/components/PageHeader";
import { StatusBadge } from "../../../ui/components/StatusBadge";
import {
  useCancelLeave, useExtendLeave, useMyRequests, useNominateReplacement,
  useRespondSubstitute, useSubmitResumption, useSubstituteQueue, useWithdraw,
} from "../api/hooks";
import type { LeaveRequest } from "../api/types";

const EXTENDABLE = new Set(["EL", "COL", "VL"]);

function iso(value: Date | null): string | null {
  if (!value) return null;
  return value.toISOString().slice(0, 10);
}

type Action =
  | { kind: "withdraw" | "cancel" | "resume"; request: LeaveRequest }
  | { kind: "extend" | "nominate"; request: LeaveRequest };

export default function MyLeavePage() {
  const navigate = useNavigate();
  const { data, isPending, error } = useMyRequests();
  const subs = useSubstituteQueue();
  const [action, setAction] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [newEnd, setNewEnd] = useState<Date | null>(null);
  const [subId, setSubId] = useState<number | undefined>();

  const withdraw = useWithdraw();
  const cancel = useCancelLeave();
  const extend = useExtendLeave();
  const resume = useSubmitResumption();
  const nominate = useNominateReplacement();
  const respond = useRespondSubstitute();

  const today = new Date().toISOString().slice(0, 10);
  const rows = data?.results ?? [];
  const substituteRequests = subs.data?.results ?? [];

  function close() {
    setAction(null);
    setNote("");
    setNewEnd(null);
    setSubId(undefined);
  }

  function submitAction() {
    if (!action) return;
    const onDone = (message: string) => ({
      onSuccess: () => {
        notifications.show({ color: "green", title: "Done", message });
        close();
      },
      onError: (e: unknown) => notifications.show({
        color: "red", title: "Refused", message: errorMessage(e),
      }),
    });
    const id = action.request.id;
    if (action.kind === "withdraw") {
      withdraw.mutate(id, onDone("The request was withdrawn."));
    } else if (action.kind === "cancel") {
      cancel.mutate({ id, note }, onDone("Cancellation submitted for review."));
    } else if (action.kind === "resume") {
      const date = iso(newEnd);
      if (date) submitResume(id, date);
    } else if (action.kind === "extend") {
      const date = iso(newEnd);
      if (date) extend.mutate({ id, new_end_date: date, purpose: note },
        onDone("Extension submitted for review."));
    } else if (action.kind === "nominate" && subId) {
      nominate.mutate({ id, substitute_user_id: subId },
        onDone("Replacement nominated."));
    }
  }

  function submitResume(id: number, date: string) {
    resume.mutate({ id, resumption_date: date, note }, {
      onSuccess: () => {
        notifications.show({ color: "green", title: "Resumption submitted",
          message: "The sanctioning authority will review it." });
        close();
      },
      onError: (e: unknown) => notifications.show({
        color: "red", title: "Refused", message: errorMessage(e),
      }),
    });
  }

  const columns: Column<LeaveRequest>[] = [
    { key: "category", header: "Category",
      render: (r) => r.category_label },
    { key: "period", header: "Period",
      render: (r) => `${r.start_date} → ${r.end_date}` },
    { key: "days", header: "Days", align: "right",
      render: (r) => r.chargeable_days },
    { key: "kind", header: "Type", render: (r) => r.kind },
    { key: "status", header: "Status",
      render: (r) => <StatusBadge status={r.status} /> },
    { key: "actions", header: "", render: (r) => (
      <Group gap="xs" wrap="nowrap">
        {r.status !== "draft" && r.status !== "approved" && r.status !== "rejected"
          && r.status !== "withdrawn" && r.status !== "cancelled" && (
          <Button size="compact-xs" variant="subtle" color="red"
            onClick={() => setAction({ kind: "withdraw", request: r })}>
            Withdraw
          </Button>
        )}
        {r.kind === "application" && r.status === "approved"
          && r.start_date > today && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "cancel", request: r })}>
            Cancel
          </Button>
        )}
        {r.kind === "application" && r.status === "approved"
          && EXTENDABLE.has(r.category) && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "extend", request: r })}>
            Extend
          </Button>
        )}
        {r.kind === "application" && r.status === "approved"
          && EXTENDABLE.has(r.category) && !r.resumption_date && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "resume", request: r })}>
            Resume
          </Button>
        )}
        {r.status === "applicant_action_required" && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "nominate", request: r })}>
            Replace substitute
          </Button>
        )}
      </Group>
    )},
  ];

  if (error) return <Container size="md"><ErrorState error={error} /></Container>;

  return (
    <Container size="lg">
      <PageHeader
        title="My Leave"
        subtitle="Every request you have made, and where each one stands"
        action={
          <Button leftSection={<FaPlus size={12} />}
            onClick={() => navigate("/leave/apply")}>
            Apply for Leave
          </Button>
        }
      />

      {substituteRequests.length > 0 && (
        <Card padding="lg" mb="lg" withBorder>
          <Text fw={600} mb="xs">Responsibility requests waiting on you</Text>
          <Stack gap="sm">
            {substituteRequests.map((s) => (
              <Group key={s.id} justify="space-between">
                <Text size="sm">Responsibility for request #{s.request}</Text>
                <Group gap="xs">
                  <Button size="compact-xs" color="green"
                    loading={respond.isPending}
                    onClick={() => respond.mutate({ id: s.request, accept: true }, {
                      onError: (e) => notifications.show({
                        color: "red", title: "Refused", message: errorMessage(e) }),
                    })}>
                    Accept
                  </Button>
                  <Button size="compact-xs" color="red" variant="light"
                    loading={respond.isPending}
                    onClick={() => respond.mutate({ id: s.request, accept: false }, {
                      onError: (e) => notifications.show({
                        color: "red", title: "Refused", message: errorMessage(e) }),
                    })}>
                    Decline
                  </Button>
                </Group>
              </Group>
            ))}
          </Stack>
        </Card>
      )}

      <Card padding={0} withBorder>
        <Group justify="space-between" px="lg" pt="lg">
          <Text fw={600}>My requests</Text>
          <Badge variant="light">{rows.length}</Badge>
        </Group>
        <Divider my="sm" />
        <DataTable<LeaveRequest>
          rows={rows} columns={columns} loading={isPending} rowKey={(r) => r.id}
          empty={{ icon: FaClipboardList, title: "No leave requests yet",
            description: "Apply for leave and it will appear here." }}
        />
      </Card>

      <FormModal
        opened={action != null} onClose={close}
        title={modalTitle(action)} subtitle={modalSubtitle(action)}
        onSubmit={submitAction} submitLabel="Confirm"
        submitting={withdraw.isPending || cancel.isPending || extend.isPending
          || resume.isPending || nominate.isPending}
        disabled={
          (action?.kind === "extend" && !newEnd)
          || (action?.kind === "resume" && !newEnd)
          || (action?.kind === "nominate" && !subId)
        }
      >
        <Stack gap="md">
          {action?.kind === "nominate" && (
            <NumberInput label="Replacement substitute's user id" required
              value={subId} onChange={(v) => setSubId(Number(v))} min={1} />
          )}
          {(action?.kind === "extend" || action?.kind === "resume") && (
            <DateInput label={action.kind === "extend"
              ? "New end date" : "Actual resumption date"} required
              value={newEnd} onChange={setNewEnd} />
          )}
          <Textarea label="Note" autosize minRows={2} value={note}
            onChange={(e) => setNote(e.currentTarget.value)} />
        </Stack>
      </FormModal>
    </Container>
  );
}

function modalTitle(action: Action | null): string {
  if (!action) return "";
  return {
    withdraw: "Withdraw this request",
    cancel: "Request cancellation",
    extend: "Request an extension",
    resume: "Submit resumption of duty",
    nominate: "Nominate a replacement substitute",
  }[action.kind];
}

function modalSubtitle(action: Action | null): string {
  if (!action) return "";
  return {
    withdraw: "Withdrawal is immediate and stops all further approval.",
    cancel: "Cancellation follows the same approval path as the leave.",
    extend: "Only the additional period is posted on approval.",
    resume: "The sanctioning authority reviews the actual return date.",
    nominate: "The new nominee must accept before routing continues.",
  }[action.kind];
}
