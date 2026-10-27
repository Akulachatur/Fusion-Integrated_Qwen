import { useState } from "react";
import { Badge, Card, Container, Divider, Group, NumberInput, Text } from "@mantine/core";
import { FaWallet } from "react-icons/fa";

import { DataTable, type Column } from "../../../ui/components/DataTable";
import { ErrorState } from "../../../ui/components/ErrorState";
import { PageHeader } from "../../../ui/components/PageHeader";
import { useMyBalances } from "../api/hooks";
import type { LeaveBalance } from "../api/types";

const columns: Column<LeaveBalance>[] = [
  { key: "category", header: "Category", render: (b) => b.category_label },
  { key: "entitled", header: "Entitled", align: "right",
    render: (b) => b.entitled },
  { key: "carried", header: "Carried forward", align: "right",
    render: (b) => b.carried_forward },
  { key: "used", header: "Used", align: "right", render: (b) => b.used },
  { key: "adjusted", header: "Adjusted", align: "right",
    render: (b) => b.adjusted },
  { key: "available", header: "Available", align: "right",
    render: (b) => <Badge variant="light" color="green">{b.available}</Badge> },
];

export default function BalancesPage() {
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const { data, isPending, error } = useMyBalances(year);
  const rows = data?.results ?? [];

  if (error) return <Container size="md"><ErrorState error={error} /></Container>;

  return (
    <Container size="md">
      <PageHeader
        title="Leave Balances"
        subtitle="What each category still has available this year"
        action={
          <NumberInput w={140} label="Year" value={year} min={2000}
            onChange={(v) => setYear(Number(v))} />
        }
      />

      <Card padding={0} withBorder>
        <Group justify="space-between" px="lg" pt="lg">
          <Text fw={600}>Balances for {year}</Text>
        </Group>
        <Divider my="sm" />
        <DataTable<LeaveBalance>
          rows={rows} columns={columns} loading={isPending}
          rowKey={(b) => `${b.category}-${b.year}`}
          empty={{ icon: FaWallet, title: "No balances yet",
            description: "Balances are created when you first apply for leave." }}
        />
      </Card>
    </Container>
  );
}
