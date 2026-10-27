import { useState } from "react";
import {
  Button, Card, Container, Divider, Group, NumberInput, Stack, Text, TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaUserClock } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useSetSla, useSla } from "../api/hooks";
import type { SlaRow } from "../api/types";

export default function SlaPage() {
  const { data, isPending, error } = useSla();
  const setSla = useSetSla();
  const [taskClass, setTaskClass] = useState("unit_head_review");
  const [reminder, setReminder] = useState<number>(24);
  const [escalation, setEscalation] = useState<number>(48);

  const rows = data?.results ?? [];

  function save() {
    setSla.mutate({ task_class: taskClass, reminder_hours: reminder,
      escalation_hours: escalation }, {
      onSuccess: () => notifications.show({ color: "green", title: "Saved",
        message: "SLA processing now uses these thresholds." }),
      onError: (e) => notifications.show({
        color: "red", title: "Not saved", message: errorMessage(e) }),
    });
  }

  const columns: Column<SlaRow>[] = [
    { key: "task_class", header: "Task class", render: (r) => r.task_class },
    { key: "reminder", header: "Reminder (hours)", align: "right",
      render: (r) => r.reminder_hours },
    { key: "escalation", header: "Escalation (hours)", align: "right",
      render: (r) => r.escalation_hours },
  ];

  if (error) return <Container size="md"><ErrorState error={error} /></Container>;

  return (
    <Container size="md">
      <PageHeader title="SLA Settings"
        subtitle="Reminder and escalation thresholds for actionable tasks" />

      <Card padding={0} withBorder mb="lg">
        <Text fw={600} px="lg" pt="lg">Configured thresholds</Text>
        <Divider my="sm" />
        <DataTable<SlaRow>
          rows={rows} columns={columns} loading={isPending} minWidth={520}
          rowKey={(r) => r.task_class}
          empty={{ icon: FaUserClock, title: "No thresholds configured",
            description: "Add one below, or run `manage.py seed_leave`." }}
        />
      </Card>

      <Card padding="lg" withBorder>
        <Text fw={600} mb="sm">Set a threshold</Text>
        <Stack gap="md">
          <TextInput label="Task class" required value={taskClass}
            onChange={(e) => setTaskClass(e.currentTarget.value)} />
          <Group grow>
            <NumberInput label="Reminder after (hours)" value={reminder}
              onChange={(v) => setReminder(Number(v))} min={1} />
            <NumberInput label="Escalate after (hours)" value={escalation}
              onChange={(v) => setEscalation(Number(v))} min={1} />
          </Group>
          <Button onClick={save} loading={setSla.isPending}>Save</Button>
        </Stack>
      </Card>
    </Container>
  );
}
