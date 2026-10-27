import { useState } from "react";
import {
  Button, Card, Checkbox, Container, Group, NumberInput, Select, Stack,
  Textarea, TextInput,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "../../../lib/http";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useSubmitLeave } from "../api/hooks";
import { CATEGORIES, HALF_DAYS } from "../api/types";

const HALF_DAY_CATEGORIES = new Set(["CL"]);

function iso(value: Date | null): string | null {
  return value ? value.toISOString().slice(0, 10) : null;
}

export default function ApplyLeavePage() {
  const navigate = useNavigate();
  const submit = useSubmitLeave();

  const [category, setCategory] = useState<string | null>("CL");
  const [start, setStart] = useState<Date | null>(null);
  const [end, setEnd] = useState<Date | null>(null);
  const [halfDay, setHalfDay] = useState<string>("none");
  const [purpose, setPurpose] = useState("");
  const [station, setStation] = useState(false);
  const [place, setPlace] = useState("");
  const [stationPurpose, setStationPurpose] = useState("");
  const [evidence, setEvidence] = useState("");
  const [substitute, setSubstitute] = useState<number | undefined>();

  const startIso = iso(start);
  const endIso = iso(end);
  const complete = Boolean(category && startIso && endIso && purpose.trim());

  function onSave() {
    submit.mutate({
      category, start_date: startIso, end_date: endIso, half_day: halfDay,
      purpose, station_leave: station, station_place: place,
      station_purpose: stationPurpose, evidence_reference: evidence,
      substitute_user_id: substitute ?? null,
    }, {
      onSuccess: () => {
        notifications.show({
          color: "green", title: "Submitted",
          message: "Your request is now in the approval process.",
        });
        navigate("/leave/mine");
      },
      onError: (e) => notifications.show({
        color: "red", title: "Not submitted", message: errorMessage(e),
      }),
    });
  }

  return (
    <Container size="md">
      <PageHeader title="Apply for Leave"
        subtitle="One application captures the category, period and purpose" />

      {submit.error != null && <ErrorState error={submit.error} />}

      <Card padding="lg" withBorder>
        <Stack gap="md">
          <Select label="Leave category" required data={[...CATEGORIES]}
            value={category} onChange={setCategory} />
          <Group grow align="flex-start">
            <DateInput label="From" required value={start} onChange={setStart} />
            <DateInput label="To" required value={end} onChange={setEnd} />
          </Group>
          {category && HALF_DAY_CATEGORIES.has(category) && (
            <Select label="Half day" data={[...HALF_DAYS]} value={halfDay}
              onChange={(v) => setHalfDay(v ?? "none")} />
          )}
          <Textarea label="Purpose / reason" required autosize minRows={3}
            value={purpose} onChange={(e) => setPurpose(e.currentTarget.value)} />
          <TextInput label="Supporting evidence reference"
            description="Required for Commuted Leave where applicable"
            value={evidence} onChange={(e) => setEvidence(e.currentTarget.value)} />
          <NumberInput label="Substitute's user id"
            description="Leave blank when responsibility coverage is not required"
            value={substitute} onChange={(v) => setSubstitute(Number(v))} min={1} />

          <Checkbox label="I will be outside Jabalpur (Station Leave)"
            checked={station} onChange={(e) => setStation(e.currentTarget.checked)} />
          {station && (
            <Group grow align="flex-start">
              <TextInput label="Station / place" value={place}
                onChange={(e) => setPlace(e.currentTarget.value)} />
              <TextInput label="Station Leave purpose" value={stationPurpose}
                onChange={(e) => setStationPurpose(e.currentTarget.value)} />
            </Group>
          )}

          <Button onClick={onSave} loading={submit.isPending} disabled={!complete}>
            Submit application
          </Button>
        </Stack>
      </Card>
    </Container>
  );
}
