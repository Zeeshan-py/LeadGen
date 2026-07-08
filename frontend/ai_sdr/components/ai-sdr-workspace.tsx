"use client";

/**
 * Full AI SDR dashboard workspace.
 *
 * Owns contact metrics, filters, table interactions, bulk delete/export, and
 * contact profile display without importing the Lead Generator UI module.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BriefcaseBusiness,
  CalendarClock,
  Download,
  Eye,
  Filter,
  Mail,
  MoreHorizontal,
  Phone,
  RefreshCw,
  Search,
  Trash2,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { bulkDeleteAISDRContacts, exportAISDRContacts, getAISDRDashboard } from "../api";
import type { AISDRContact, AISDRDashboard, AISDRDashboardParams } from "../types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

const emptyDashboard: AISDRDashboard = {
  stats: {
    total_contacts: 0,
    ready_to_call: 0,
    calls_today: 0,
    interested: 0,
    qualified: 0,
    meetings_pending: 0,
    average_call_duration_seconds: 0,
    conversion_rate: 0,
  },
  contacts: [],
  filters: {
    statuses: [],
    industries: [],
    cities: [],
    sources: [],
  },
  total: 0,
};

const metricCards = [
  { key: "total_contacts", label: "Total Contacts", icon: Users },
  { key: "ready_to_call", label: "Ready to Call", icon: Phone },
  { key: "calls_today", label: "Calls Today", icon: CalendarClock },
  { key: "interested", label: "Interested", icon: TrendingUp },
  { key: "qualified", label: "Qualified", icon: UserCheck },
  { key: "meetings_pending", label: "Meetings Pending", icon: BriefcaseBusiness },
  { key: "average_call_duration_seconds", label: "Average Call Duration", icon: CalendarClock },
  { key: "conversion_rate", label: "Conversion Rate", icon: TrendingUp },
] as const;

const pipelineLabels: Record<string, string> = {
  new: "New",
  qualified: "Qualified",
  email_generated: "Email Generated",
  email_sent: "Email Sent",
  opened: "Opened",
  replied: "Replied",
  interested: "Interested",
  meeting_scheduled: "Meeting Scheduled",
  won: "Won",
  lost: "Lost",
  archived: "Archived",
};

function formatDate(value: string | null) {
  if (!value) return "Unscheduled";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

function metricValue(metric: (typeof metricCards)[number], dashboard: AISDRDashboard) {
  const value = dashboard.stats[metric.key];
  if (metric.key === "average_call_duration_seconds") {
    return formatDuration(value);
  }
  if (metric.key === "conversion_rate") {
    return `${value}%`;
  }
  return value.toLocaleString();
}

function labelFor(value: string) {
  return pipelineLabels[value] ?? value.replaceAll("_", " ");
}

function statusVariant(value: string) {
  if (["interested", "meeting_scheduled", "won", "completed", "stored"].includes(value)) {
    return "default" as const;
  }
  if (["lost", "archived", "failed"].includes(value)) {
    return "destructive" as const;
  }
  return "secondary" as const;
}

function sourceLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function AISDRWorkspace() {
  const [dashboard, setDashboard] = useState<AISDRDashboard>(emptyDashboard);
  const [filters, setFilters] = useState<AISDRDashboardParams>({});
  const [searchDraft, setSearchDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [selectedContact, setSelectedContact] = useState<AISDRContact | null>(null);

  const selectedContacts = useMemo(
    () => dashboard.contacts.filter((contact) => selectedIds.has(contact.id)),
    [dashboard.contacts, selectedIds],
  );
  const allVisibleSelected = dashboard.contacts.length > 0 && selectedIds.size === dashboard.contacts.length;

  const refresh = useCallback(async (nextFilters: AISDRDashboardParams) => {
    setLoading(true);
    try {
      const nextDashboard = await getAISDRDashboard(nextFilters);
      setDashboard(nextDashboard);
      setSelectedIds(new Set());
    } catch (error) {
      setDashboard(emptyDashboard);
      toast.error(error instanceof Error ? error.message : "AI SDR dashboard could not load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh({});
  }, [refresh]);

  function updateFilter(key: keyof AISDRDashboardParams, value: string) {
    const nextFilters = {
      ...filters,
      [key]: value === "all" ? "" : value,
    };
    setFilters(nextFilters);
    refresh(nextFilters);
  }

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextFilters = { ...filters, search: searchDraft.trim() };
    setFilters(nextFilters);
    refresh(nextFilters);
  }

  function toggleContact(id: string) {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleBulkSelect() {
    setSelectedIds(allVisibleSelected ? new Set() : new Set(dashboard.contacts.map((contact) => contact.id)));
  }

  async function bulkExport() {
    const ids = selectedContacts.length ? selectedContacts.map((contact) => contact.id) : dashboard.contacts.map((contact) => contact.id);
    if (!ids.length) {
      toast.error("No contacts to export");
      return;
    }
    try {
      const blob = await exportAISDRContacts(ids);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "leadforge-ai-sdr-contacts.csv";
      link.click();
      URL.revokeObjectURL(url);
      toast.success("Contacts exported");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    }
  }

  async function bulkDelete() {
    const ids = selectedContacts.map((contact) => contact.id);
    if (!ids.length) {
      toast.error("Select contacts before deleting");
      return;
    }
    const confirmed = window.confirm(`Delete ${ids.length} selected AI SDR contact${ids.length === 1 ? "" : "s"} from the active dashboard?`);
    if (!confirmed) {
      return;
    }
    try {
      const result = await bulkDeleteAISDRContacts(ids);
      toast.success(`${result.updated} contact${result.updated === 1 ? "" : "s"} removed from AI SDR`);
      await refresh(filters);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Bulk delete failed");
    }
  }

  function plannedAction(action: string) {
    toast.info(`${action} is not active in this architecture pass`);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="font-heading text-2xl font-semibold tracking-normal">AI SDR Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Contacts, readiness, and pipeline movement from the independent SDR module.
          </p>
        </div>
        <Button variant="outline" onClick={() => refresh(filters)} disabled={loading}>
          <RefreshCw data-icon="inline-start" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.key} size="sm">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-3">
                  <span>{metric.label}</span>
                  <Icon className="text-muted-foreground" />
                </CardTitle>
                <CardDescription className="text-3xl font-semibold text-foreground">
                  {metricValue(metric, dashboard)}
                </CardDescription>
              </CardHeader>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <CardTitle>Contacts</CardTitle>
              <CardDescription>{dashboard.total.toLocaleString()} contacts in the current SDR view</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={toggleBulkSelect}>
                <UserCheck data-icon="inline-start" />
                Bulk Select
              </Button>
              <Button variant="outline" disabled title="Bulk calling is not built yet">
                <Phone data-icon="inline-start" />
                Bulk Call
              </Button>
              <Button variant="outline" disabled={!selectedIds.size} onClick={bulkDelete}>
                <Trash2 data-icon="inline-start" />
                Bulk Delete
              </Button>
              <Button variant="outline" onClick={bulkExport}>
                <Download data-icon="inline-start" />
                Bulk Export
              </Button>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1.4fr_repeat(4,minmax(140px,1fr))]">
            <form onSubmit={submitSearch} className="flex gap-2">
              <Field className="min-w-0 flex-1">
                <FieldLabel htmlFor="ai-sdr-search" className="sr-only">
                  Search
                </FieldLabel>
                <Input
                  id="ai-sdr-search"
                  value={searchDraft}
                  onChange={(event) => setSearchDraft(event.target.value)}
                  placeholder="Search contacts"
                />
              </Field>
              <Button type="submit" variant="secondary">
                <Search data-icon="inline-start" />
                Search
              </Button>
            </form>
            <FilterSelect
              label="Status"
              value={filters.status}
              options={dashboard.filters.statuses}
              onChange={(value) => updateFilter("status", value)}
            />
            <FilterSelect
              label="Industry"
              value={filters.industry}
              options={dashboard.filters.industries}
              onChange={(value) => updateFilter("industry", value)}
            />
            <FilterSelect
              label="City"
              value={filters.city}
              options={dashboard.filters.cities}
              onChange={(value) => updateFilter("city", value)}
            />
            <FilterSelect
              label="Source"
              value={filters.source}
              options={dashboard.filters.sources}
              onChange={(value) => updateFilter("source", value)}
            />
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={allVisibleSelected}
                    onCheckedChange={toggleBulkSelect}
                    aria-label="Select all contacts"
                  />
                </TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Industry</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Pipeline Stage</TableHead>
                <TableHead>Next Follow-up</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {dashboard.contacts.map((contact) => (
                <TableRow
                  key={contact.id}
                  className={cn(selectedIds.has(contact.id) && "bg-muted/50")}
                >
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(contact.id)}
                      onCheckedChange={() => toggleContact(contact.id)}
                      aria-label={`Select ${contact.company}`}
                    />
                  </TableCell>
                  <TableCell>
                    <button
                      type="button"
                      className="max-w-56 truncate text-left font-medium hover:text-primary"
                      onClick={() => setSelectedContact(contact)}
                    >
                      {contact.company || "Unknown Company"}
                    </button>
                  </TableCell>
                  <TableCell>{contact.contact || "Unassigned"}</TableCell>
                  <TableCell className="font-mono text-xs">{contact.phone || "No phone"}</TableCell>
                  <TableCell className="max-w-56 truncate">{contact.email || "No email"}</TableCell>
                  <TableCell>{contact.industry || "Uncategorized"}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(contact.status)}>{labelFor(contact.status)}</Badge>
                  </TableCell>
                  <TableCell>{sourceLabel(contact.source)}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(contact.pipeline_stage)}>{labelFor(contact.pipeline_stage)}</Badge>
                  </TableCell>
                  <TableCell>{formatDate(contact.next_follow_up)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon-sm" onClick={() => setSelectedContact(contact)}>
                        <Eye />
                        <span className="sr-only">View profile</span>
                      </Button>
                      <Button variant="ghost" size="icon-sm" asChild>
                        <Link
                          href={`/ai-sdr/call?contactId=${contact.id}`}
                          scroll={false}
                          title="Open AI Calling Workspace"
                        >
                          <Phone />
                          <span className="sr-only">Call contact</span>
                        </Link>
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm">
                            <MoreHorizontal />
                            <span className="sr-only">More actions</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuGroup>
                            <DropdownMenuItem onClick={() => setSelectedContact(contact)}>
                              <Eye />
                              Open Profile
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => plannedAction("Delete")}>
                              <Trash2 />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuGroup>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!dashboard.contacts.length ? (
                <TableRow>
                  <TableCell colSpan={11} className="h-32 text-center text-muted-foreground">
                    No AI SDR contacts found
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <ContactProfileSheet
        contact={selectedContact}
        onOpenChange={(open) => {
          if (!open) setSelectedContact(null);
        }}
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <Field>
      <FieldLabel className="flex items-center gap-1 text-xs">
        <Filter />
        {label}
      </FieldLabel>
      <Select value={value || "all"} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="all">All {label}</SelectItem>
            {options.map((option) => (
              <SelectItem key={option} value={option}>
                {labelFor(option)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </Field>
  );
}

function ContactProfileSheet({
  contact,
  onOpenChange,
}: {
  contact: AISDRContact | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={Boolean(contact)} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {contact ? (
          <>
            <SheetHeader>
              <SheetTitle>{contact.company || "Unknown Company"}</SheetTitle>
              <SheetDescription>
                {contact.contact || "Unassigned contact"} - {sourceLabel(contact.source)}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-5 px-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusVariant(contact.status)}>{labelFor(contact.status)}</Badge>
                <Badge variant={statusVariant(contact.pipeline_stage)}>{labelFor(contact.pipeline_stage)}</Badge>
                <Badge variant="outline">{contact.industry || "Uncategorized"}</Badge>
              </div>
              <Separator />
              <ProfileSection
                title="Contact"
                rows={[
                  ["Name", contact.contact || "Unassigned"],
                  ["Phone", contact.phone || "No phone"],
                  ["Email", contact.email || "No email"],
                  ["Website", contact.website || "No website"],
                ]}
              />
              <ProfileSection
                title="SDR"
                rows={[
                  ["Status", labelFor(contact.status)],
                  ["Pipeline Stage", labelFor(contact.pipeline_stage)],
                  ["Source", sourceLabel(contact.source)],
                  ["Next Follow-up", formatDate(contact.next_follow_up)],
                  ["Last Contacted", formatDate(contact.last_contacted_at)],
                ]}
              />
              <ProfileSection
                title="Market"
                rows={[
                  ["Industry", contact.industry || "Uncategorized"],
                  ["City", contact.city || "Unknown"],
                  ["State", contact.state || "Unknown"],
                  ["Country", contact.country || "Unknown"],
                ]}
              />
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-medium">Notes</h3>
                <p className="rounded-lg border border-border/70 bg-muted/30 p-3 text-sm text-muted-foreground">
                  {contact.notes || "No notes recorded"}
                </p>
              </div>
            </div>
            <SheetFooter>
              <Button asChild>
                <Link href={`/ai-sdr/call?contactId=${contact.id}`} scroll={false}>
                  <Phone data-icon="inline-start" />
                  Call
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <a href={contact.email ? `mailto:${contact.email}` : undefined}>
                  <Mail data-icon="inline-start" />
                  Email
                </a>
              </Button>
            </SheetFooter>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function ProfileSection({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="grid gap-2">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[140px_1fr] gap-3 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="min-w-0 truncate font-medium">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
