import { useState } from "react";
import {
  Badge, Button, Card, Container, Divider, Group, NumberInput, Stack, Text,
  Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { FaCalendarAlt } from "react-icons/fa";

import { errorMessage } from "../../../lib/http";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import {
  useCalendars, usePublishCalendar, useSyncVacation, useVacationPeriods,
} from "../api/hooks";
import type { HolidayRow } from "../api/types";

/** "YYYY-MM-DD | Name | closed|restricted", one holiday per line. */
function parseHolidays(text: string): HolidayRow[] {
  return text.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
    const [date, name, kind] = line.split("|").map((p) => p.trim());
    return { date: date ?? "", name: name ?? "",
      kind: kind === "restricted" ? "restricted" : "closed" };
  });
}

export default function CalendarPage() {
  const calendars = useCalendars();
  const vacation = useVacationPeriods();
  const publish = usePublishCalendar();
  const sync = useSyncVacation();

  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [note, setNote] = useState("");
  const [body, setBody] = useState("");
  const [periods, setPeriods] = useState("");

  const rows = calendars.data?.results ?? [];
  const vacations = vacation.data?.results ?? [];

  function onPublish() {
    const holidays = parseHolidays(body);
    if (!holidays.length) {
      notifications.show({ color: "red", title: "Nothing to publish",
        message: "Add at least one holiday, one per line." });
      return;
    }
    publish.mutate({ year, note, holidays }, {
      onSuccess: () => {
        notifications.show({ color: "green", title: "Published",
          message: "This calendar now governs date validation." });
        setBody("");
      },
      onError: (e) => notifications.show({
        color: "red", title: "Could not publish", message: errorMessage(e) }),
    });
  }

  function onSync() {
    const list = periods.split("\n").map((l) => l.trim()).filter(Boolean)
      .map((line) => {
        const [start_date, end_date, label] = line.split("|").map((p) => p.trim());
        return { start_date: start_date ?? "", end_date: end_date ?? "",
          label: label ?? "" };
      });
    sync.mutate(list, {
      onSuccess: () => notifications.show({ color: "green",
        title: "Synced", message: "Vacation periods replaced from the Academic Calendar." }),
      onError: (e) => notifications.show({
        color: "red", title: "Could not sync", message: errorMessage(e) }),
    });
  }

  if (calendars.error) {
    return <Container size="md"><ErrorState error={calendars.error} /></Container>;
  }

  return (
    <Container size="lg">
      <PageHeader title="Holiday Calendar"
        subtitle="The published calendar governs date and RH validation until replaced" />

      <Card padding="lg" withBorder mb="lg">
        <Text fw={600} mb="sm">Publish a calendar</Text>
        <Stack gap="md">
          <Group grow align="flex-start">
            <NumberInput label="Year" required value={year}
              onChange={(v) => setYear(Number(v))} min={2000} />
            <Textarea label="Note" autosize minRows={1} value={note}
              onChange={(e) => setNote(e.currentTarget.value)} />
          </Group>
          <Textarea label="Holidays" required autosize minRows={6} value={body}
            onChange={(e) => setBody(e.currentTarget.value)}
            description="One per line: YYYY-MM-DD | Name | closed or restricted" />
          <Button onClick={onPublish} loading={publish.isPending}>
            Publish calendar
          </Button>
        </Stack>
      </Card>

      <Card padding="lg" withBorder mb="lg">
        <Text fw={600} mb="xs">Published calendars</Text>
        <Divider mb="sm" />
        <Stack gap="sm">
          {rows.map((c) => (
            <Group key={c.id} justify="space-between">
              <Text size="sm">Year {c.year}</Text>
              <Group gap="xs">
                <Badge variant="light" color={c.status === "published" ? "green" : "gray"}>
                  {c.status}
                </Badge>
                <Text size="xs" c="dimmed">{c.holidays.length} holiday(s)</Text>
              </Group>
            </Group>
          ))}
          {rows.length === 0 && <Text size="sm" c="dimmed">No calendars yet.</Text>}
        </Stack>
      </Card>

      <Card padding="lg" withBorder>
        <Group justify="space-between" mb="sm">
          <Text fw={600}>Academic Calendar vacation periods</Text>
          <Badge variant="light">{vacations.length}</Badge>
        </Group>
        <Stack gap="md">
          <Textarea label="Vacation periods" autosize minRows={4} value={periods}
            onChange={(e) => setPeriods(e.currentTarget.value)}
            description="One per line: YYYY-MM-DD | YYYY-MM-DD | Label" />
          <Button variant="light" leftSection={<FaCalendarAlt size={12} />}
            onClick={onSync} loading={sync.isPending}>
            Re-sync from Academic Calendar
          </Button>
        </Stack>
      </Card>
    </Container>
  );
}
