"use client";

import { Mail, Phone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { dateLabel, relativeDateLabel } from "@/lib/format";
import { crmStageLabels, type CrmLead } from "@/lib/types";

export function CrmTable({
  leads,
  onSelect,
}: {
  leads: CrmLead[];
  onSelect: (lead: CrmLead) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border/70 bg-card/55">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Business</TableHead>
            <TableHead>Contact</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Country / Industry</TableHead>
            <TableHead>Assigned</TableHead>
            <TableHead>Last contacted</TableHead>
            <TableHead>Next follow-up</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <TableRow
              key={lead.id}
              role="button"
              tabIndex={0}
              className="cursor-pointer"
              onClick={() => onSelect(lead)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelect(lead);
              }}
            >
              <TableCell>
                <p className="font-medium">{lead.business_name}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {lead.tags.slice(0, 2).map((tag) => (
                    <Badge key={tag.id} variant="outline">{tag.name}</Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell>
                <p>{lead.contact_name || "—"}</p>
                <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <Mail className="size-3.5" /> {lead.email || "No email"}
                </p>
                <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <Phone className="size-3.5" /> {lead.phone || "No phone"}
                </p>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{crmStageLabels[lead.crm_stage]}</Badge>
              </TableCell>
              <TableCell>{[lead.country, lead.industry].filter(Boolean).join(" · ") || "—"}</TableCell>
              <TableCell>{lead.assigned_user?.name || "Unassigned"}</TableCell>
              <TableCell>{relativeDateLabel(lead.last_contacted_at)}</TableCell>
              <TableCell>{lead.next_follow_up_at ? dateLabel(lead.next_follow_up_at) : "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!leads.length ? (
        <p className="p-10 text-center text-sm text-muted-foreground">No leads match these filters.</p>
      ) : null}
    </div>
  );
}
