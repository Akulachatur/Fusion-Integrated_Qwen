import { useState } from "react";
import {
  Button, Card, Container, Divider, Group, Select, Stack, Text, Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCheckDouble } from "react-icons/fa";

import { useAuth } from "../../../auth/AuthProvider";
import { errorMessage } from "../../../lib/http";
import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { FormModal } from "../../../ui/components/FormModal";
import { PageHeader } from "../../../ui/components/PageHeader";
import { StatusBadge } from "../../../ui/components/StatusBadge";
import {
  useApprovals, useFinalDecision, useReviewResumption, useRouteApproval,
  useUnitHeadDecision,
} from "../api/hooks";
import { QUEUE_ROLES, type LeaveRequest } from "../api/types";

type Action = {
  kind: "unit_head" | "route" | "final" | "resumption";
  request: LeaveRequest;
};

const DECISIONS = [
  { value: "recommend", label: "Recommended" },
  { value: "not_recommend", label: "Not Recommended" },
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
];

export default function ApprovalsPage() {
  const { session } = useAuth();
  const [role, setRole] = useState<string | null>(session?.active_role ?? "unit_head");
  const { data, isPending, error } = useApprovals(role ?? undefined);
  const [action, setAction] = useState<Action | null>(null);
  const [decision, setDecision] = useState<string | null>("recommend");
  const [note, setNote] = useState("");

  const unitHead = useUnitHeadDecision();
  const route = useRouteApproval();
  const final = useFinalDecision();
  const resumption = useReviewResumption();

  const rows = data?.results ?? [];

  function close() {
    setAction(null);
    setDecision("recommend");
    setNote("");
  }

  function run() {
    if (!action) return;
    const done = (message: string) => ({
      onSuccess: () => {
        notifications.show({ color: "green", title: "Recorded", message });
        close();
      },
      onError: (e: unknown) => notifications.show({
        color: "red", title: "Refused", message: errorMessage(e) }),
    });
    const id = action.request.id;
    if (action.kind === "unit_head") {
      unitHead.mutate({ id, decision: decision ?? "recommend", note },
        done("The decision was recorded."));
    } else if (action.kind === "route") {
      route.mutate({ id, note }, done("Request routed to the sanctioning authority."));
    } else if (action.kind === "final") {
      final.mutate({ id, approve: decision === "approve", note },
        done("The final decision was recorded."));
    } else {
      resumption.mutate({ id, note }, done("Resumption reviewed."));
    }
  }

  const columns: Column<LeaveRequest>[] = [
    { key: "applicant", header: "Applicant",
      render: (r) => `#${r.applicant_user_id}` },
    { key: "category", header: "Category", render: (r) => r.category_label },
    { key: "kind", header: "Type", render: (r) => r.kind },
    { key: "period", header: "Period",
      render: (r) => `${r.start_date} → ${r.end_date}` },
    { key: "status", header: "Status",
      render: (r) => <StatusBadge status={r.status} /> },
    { key: "actions", header: "", render: (r) => (
      <Group gap="xs" wrap="nowrap">
        {r.status === "awaiting_unit_head" && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "unit_head", request: r })}>
            Review
          </Button>
        )}
        {r.status === "awaiting_establishment" && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "route", request: r })}>
            Route
          </Button>
        )}
        {(r.status === "awaiting_final_sanction"
          || r.status === "awaiting_director_self_sanction") && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "final", request: r })}>
            Decide
          </Button>
        )}
        {r.status === "approved" && r.resumption_date && !r.resumption_reviewed_at
          && (
          <Button size="compact-xs" variant="subtle"
            onClick={() => setAction({ kind: "resumption", request: r })}>
            Review resumption
          </Button>
        )}
      </Group>
    )},
  ];

  if (error) return <Container size="md"><ErrorState error={error} /></Container>;

  return (
    <Container size="lg">
      <PageHeader
        title="Approvals"
        subtitle="Requests waiting on a role's decision or recommendation"
        action={
          <Select label="Queue" data={[...QUEUE_ROLES]} value={role}
            onChange={setRole} w={200} />
        }
      />

      <Card padding={0} withBorder>
        <Group justify="space-between" px="lg" pt="lg">
          <Text fw={600}>Waiting on {role}</Text>
        </Group>
        <Divider my="sm" />
        <DataTable<LeaveRequest>
          rows={rows} columns={columns} loading={isPending} rowKey={(r) => r.id}
          empty={{ icon: FaCheckDouble, title: "Nothing waiting",
            description: "Requests routed to this role will appear here." }}
        />
      </Card>

      <FormModal
        opened={action != null} onClose={close}
        title="Record a decision" onSubmit={run} submitLabel="Record"
        submitting={unitHead.isPending || route.isPending || final.isPending
          || resumption.isPending}
      >
        <Stack gap="md">
          {action?.kind === "unit_head" && (
            <Select label="Decision" data={DECISIONS} value={decision}
              onChange={setDecision}
              description="CL/RH are approved or rejected here; higher-sanction
                categories are recommended or not recommended." />
          )}
          {action?.kind === "final" && (
            <Select label="Decision"
              data={[{ value: "approve", label: "Approve" },
                { value: "reject", label: "Reject" }]}
              value={decision} onChange={setDecision} />
          )}
          <Textarea label="Note" autosize minRows={2} value={note}
            onChange={(e) => setNote(e.currentTarget.value)} />
        </Stack>
      </FormModal>
    </Container>
  );
}
