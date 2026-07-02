"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { csvExportUrl, getCampaigns } from "@/lib/api";
import type { Campaign } from "@/lib/types";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  useEffect(() => {
    getCampaigns().then(setCampaigns).catch((error) => toast.error(error.message));
  }, []);

  const enrichedCampaigns = campaigns.filter((campaign) => campaign.leads_generated > 0);

  return (
    <section className="flex flex-col gap-4" aria-labelledby="campaign-history-title">
      <header>
        <h2 id="campaign-history-title" className="text-lg font-semibold">Past Enriched Campaigns</h2>
        <p className="text-sm text-muted-foreground">
          {enrichedCampaigns.length} campaigns ready to export
        </p>
      </header>

      {enrichedCampaigns.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {enrichedCampaigns.map((campaign) => {
            const location = [campaign.city, campaign.state, campaign.country].filter(Boolean).join(", ");
            return (
              <Card key={campaign.id} className="gap-4 py-4">
                <CardHeader className="gap-2 px-4">
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <CardTitle className="min-w-0 truncate text-base">{campaign.name}</CardTitle>
                    <StatusBadge value={campaign.status} />
                  </div>
                  <CardDescription className="truncate">{location || "All locations"}</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-3 px-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Leads</p>
                    <p className="text-lg font-semibold">{campaign.leads_generated}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-muted-foreground">Business type</p>
                    <p className="truncate font-medium">{campaign.business_type}</p>
                  </div>
                </CardContent>
                <CardFooter className="px-4">
                  <Button asChild className="w-full">
                    <a
                      href={csvExportUrl({ scope: "all", campaignId: campaign.id })}
                      download
                    >
                      <Download data-icon="inline-start" />
                      Export {campaign.leads_generated} leads
                    </a>
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      ) : (
        <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          Enriched campaigns will appear here after a successful lead generation run.
        </p>
      )}
    </section>
  );
}
