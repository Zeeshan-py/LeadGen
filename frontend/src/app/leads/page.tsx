"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Download, Edit3, ExternalLink, Link2, MapPin, MoreHorizontal, Phone, Search } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { csvExportUrl, getCampaigns, getLeads, startManualSdrBridgeCall, updateLead } from "@/lib/api";
import { businessTypes, continents, countriesByContinent } from "@/lib/markets";
import type { Campaign, Lead } from "@/lib/types";

const socialPlatforms = [
  { key: "facebook", label: "Facebook" },
  { key: "instagram", label: "Instagram" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "youtube", label: "YouTube" },
  { key: "x_twitter", label: "X / Twitter" },
  { key: "tiktok", label: "TikTok" },
] as const;

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [scope, setScope] = useState("latest");
  const [campaignId, setCampaignId] = useState("");
  const [outreachStatus, setOutreachStatus] = useState("all");
  const [country, setCountry] = useState("all");
  const [businessType, setBusinessType] = useState("all");
  const [contact, setContact] = useState("all");
  const [sort, setSort] = useState("-created_at");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Lead | null>(null);

  useEffect(() => {
    getCampaigns().then(setCampaigns).catch((error) => toast.error(error.message));

    const campaignFromUrl = new URLSearchParams(window.location.search).get("campaign_id");
    if (campaignFromUrl) {
      setCampaignId(campaignFromUrl);
      setScope("all");
    }
  }, []);

  const leadParams = useMemo(() => {
    const params: Record<string, string> = { sort, scope };
    if (campaignId) params.campaign_id = campaignId;
    if (deferredSearch) params.search = deferredSearch;
    if (outreachStatus !== "all") params.outreach_status = outreachStatus;
    if (country !== "all") params.country = country;
    if (businessType !== "all") params.business_type = businessType;
    if (contact !== "all") params.contact = contact;
    return params;
  }, [businessType, campaignId, contact, country, deferredSearch, outreachStatus, scope, sort]);

  useEffect(() => {
    setSelected(new Set());
    getLeads(leadParams).then(setLeads).catch((error) => toast.error(error.message));
  }, [leadParams]);

  const selectedLeads = useMemo(() => leads.filter((lead) => selected.has(lead.id)), [leads, selected]);

  async function saveEdit() {
    if (!editing) return;
    try {
      const updated = await updateLead(editing.id, editing);
      setLeads((prev) => prev.map((lead) => (lead.id === updated.id ? updated : lead)));
      setEditing(null);
      toast.success("Lead updated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Update failed");
    }
  }

  async function bulkStatus(nextStatus: string) {
    await Promise.all(selectedLeads.map((lead) => updateLead(lead.id, { lead_status: nextStatus })));
    setSelected(new Set());
    const refreshed = await getLeads(leadParams);
    setLeads(refreshed);
    toast.success("Bulk action applied");
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="glass-panel rounded-lg p-4">
        <div className="mb-4 inline-flex rounded-lg border border-border/70 bg-secondary/30 p-1">
          {[
            ["latest", "Latest Leads"],
            ["all", "All Leads"],
          ].map(([value, label]) => (
            <Button
              key={value}
              size="sm"
              variant={!campaignId && scope === value ? "default" : "ghost"}
              onClick={() => {
                setCampaignId("");
                setScope(value);
              }}
            >
              {label}
            </Button>
          ))}
        </div>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="grid flex-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search leads, websites, emails, cities..." className="pl-9" />
            </div>
            <Select
              value={campaignId || "all"}
              onValueChange={(value) => {
                const nextCampaignId = value === "all" ? "" : value;
                setCampaignId(nextCampaignId);
                if (nextCampaignId) setScope("all");
              }}
            >
              <SelectTrigger className="w-full min-w-0 overflow-hidden">
                <SelectValue className="min-w-0 flex-1 truncate" placeholder="Campaign" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Campaigns</SelectItem>
                  {campaigns.map((campaign) => (
                    <SelectItem key={campaign.id} value={campaign.id}>
                      {campaign.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={country} onValueChange={setCountry}>
              <SelectTrigger><SelectValue placeholder="Country" /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Countries</SelectItem>
                  {continents.flatMap((continent) =>
                    countriesByContinent[continent].map((item) => (
                      <SelectItem key={item} value={item}>{item}</SelectItem>
                    )),
                  )}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={businessType} onValueChange={setBusinessType}>
              <SelectTrigger><SelectValue placeholder="Business type" /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Business Types</SelectItem>
                  {businessTypes.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={contact} onValueChange={setContact}>
              <SelectTrigger><SelectValue placeholder="Contact data" /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">Any Contact Data</SelectItem>
                  <SelectItem value="email">Has Email</SelectItem>
                  <SelectItem value="phone">Has Phone</SelectItem>
                  <SelectItem value="social">Has Social Links</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={outreachStatus} onValueChange={setOutreachStatus}>
              <SelectTrigger>
                <SelectValue placeholder="Outreach" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">All Outreach</SelectItem>
                  <SelectItem value="not_started">Not Started</SelectItem>
                  <SelectItem value="sent">Sent</SelectItem>
                  <SelectItem value="opened">Opened</SelectItem>
                  <SelectItem value="replied">Replied</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={sort} onValueChange={setSort}>
              <SelectTrigger>
                <SelectValue placeholder="Sort" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="-created_at">Newest</SelectItem>
                  <SelectItem value="business_name">Business Name</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" disabled={!selected.size}>Bulk Actions</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => bulkStatus("contacted")}>Mark contacted</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => bulkStatus("won")}>Mark won</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => bulkStatus("lost")}>Mark lost</DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button asChild>
              <a href={csvExportUrl({ scope, campaignId })}>
                <Download data-icon="inline-start" />
                Export CSV
              </a>
            </Button>
          </div>
        </div>
      </div>

      <div className="glass-panel overflow-hidden rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={selected.size === leads.length && leads.length > 0}
                  onCheckedChange={(checked) => setSelected(checked ? new Set(leads.map((lead) => lead.id)) : new Set())}
                  aria-label="Select all leads"
                />
              </TableHead>
              <TableHead>Business Name</TableHead>
              <TableHead>Website</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Map</TableHead>
              <TableHead>Socials</TableHead>
              <TableHead>Outreach</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.map((lead) => (
              <TableRow key={lead.id}>
                <TableCell>
                  <Checkbox
                    checked={selected.has(lead.id)}
                    onCheckedChange={(checked) => {
                      setSelected((prev) => {
                        const next = new Set(prev);
                        if (checked) next.add(lead.id);
                        else next.delete(lead.id);
                        return next;
                      });
                    }}
                    aria-label={`Select ${lead.business_name}`}
                  />
                </TableCell>
                <TableCell className="max-w-[220px] font-medium">{lead.business_name}</TableCell>
                <TableCell className="max-w-[220px] truncate">
                  {lead.website ? (
                    <a className="text-primary hover:underline" href={lead.website} target="_blank" rel="noreferrer">
                      {lead.website}
                    </a>
                  ) : (
                    <span className="text-muted-foreground">No website</span>
                  )}
                </TableCell>
                <TableCell>
                  {lead.email ? (
                    <a className="text-primary hover:underline" href={`mailto:${lead.email}`}>
                      {lead.email}
                    </a>
                  ) : (
                    <span className="text-muted-foreground">Missing</span>
                  )}
                </TableCell>
                <TableCell>
                  {lead.phone ? (
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{lead.phone}</span>
                      <ManualSdrLeadCallButton lead={lead} />
                    </div>
                  ) : (
                    <span className="text-muted-foreground">Missing</span>
                  )}
                </TableCell>
                <TableCell>
                  <MapLinkCell lead={lead} />
                </TableCell>
                <TableCell className="min-w-[210px]">
                  <SocialLinksCell lead={lead} />
                </TableCell>
                <TableCell>
                  <StatusBadge value={lead.outreach_status} />
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${lead.business_name}`}>
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuGroup>
                        <DropdownMenuItem onClick={() => setEditing(lead)}>
                          <Edit3 />
                          Edit
                        </DropdownMenuItem>
                        {lead.website ? (
                          <DropdownMenuItem asChild>
                            <a href={lead.website} target="_blank" rel="noreferrer">
                              <ExternalLink />
                              Open website
                            </a>
                          </DropdownMenuItem>
                        ) : null}
                        {lead.google_maps_url ? (
                          <DropdownMenuItem asChild>
                            <a href={lead.google_maps_url} target="_blank" rel="noreferrer">
                              <MapPin />
                              Open Maps
                            </a>
                          </DropdownMenuItem>
                        ) : null}
                        {lead.phone ? (
                          <DropdownMenuItem onClick={() => startManualLeadCall(lead)}>
                            <Phone />
                            Manual SDR Call
                          </DropdownMenuItem>
                        ) : null}
                      </DropdownMenuGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Lead</DialogTitle>
            <DialogDescription>Update lead details, status, notes, and tags.</DialogDescription>
          </DialogHeader>
          {editing ? (
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="edit-name">Business Name</FieldLabel>
                <Input id="edit-name" value={editing.business_name} onChange={(event) => setEditing({ ...editing, business_name: event.target.value })} />
              </Field>
              <Field>
                <FieldLabel htmlFor="edit-email">Email</FieldLabel>
                <Input id="edit-email" value={editing.email} onChange={(event) => setEditing({ ...editing, email: event.target.value })} />
              </Field>
              <Field>
                <FieldLabel htmlFor="edit-phone">Phone</FieldLabel>
                <Input id="edit-phone" value={editing.phone} onChange={(event) => setEditing({ ...editing, phone: event.target.value })} />
              </Field>
              <Field>
                <FieldLabel htmlFor="edit-notes">Lead Notes</FieldLabel>
                <Textarea id="edit-notes" value={editing.notes} onChange={(event) => setEditing({ ...editing, notes: event.target.value })} />
              </Field>
              <Field>
                <FieldLabel htmlFor="edit-tags">Tags</FieldLabel>
                <Input
                  id="edit-tags"
                  value={editing.tags.join(", ")}
                  onChange={(event) => setEditing({ ...editing, tags: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })}
                />
              </Field>
              <Separator />
              <Field>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <FieldLabel>Social Profiles</FieldLabel>
                  <StatusBadge value={editing.social_status} />
                </div>
                {socialPlatforms.some((platform) => editing.social_links?.[platform.key]) ? (
                  <div className="flex flex-wrap gap-2">
                    {socialPlatforms.map((platform) => {
                      const link = editing.social_links?.[platform.key];
                      return link ? (
                        <Button key={platform.key} asChild size="sm" variant="outline">
                          <a href={link} target="_blank" rel="noreferrer">
                            <ExternalLink data-icon="inline-start" />
                            {platform.label}
                          </a>
                        </Button>
                      ) : null;
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No social profiles found on the scanned website pages.</p>
                )}
              </Field>
            </FieldGroup>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={saveEdit}>Save Lead</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

async function startManualLeadCall(lead: Lead) {
  const ownerPhone = getOwnerPhoneForManualCall();
  if (!ownerPhone) return;
  try {
    await startManualSdrBridgeCall({
      to_phone: lead.phone,
      business_name: lead.business_name,
      owner_phone: ownerPhone,
    });
    toast.success("Manual SDR call started. Answer your phone to connect to the business.");
  } catch (error) {
    toast.error(error instanceof Error ? error.message : "Manual SDR call could not start");
  }
}

function ManualSdrLeadCallButton({ lead }: { lead: Lead }) {
  return (
    <Button
      type="button"
      size="icon-xs"
      variant="outline"
      onClick={() => startManualLeadCall(lead)}
      title="Manual SDR call through Twilio. AI will not speak."
      aria-label={`Manual SDR call ${lead.business_name}`}
    >
      <Phone />
    </Button>
  );
}

function MapLinkCell({ lead }: { lead: Lead }) {
  const href = lead.google_maps_url || googleMapsSearchUrl(lead);
  if (!href) {
    return <span className="text-muted-foreground">Missing</span>;
  }
  return (
    <Button asChild size="sm" variant="outline" className="h-7 px-2 text-xs">
      <a href={href} target="_blank" rel="noreferrer" aria-label={`Open Google Maps for ${lead.business_name}`}>
        <MapPin data-icon="inline-start" className="size-3.5" />
        Maps
      </a>
    </Button>
  );
}

function googleMapsSearchUrl(lead: Lead) {
  const query = [lead.business_name, lead.location, lead.city, lead.state, lead.country]
    .filter(Boolean)
    .join(", ");
  if (!query.trim()) return "";
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

function getOwnerPhoneForManualCall() {
  const storageKey = "leadforge_manual_sdr_owner_phone";
  const saved = window.localStorage.getItem(storageKey) || "";
  const entered = window.prompt(
    "Enter your phone number. Twilio will call you first, then connect you to the business.",
    saved,
  );
  const normalized = (entered || "").trim().replace(/[^\d+]/g, "");
  if (!normalized) return "";
  window.localStorage.setItem(storageKey, normalized);
  return normalized;
}

function SocialLinksCell({ lead }: { lead: Lead }) {
  const links = socialPlatforms
    .map((platform) => ({ ...platform, url: lead.social_links?.[platform.key] }))
    .filter((platform) => Boolean(platform.url));

  if (!links.length) {
    return <span className="text-muted-foreground">Missing</span>;
  }

  return (
    <div className="flex max-w-[260px] flex-wrap gap-1.5">
      {links.map((platform) => (
        <Button key={platform.key} asChild size="sm" variant="outline" className="h-7 px-2 text-xs">
          <a href={platform.url} target="_blank" rel="noreferrer" aria-label={`Open ${platform.label} for ${lead.business_name}`}>
            <Link2 data-icon="inline-start" className="size-3.5" />
            {shortSocialLabel(platform.key)}
          </a>
        </Button>
      ))}
    </div>
  );
}

function shortSocialLabel(key: (typeof socialPlatforms)[number]["key"]) {
  if (key === "x_twitter") {
    return "X";
  }
  return socialPlatforms.find((platform) => platform.key === key)?.label ?? key;
}
