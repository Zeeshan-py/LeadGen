"use client";

import { Columns3, Search, Table2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  crmStageLabels,
  crmStages,
  type CrmStage,
  type CrmUser,
} from "@/lib/types";

export type CrmFilters = {
  search: string;
  stage: CrmStage | "all";
  country: string;
  industry: string;
  assignedUserId: string;
  createdFrom: string;
  lastContactedFrom: string;
};

export function CrmToolbar({
  filters,
  users,
  countries,
  industries,
  view,
  onFiltersChange,
  onViewChange,
}: {
  filters: CrmFilters;
  users: CrmUser[];
  countries: string[];
  industries: string[];
  view: "kanban" | "table";
  onFiltersChange: (next: CrmFilters) => void;
  onViewChange: (view: "kanban" | "table") => void;
}) {
  function setFilter<Key extends keyof CrmFilters>(
    key: Key,
    value: CrmFilters[Key],
  ) {
    onFiltersChange({ ...filters, [key]: value });
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border/70 bg-card/55 p-3 xl:flex-row xl:items-end xl:justify-between">
      <div className="grid flex-1 gap-2 md:grid-cols-2 xl:grid-cols-[minmax(220px,1.5fr)_repeat(6,minmax(130px,1fr))]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filters.search}
            onChange={(event) => setFilter("search", event.target.value)}
            placeholder="Search business, email or phone"
            className="pl-9"
            aria-label="Search business, email or phone"
          />
        </div>
        <Select
          value={filters.stage}
          onValueChange={(value) => setFilter("stage", value as CrmFilters["stage"])}
        >
          <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">All statuses</SelectItem>
              {crmStages.map((stage) => (
                <SelectItem key={stage} value={stage}>{crmStageLabels[stage]}</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <FilterSelect
          value={filters.country}
          placeholder="Country"
          allLabel="All countries"
          options={countries}
          onChange={(value) => setFilter("country", value)}
        />
        <FilterSelect
          value={filters.industry}
          placeholder="Industry"
          allLabel="All industries"
          options={industries}
          onChange={(value) => setFilter("industry", value)}
        />
        <Select
          value={filters.assignedUserId}
          onValueChange={(value) => setFilter("assignedUserId", value)}
        >
          <SelectTrigger><SelectValue placeholder="Assigned user" /></SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="all">All users</SelectItem>
              <SelectItem value="unassigned">Unassigned</SelectItem>
              {users.map((user) => (
                <SelectItem key={user.id} value={user.id}>{user.name}</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={filters.createdFrom}
          onChange={(event) => setFilter("createdFrom", event.target.value)}
          aria-label="Date created"
        />
        <Input
          type="date"
          value={filters.lastContactedFrom}
          onChange={(event) => setFilter("lastContactedFrom", event.target.value)}
          aria-label="Last contacted"
        />
      </div>
      <div className="flex shrink-0">
        <Button
          variant={view === "kanban" ? "default" : "outline"}
          className="rounded-r-none"
          onClick={() => onViewChange("kanban")}
        >
          <Columns3 data-icon="inline-start" />
          Kanban
        </Button>
        <Button
          variant={view === "table" ? "default" : "outline"}
          className="rounded-l-none border-l-0"
          onClick={() => onViewChange("table")}
        >
          <Table2 data-icon="inline-start" />
          Table
        </Button>
      </div>
    </div>
  );
}

function FilterSelect({
  value,
  placeholder,
  allLabel,
  options,
  onChange,
}: {
  value: string;
  placeholder: string;
  allLabel: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value="all">{allLabel}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option} value={option}>{option}</SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
