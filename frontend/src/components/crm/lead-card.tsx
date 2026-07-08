"use client";

import { CalendarDays, Mail, MapPin, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { relativeDateLabel, dateLabel } from "@/lib/format";
import type { CrmLead } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LeadCard({
  lead,
  selected,
  onClick,
}: {
  lead: CrmLead;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full flex-col gap-3 rounded-lg border border-border/70 bg-card/70 p-3 text-left transition [contain-intrinsic-size:180px] [content-visibility:auto] hover:border-primary/40 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected && "border-primary bg-primary/5 ring-1 ring-primary/70",
      )}
      aria-label={`Open CRM profile for ${lead.business_name}`}
    >
      <div className="min-w-0">
        <p className="truncate font-medium text-foreground">{lead.business_name}</p>
        <p className="mt-1 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <UserRound className="size-3.5 shrink-0" />
          {lead.contact_name || "Contact not identified"}
        </p>
        <p className="mt-1 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <Mail className="size-3.5 shrink-0" />
          {lead.email || "No email"}
        </p>
        <p className="mt-1 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <MapPin className="size-3.5 shrink-0" />
          {[lead.country, lead.industry].filter(Boolean).join(" · ") || "Location unknown"}
        </p>
      </div>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/15 font-semibold text-primary">
            {lead.assigned_user?.initials || "—"}
          </span>
          <span className="truncate">{lead.assigned_user?.name || "Unassigned"}</span>
        </div>
        <span className="flex shrink-0 items-center gap-1">
          <CalendarDays className="size-3.5" />
          {lead.next_follow_up_at ? dateLabel(lead.next_follow_up_at) : "No follow-up"}
        </span>
      </div>
      {lead.tags.length ? (
        <div className="flex flex-wrap gap-1.5">
          {lead.tags.slice(0, 3).map((tag) => (
            <Badge key={tag.id} variant="outline">
              {tag.name}
            </Badge>
          ))}
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Last contacted: {relativeDateLabel(lead.last_contacted_at)}
      </p>
    </button>
  );
}
