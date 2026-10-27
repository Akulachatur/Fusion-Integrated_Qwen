import { useState } from "react";
import {
  Button, Card, Container, Divider, NumberInput, Select, Stack,
  Switch, Text, Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";

import { errorMessage } from "../../../lib/http";
import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { FormModal } from "../../../ui/components/FormModal";
import { PageHeader } from "../../../ui/components/PageHeader";
import { usePolicy, useSetHierarchy, useSetPolicy } from "../api/hooks";
import { CATEGORIES, type PolicyRow } from "../api/types";

export default function PolicyPage() {
  const { data, isPending, error } = usePolicy();
  const setPolicy = useSetPolicy();
  const setHierarchy = useSetHierarchy();
  const [editing, setEditing] = useState<PolicyRow | null>(null);
  const [entitlement, setEntitlement] = useState<number>(0);
  const [carry, setCarry] = useState(false);
  const [continuous, setContinuous] = useState(false);
  const [halfDay, setHalfDay] = useState(false);

  const [hCategory, setHCategory] = useState<string | null>("CL");
  const [steps, setSteps] = useState("");

  const rows = data?.results ?? [];

  function openEditor(row: PolicyRow) {
    setEditing(row);
    setEntitlement(Number(row.annual_entitlement));
    setCarry(row.carries_forward);
    setContinuous(row.continuous_counting);
    setHalfDay(row.half_day_allowed);
  }

  function savePolicy() {
    setPolicy.mutate({
      category: editing?.category,
      annual_entitlement: entitlement,
      carries_forward: carry,
      continuous_counting: continuous,
      half_day_allowed: halfDay,
    }, {
      onSuccess: () => {
        notifications.show({ color: "green", title: "Saved",
          message: "Validation now uses the updated policy." });
        setEditing(null);
      },
      onError: (e) => notifications.show({
        color: "red", title: "Not saved", message: errorMessage(e) }),
    });
  }

  function saveHierarchy() {
    const parsed = steps.split("\n").map((l) => l.trim()).filter(Boolean)
      .map((line) => {
        const [seq, role, final] = line.split("|").map((p) => p.trim());
        return { seq: Number(seq), role, is_final: final === "final" };
      });
    if (!parsed.length) {
      notifications.show({ color: "red", title: "Nothing to save",
        message: "Add at least one step." });
      return;
    }
    setHierarchy.mutate({ category: hCategory ?? "CL", steps: parsed }, {
      onSuccess: () => notifications.show({ color: "green", title: "Saved",
        message: "Routing now uses the configured path." }),
      onError: (e) => notifications.show({
        color: "red", title: "Not saved", message: errorMessage(e) }),
    });
  }

  const columns: Column<PolicyRow>[] = [
    { key: "category", header: "Category", render: (p) => p.category },
    { key: "entitlement", header: "Annual entitlement", align: "right",
      render: (p) => p.annual_entitlement },
    { key: "carry", header: "Carries forward",
      render: (p) => (p.carries_forward ? "Yes" : "No") },
    { key: "continuous", header: "Continuous counting",
      render: (p) => (p.continuous_counting ? "Yes" : "No") },
    { key: "half", header: "Half day",
      render: (p) => (p.half_day_allowed ? "Yes" : "No") },
    { key: "edit", header: "", render: (p) => (
      <Button size="compact-xs" variant="subtle" onClick={() => openEditor(p)}>
        Edit
      </Button>
    )},
  ];

  if (error) return <Container size="md"><ErrorState error={error} /></Container>;

  return (
    <Container size="lg">
      <PageHeader title="Policy & Hierarchy"
        subtitle="The current configured parameters — there is no draft lifecycle" />

      <Card padding={0} withBorder mb="lg">
        <Text fw={600} px="lg" pt="lg">Leave policy</Text>
        <Divider my="sm" />
        <DataTable<PolicyRow>
          rows={rows} columns={columns} loading={isPending} minWidth={640}
          rowKey={(p) => p.category}
          empty={{ title: "No policy rows",
            description: "Run `manage.py seed_leave` to load the baseline." }}
        />
      </Card>

      <Card padding="lg" withBorder>
        <Text fw={600} mb="sm">Sanctioning hierarchy</Text>
        <Stack gap="md">
          <Select label="Category" data={[...CATEGORIES]} value={hCategory}
            onChange={setHCategory} />
          <Textarea label="Steps" autosize minRows={4} value={steps}
            onChange={(e) => setSteps(e.currentTarget.value)}
            description="One per line: seq | role | final (role: unit_head,
              establishment, dean, registrar, director)" />
          <Button onClick={saveHierarchy} loading={setHierarchy.isPending}>
            Save hierarchy
          </Button>
        </Stack>
      </Card>

      <FormModal
        opened={editing != null} onClose={() => setEditing(null)}
        title={`Edit ${editing?.category ?? ""} policy`}
        onSubmit={savePolicy} submitLabel="Save"
        submitting={setPolicy.isPending}
      >
        <Stack gap="md">
          <NumberInput label="Annual entitlement" value={entitlement}
            onChange={(v) => setEntitlement(Number(v))} min={0} decimalScale={2} />
          <Switch label="Unused days carry forward" checked={carry}
            onChange={(e) => setCarry(e.currentTarget.checked)} />
          <Switch label="Counts continuously (EL/COL/VL rule)" checked={continuous}
            onChange={(e) => setContinuous(e.currentTarget.checked)} />
          <Switch label="Half day allowed" checked={halfDay}
            onChange={(e) => setHalfDay(e.currentTarget.checked)} />
        </Stack>
      </FormModal>
    </Container>
  );
}
