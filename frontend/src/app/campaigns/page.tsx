"use client";

import { useEffect, useState } from "react";
import { Layers3, Plus } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createCampaign, getCampaigns } from "@/lib/api";
import type { Campaign } from "@/lib/types";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [form, setForm] = useState({
    name: "Dallas Dentists",
    city: "Dallas",
    state: "TX",
    country: "United States",
    business_type: "Dentists",
    max_leads: 50,
  });

  useEffect(() => {
    getCampaigns().then(setCampaigns).catch((error) => toast.error(error.message));
  }, []);

  async function onCreate() {
    try {
      const campaign = await createCampaign(form);
      setCampaigns((prev) => [campaign, ...prev]);
      toast.success("Campaign created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Campaign creation failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
      <Card className="glass-panel h-fit">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers3 className="size-5 text-primary" />
            Create Campaign
          </CardTitle>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="campaign-name">Campaign Name</FieldLabel>
              <Input id="campaign-name" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </Field>
            <Field>
              <FieldLabel htmlFor="campaign-business">Business Type</FieldLabel>
              <Input id="campaign-business" value={form.business_type} onChange={(event) => setForm((prev) => ({ ...prev, business_type: event.target.value }))} />
            </Field>
            <div className="grid gap-3 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="campaign-city">City</FieldLabel>
                <Input id="campaign-city" value={form.city} onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))} />
              </Field>
              <Field>
                <FieldLabel htmlFor="campaign-state">State</FieldLabel>
                <Input id="campaign-state" value={form.state} onChange={(event) => setForm((prev) => ({ ...prev, state: event.target.value }))} />
              </Field>
            </div>
            <Field>
              <FieldLabel htmlFor="campaign-country">Country</FieldLabel>
              <Input id="campaign-country" value={form.country} onChange={(event) => setForm((prev) => ({ ...prev, country: event.target.value }))} />
            </Field>
            <Field>
              <FieldLabel htmlFor="campaign-max">Max Leads</FieldLabel>
              <Input id="campaign-max" type="number" min={1} max={500} value={form.max_leads} onChange={(event) => setForm((prev) => ({ ...prev, max_leads: Number(event.target.value) }))} />
            </Field>
            <Button onClick={onCreate}>
              <Plus data-icon="inline-start" />
              Create Campaign
            </Button>
          </FieldGroup>
        </CardContent>
      </Card>

      <Card className="glass-panel overflow-hidden">
        <CardHeader>
          <CardTitle>Campaigns</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Leads Generated</TableHead>
                <TableHead>Emails Sent</TableHead>
                <TableHead>Replies</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Niche</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((campaign) => (
                <TableRow key={campaign.id}>
                  <TableCell className="font-medium">{campaign.name}</TableCell>
                  <TableCell>
                    <StatusBadge value={campaign.status} />
                  </TableCell>
                  <TableCell>{campaign.leads_generated}</TableCell>
                  <TableCell>{campaign.emails_sent}</TableCell>
                  <TableCell>{campaign.replies}</TableCell>
                  <TableCell>{[campaign.city, campaign.state, campaign.country].filter(Boolean).join(", ")}</TableCell>
                  <TableCell>{campaign.business_type}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
