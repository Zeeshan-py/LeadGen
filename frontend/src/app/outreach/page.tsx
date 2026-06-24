"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, Mail, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { getLeads, getOutreach, regenerateOutreach, sendEmail, syncEmailStatuses } from "@/lib/api";
import type { Lead, Outreach } from "@/lib/types";

const versions = [
  { key: "cold_email", label: "Cold Email" },
  { key: "follow_up_1", label: "Follow Up 1" },
  { key: "follow_up_2", label: "Follow Up 2" },
] as const;

export default function OutreachPage() {
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [version, setVersion] = useState<(typeof versions)[number]["key"]>("cold_email");

  useEffect(() => {
    Promise.all([getOutreach(), getLeads({ limit: "500" })])
      .then(([outreachRows, leadRows]) => {
        setOutreach(outreachRows);
        setLeads(leadRows);
        setSelectedId(outreachRows[0]?.id ?? "");
      })
      .catch((error) => toast.error(error.message));
  }, []);

  const leadById = useMemo(() => new Map(leads.map((lead) => [lead.id, lead])), [leads]);
  const selected = outreach.find((item) => item.id === selectedId) ?? outreach[0];
  const selectedLead = selected ? leadById.get(selected.lead_id) : undefined;
  const body = selected ? selected[version] : "";

  async function copyText() {
    await navigator.clipboard.writeText(body);
    toast.success("Copied");
  }

  async function onSend() {
    if (!selected) return;
    try {
      const updated = await sendEmail(selected.id, version);
      setOutreach((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      toast.success("Email sent through Gmail");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Email send failed");
    }
  }

  async function onRegenerate() {
    if (!selected) return;
    try {
      const updated = await regenerateOutreach(selected.lead_id);
      setOutreach((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      toast.success("Outreach regenerated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Regeneration failed");
    }
  }

  async function onSync() {
    try {
      const result = await syncEmailStatuses();
      toast.success(
        `Checked ${result.checked} sent emails. Replies: ${result.replied}. Closed: ${result.closed}.`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sync failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      <Card className="glass-panel h-fit">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="size-5 text-primary" />
            Outreach Queue
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Select value={selectedId} onValueChange={setSelectedId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a lead" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {outreach.map((item) => {
                  const lead = leadById.get(item.lead_id);
                  return (
                    <SelectItem key={item.id} value={item.id}>
                      {lead?.business_name ?? item.lead_id}
                    </SelectItem>
                  );
                })}
              </SelectGroup>
            </SelectContent>
          </Select>
          {selectedLead ? (
            <div className="rounded-lg border border-border/70 bg-secondary/30 p-4">
              <p className="font-medium">{selectedLead.business_name}</p>
              <p className="mt-1 text-sm text-muted-foreground">{selectedLead.email || "No email captured yet"}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusBadge value={selectedLead.outreach_status} />
                <StatusBadge value={selected?.status ?? "draft"} />
              </div>
            </div>
          ) : (
            <p className="rounded-lg border border-border/70 bg-secondary/30 p-4 text-sm text-muted-foreground">
              Outreach drafts appear here after a lead generation run.
            </p>
          )}
          <Button variant="outline" onClick={onSync}>
            <ShieldCheck data-icon="inline-start" />
            Sync Replies
          </Button>
        </CardContent>
      </Card>

      <Card className="glass-panel">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>{selected?.subject_line || "No outreach draft selected"}</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">{selected?.personalized_first_line}</p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button variant="outline" onClick={copyText} disabled={!selected}>
              <Copy data-icon="inline-start" />
              Copy
            </Button>
            <Button variant="outline" onClick={onRegenerate} disabled={!selected}>
              <RefreshCw data-icon="inline-start" />
              Regenerate
            </Button>
            <Button onClick={onSend} disabled={!selected || !selectedLead?.email}>
              <Send data-icon="inline-start" />
              Send Email
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={version} onValueChange={(value) => setVersion(value as typeof version)}>
            <TabsList>
              {versions.map((item) => (
                <TabsTrigger key={item.key} value={item.key}>
                  {item.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {versions.map((item) => (
              <TabsContent key={item.key} value={item.key}>
                <Textarea className="min-h-[420px] resize-none leading-7" value={selected?.[item.key] ?? ""} readOnly />
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
