"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { CrmKanban } from "@/components/crm/crm-kanban";
import { CrmTable } from "@/components/crm/crm-table";
import {
  CrmToolbar,
  type CrmFilters,
} from "@/components/crm/crm-toolbar";
import { LeadDetailSheet } from "@/components/crm/lead-detail-sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { getCrmLead, getCrmLeads, getCrmUsers } from "@/lib/api";
import { trackCrmUsage } from "@/lib/analytics";
import {
  crmStages,
  type CrmLead,
  type CrmLeadDetail,
  type CrmStage,
  type CrmUser,
} from "@/lib/types";

const initialFilters: CrmFilters = {
  search: "",
  stage: "all",
  country: "all",
  industry: "all",
  assignedUserId: "all",
  createdFrom: "",
  lastContactedFrom: "",
};

const emptyStageCounts = Object.fromEntries(
  crmStages.map((stage) => [stage, 0]),
) as Record<CrmStage, number>;

export function CrmWorkspace() {
  const [leads, setLeads] = useState<CrmLead[]>([]);
  const [users, setUsers] = useState<CrmUser[]>([]);
  const [stageCounts, setStageCounts] = useState(emptyStageCounts);
  const [filters, setFilters] = useState(initialFilters);
  const [view, setView] = useState<"kanban" | "table">("kanban");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CrmLeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const deferredSearch = useDeferredValue(filters.search);

  useEffect(() => {
    trackCrmUsage("view_crm");
    getCrmUsers().then(setUsers).catch((error) => toast.error(error.message));
  }, []);

  const params = useMemo(() => {
    const next: Record<string, string> = {};
    if (deferredSearch.trim()) next.search = deferredSearch.trim();
    if (filters.stage !== "all") next.stage = filters.stage;
    if (filters.country !== "all") next.country = filters.country;
    if (filters.industry !== "all") next.industry = filters.industry;
    if (filters.assignedUserId !== "all") next.assigned_user_id = filters.assignedUserId;
    if (filters.createdFrom) {
      next.created_from = new Date(`${filters.createdFrom}T00:00:00`).toISOString();
    }
    if (filters.lastContactedFrom) {
      next.last_contacted_from = new Date(`${filters.lastContactedFrom}T00:00:00`).toISOString();
    }
    return next;
  }, [deferredSearch, filters]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getCrmLeads(params)
      .then((result) => {
        if (!active) return;
        setLeads(result.items);
        setStageCounts(result.stage_counts);
      })
      .catch((error) => active && toast.error(error.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [params]);

  const countries = useMemo(
    () => Array.from(new Set(leads.map((lead) => lead.country).filter(Boolean))).sort(),
    [leads],
  );
  const industries = useMemo(
    () => Array.from(new Set(leads.map((lead) => lead.industry).filter(Boolean))).sort(),
    [leads],
  );

  async function selectLead(lead: CrmLead) {
    setSelectedId(lead.id);
    trackCrmUsage("open_lead_detail", { stage: lead.crm_stage });
    try {
      setDetail(await getCrmLead(lead.id));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lead profile could not be loaded");
      setSelectedId(null);
    }
  }

  function handleUpdated(updated: CrmLeadDetail) {
    setDetail(updated);
    setLeads((current) =>
      current.map((lead) => (lead.id === updated.id ? updated : lead)),
    );
    if (updated.crm_stage !== detail?.crm_stage) {
      trackCrmUsage("stage_changed", { stage: updated.crm_stage });
      getCrmLeads(params)
        .then((result) => {
          setLeads(result.items);
          setStageCounts(result.stage_counts);
        })
        .catch((error) => toast.error(error.message));
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <CrmToolbar
        filters={filters}
        users={users}
        countries={countries}
        industries={industries}
        view={view}
        onFiltersChange={setFilters}
        onViewChange={setView}
      />
      {loading ? (
        <CrmLoading />
      ) : view === "kanban" ? (
        <CrmKanban
          leads={leads}
          stageCounts={stageCounts}
          selectedId={selectedId}
          onSelect={selectLead}
        />
      ) : (
        <CrmTable leads={leads} onSelect={selectLead} />
      )}
      <LeadDetailSheet
        lead={detail}
        users={users}
        open={Boolean(selectedId && detail)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setSelectedId(null);
            setDetail(null);
          }
        }}
        onUpdated={handleUpdated}
      />
    </div>
  );
}

function CrmLoading() {
  return (
    <div className="grid grid-flow-col auto-cols-[270px] gap-1 overflow-hidden">
      {Array.from({ length: 5 }, (_, index) => (
        <div key={index} className="flex min-h-[520px] flex-col gap-2 rounded-lg border border-border/70 p-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ))}
    </div>
  );
}
