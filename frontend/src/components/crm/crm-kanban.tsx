"use client";

import { MoreHorizontal, Plus } from "lucide-react";

import { LeadCard } from "@/components/crm/lead-card";
import { Button } from "@/components/ui/button";
import {
  crmStageLabels,
  crmStages,
  type CrmLead,
  type CrmStage,
} from "@/lib/types";

export function CrmKanban({
  leads,
  stageCounts,
  selectedId,
  onSelect,
}: {
  leads: CrmLead[];
  stageCounts: Record<CrmStage, number>;
  selectedId: string | null;
  onSelect: (lead: CrmLead) => void;
}) {
  const grouped = new Map<CrmStage, CrmLead[]>(
    crmStages.map((stage) => [stage, []]),
  );
  for (const lead of leads) grouped.get(lead.crm_stage)?.push(lead);

  return (
    <div className="overflow-x-auto pb-2">
      <div className="grid min-w-max grid-flow-col auto-cols-[270px] gap-1">
        {crmStages.map((stage) => (
          <section
            key={stage}
            className="flex max-h-[calc(100svh-13rem)] min-h-[520px] flex-col rounded-lg border border-border/70 bg-card/35"
          >
            <div className="flex items-center justify-between gap-2 border-b border-border/70 px-3 py-2.5">
              <div className="flex min-w-0 items-center gap-2">
                <span className="size-2 shrink-0 rounded-full bg-primary" />
                <h2 className="truncate text-sm font-semibold">{crmStageLabels[stage]}</h2>
                <BadgeCount value={stageCounts[stage] ?? 0} />
              </div>
              <div className="flex items-center">
                <Button size="icon-xs" variant="ghost" aria-label={`Add ${crmStageLabels[stage]} lead`}>
                  <Plus />
                </Button>
                <Button size="icon-xs" variant="ghost" aria-label={`${crmStageLabels[stage]} options`}>
                  <MoreHorizontal />
                </Button>
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-2 [content-visibility:auto]">
              {(grouped.get(stage) ?? []).map((lead) => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  selected={selectedId === lead.id}
                  onClick={() => onSelect(lead)}
                />
              ))}
              {!(grouped.get(stage) ?? []).length ? (
                <p className="rounded-lg border border-dashed border-border/70 p-4 text-center text-xs text-muted-foreground">
                  No leads in this stage
                </p>
              ) : null}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function BadgeCount({ value }: { value: number }) {
  return (
    <span className="rounded-md bg-secondary px-1.5 py-0.5 text-xs text-muted-foreground">
      {value}
    </span>
  );
}
