import { useState } from "react";
import {
  Button, Card, Container, Divider, Group, NumberInput, Select, Stack, Text,
  Textarea, TextInput,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { FaIdBadge } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { StatusBadge } from "../../../ui/components/StatusBadge";
import { useRecordOffline, useRecords } from "../api/hooks";
import { CATEGORIES, HALF_DAYS, type LeaveRequest } from "../api/types";

function iso(value: Date | null): string | null {
  return value ? value.toISOString().slice(0, 10) : null;
}

export default function RecordsPage() {
  const [lookup, setLookup] = useState<number | undefined>();
  const [userId, setUserId] = useState<number | undefined>();
  const [category, setCategory] = useState<string | null>("CL");
  const [start, setStart] = useState<Date | null>(null);
  const [end, setEnd] = useState<Date | null>(null);
  const [halfDay, setHalfDay] = useState("none");
  const [reference, setReference] = useState("");
  const [purpose, setPurpose] = useState("");

  const { data, isPending, error } = useRecords(lookup);
  const record = useRecordOffline();
  const rows = data?.results ?? [];
  const ready = Boolean(userId && category && iso(start) && iso(end) && reference.trim());

  function save() {
    record.mutate({
      user_id: userId, category, start_date: iso(start), end_date: iso(end),
      half_day: halfDay, sanction_reference: reference, purpose,
    }, {
      onSuccess: () => {
        notifications.show({ color: "green", title: "Recorded",
          message: "The offline-sanctioned leave was synchronized." });
        setReference("");
        setPurpose("");
      },
      onError: (e) => notifications.show({
        color: "red", title: "Not recorded", message: errorMessage(e) }),
    });
  }

  const columns: Column<LeaveRequest>[] = [
    { key: "category", header: "Category", render: (r) => r.category_label },
    { key: "kind", header: "Type", render: (r) => r.kind },
    { key: "period", header: "Period",
      render: (r) => `${r.start_date} → ${r.end_date}` },
    { key: "days", header: "Days", align: "right",
      render: (r) => r.chargeable_days },
    { key: "reference", header: "Reference",
      render: (r) => r.sanction_reference || "—" },
    { key: "status", header: "Status",
      render: (r) => <StatusBadge status={r.status} /> },
  ];

  return (
    <Container size="lg">
      <PageHeader title="Leave Records"
        subtitle="Record offline-sanctioned leave and inspect an employee's history" />

      <Card padding="lg" withBorder mb="lg">
        <Text fw={600} mb="sm">Record already-sanctioned (offline) leave</Text>
        <Stack gap="md">
          <Group grow align="flex-start">
            <NumberInput label="Employee user id" required value={userId}
              onChange={(v) => setUserId(Number(v))} min={1} />
            <Select label="Category" required data={[...CATEGORIES]}
              value={category} onChange={setCategory} />
          </Group>
          <Group grow align="flex-start">
            <DateInput label="From" required value={start} onChange={setStart} />
            <DateInput label="To" required value={end} onChange={setEnd} />
          </Group>
          <Group grow align="flex-start">
            <Select label="Half day" data={[...HALF_DAYS]} value={halfDay}
              onChange={(v) => setHalfDay(v ?? "none")} />
            <TextInput label="Sanction / reference evidence" required
              value={reference} onChange={(e) => setReference(e.currentTarget.value)} />
          </Group>
          <Textarea label="Purpose" autosize minRows={2} value={purpose}
            onChange={(e) => setPurpose(e.currentTarget.value)} />
          <Button onClick={save} loading={record.isPending} disabled={!ready}>
            Record offline leave
          </Button>
        </Stack>
      </Card>

      <Card padding={0} withBorder>
        <Group justify="space-between" px="lg" pt="lg">
          <Text fw={600}>Employee history</Text>
          <NumberInput w={200} placeholder="user id" value={lookup}
            onChange={(v) => setLookup(Number(v))} min={1} />
        </Group>
        <Divider my="sm" />
        {error
          ? <div style={{ padding: 16 }}><ErrorState error={error} /></div>
          : (
            <DataTable<LeaveRequest>
              rows={rows} columns={columns} loading={isPending} rowKey={(r) => r.id}
              empty={{ icon: FaIdBadge, title: "No records",
                description: "Enter an employee user id to list their leave." }}
            />
          )}
      </Card>
    </Container>
  );
}
