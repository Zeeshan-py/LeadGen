"use client";

import { useEffect, useState } from "react";
import {
  CalendarClock,
  CheckCircle2,
  Edit3,
  ExternalLink,
  Mail,
  MessageSquarePlus,
  Phone,
  RefreshCw,
  UserRound,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { CrmStageSelect } from "@/components/crm/crm-stage-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
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
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  addCrmNote,
  syncCrmGmail,
  updateCrmLead,
  updateCrmTags,
} from "@/lib/api";
import {
  dateTimeLabel,
  relativeDateLabel,
  toDateTimeLocal,
} from "@/lib/format";
import type {
  CrmActivity,
  CrmEmailMessage,
  CrmLeadDetail,
  CrmStage,
  CrmUser,
} from "@/lib/types";

export function LeadDetailSheet({
  lead,
  users,
  open,
  onOpenChange,
  onUpdated,
}: {
  lead: CrmLeadDetail | null;
  users: CrmUser[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: (lead: CrmLeadDetail) => void;
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [followUpOpen, setFollowUpOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    business_name: "",
    contact_name: "",
    email: "",
    phone: "",
    website: "",
    address: "",
    industry: "",
    assigned_user_id: "",
    tags: "",
  });
  const [note, setNote] = useState("");
  const [followUp, setFollowUp] = useState("");

  useEffect(() => {
    if (!lead) return;
    setForm({
      business_name: lead.business_name,
      contact_name: lead.contact_name,
      email: lead.email,
      phone: lead.phone,
      website: lead.website,
      address: lead.address,
      industry: lead.industry,
      assigned_user_id: lead.assigned_user?.id ?? "unassigned",
      tags: lead.tags.map((tag) => tag.name).join(", "),
    });
    setFollowUp(toDateTimeLocal(lead.next_follow_up_at));
  }, [lead]);

  async function mutate(action: () => Promise<CrmLeadDetail>, success: string) {
    setBusy(true);
    try {
      const updated = await action();
      onUpdated(updated);
      toast.success(success);
      return updated;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "CRM update failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function changeStage(stage: CrmStage) {
    if (!lead) return;
    await mutate(() => updateCrmLead(lead.id, { crm_stage: stage }), "Stage updated");
  }

  async function saveEdit() {
    if (!lead) return;
    const updated = await mutate(
      async () => {
        await updateCrmLead(lead.id, {
          business_name: form.business_name,
          contact_name: form.contact_name,
          email: form.email,
          phone: form.phone,
          website: form.website,
          address: form.address,
          industry: form.industry,
          assigned_user_id:
            form.assigned_user_id === "unassigned" ? null : form.assigned_user_id,
        });
        return updateCrmTags(
          lead.id,
          form.tags.split(",").map((item) => item.trim()).filter(Boolean),
        );
      },
      "Lead profile updated",
    );
    if (updated) setEditOpen(false);
  }

  async function saveNote() {
    if (!lead || !note.trim()) return;
    const updated = await mutate(() => addCrmNote(lead.id, note.trim()), "Note added");
    if (updated) {
      setNote("");
      setNoteOpen(false);
    }
  }

  async function scheduleFollowUp() {
    if (!lead) return;
    const updated = await mutate(
      () =>
        updateCrmLead(lead.id, {
          next_follow_up_at: followUp ? new Date(followUp).toISOString() : null,
        }),
      "Follow-up updated",
    );
    if (updated) setFollowUpOpen(false);
  }

  if (!lead) {
    return <Sheet open={false}><SheetContent><SheetTitle>Lead profile</SheetTitle></SheetContent></Sheet>;
  }

  const recentActivity = lead.activity.slice(0, 5);
  const recentMessages = lead.email_messages.slice(-3);

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="!w-full gap-0 overflow-y-auto bg-popover/98 p-0 sm:!max-w-[620px]">
          <SheetHeader className="border-b border-border/70 p-5 pr-14">
            <SheetTitle className="text-xl font-semibold">{lead.business_name}</SheetTitle>
            <SheetDescription>
              CRM profile, Gmail conversation, notes, and activity history.
            </SheetDescription>
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <CrmStageSelect
                value={lead.crm_stage}
                onValueChange={changeStage}
                className="w-[190px]"
              />
              <Select
                value={lead.assigned_user?.id ?? "unassigned"}
                onValueChange={(value) =>
                  mutate(
                    () =>
                      updateCrmLead(lead.id, {
                        assigned_user_id: value === "unassigned" ? null : value,
                      }),
                    "Owner updated",
                  )
                }
              >
                <SelectTrigger className="w-[180px]" aria-label="Assigned user">
                  <SelectValue placeholder="Assigned user" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="unassigned">Unassigned</SelectItem>
                    {users.map((user) => (
                      <SelectItem key={user.id} value={user.id}>{user.name}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </SheetHeader>

          <div className="flex flex-wrap gap-2 border-b border-border/70 p-4">
            <Button size="sm" variant="outline" onClick={() => setEditOpen(true)}>
              <Edit3 data-icon="inline-start" /> Edit lead
            </Button>
            <Button size="sm" variant="outline" onClick={() => setNoteOpen(true)}>
              <MessageSquarePlus data-icon="inline-start" /> Add note
            </Button>
            <Button size="sm" variant="outline" onClick={() => setFollowUpOpen(true)}>
              <CalendarClock data-icon="inline-start" /> Schedule follow-up
            </Button>
            <Button size="sm" variant="outline" onClick={() => changeStage("won")}>
              <CheckCircle2 data-icon="inline-start" /> Mark won
            </Button>
            <Button size="sm" variant="destructive" onClick={() => changeStage("lost")}>
              <XCircle data-icon="inline-start" /> Mark lost
            </Button>
          </div>

          <Tabs defaultValue="overview" className="p-4">
            <TabsList variant="line" className="w-full justify-start border-b border-border/70">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="conversation">Conversation</TabsTrigger>
              <TabsTrigger value="notes">Notes</TabsTrigger>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="flex flex-col gap-5 pt-4">
              <div className="grid gap-5 sm:grid-cols-2">
                <InfoSection title="Company information">
                  <Property label="Website">
                    {lead.website ? (
                      <a className="inline-flex items-center gap-1 text-primary hover:underline" href={lead.website} target="_blank" rel="noreferrer">
                        {lead.website.replace(/^https?:\/\//, "")}
                        <ExternalLink className="size-3.5" />
                      </a>
                    ) : "—"}
                  </Property>
                  <Property label="Address">{lead.address || "—"}</Property>
                  <Property label="Industry">{lead.industry || "—"}</Property>
                  <Property label="Date created">{dateTimeLabel(lead.created_at)}</Property>
                </InfoSection>
                <InfoSection title="Contact information">
                  <Property label="Contact">
                    <span className="inline-flex items-center gap-1.5">
                      <UserRound className="size-3.5" /> {lead.contact_name || "—"}
                    </span>
                  </Property>
                  <Property label="Email">
                    <span className="inline-flex items-center gap-1.5">
                      <Mail className="size-3.5" /> {lead.email || "—"}
                    </span>
                  </Property>
                  <Property label="Phone">
                    <span className="inline-flex items-center gap-1.5">
                      <Phone className="size-3.5" /> {lead.phone || "—"}
                    </span>
                  </Property>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {lead.tags.map((tag) => (
                      <Badge key={tag.id} variant="outline">{tag.name}</Badge>
                    ))}
                  </div>
                </InfoSection>
              </div>
              <Separator />
              <div className="grid gap-5 sm:grid-cols-2">
                <Property label="Last contacted">{relativeDateLabel(lead.last_contacted_at)}</Property>
                <Property label="Next follow-up">{dateTimeLabel(lead.next_follow_up_at)}</Property>
              </div>
              <Separator />
              <div className="grid gap-5 lg:grid-cols-2">
                <InfoSection title="Recent conversation">
                  {lead.outreach_history[0] ? (
                    <ConversationPreview
                      label="AI-generated draft"
                      body={lead.outreach_history[0].cold_email}
                      date={lead.outreach_history[0].created_at}
                    />
                  ) : null}
                  {recentMessages.map((message) => (
                    <ConversationPreview
                      key={message.id}
                      label={message.direction === "sent" ? "Email sent" : "Reply received"}
                      body={message.body_text || message.snippet}
                      date={message.message_at}
                    />
                  ))}
                  {!lead.outreach_history.length && !recentMessages.length ? (
                    <p className="text-sm text-muted-foreground">No conversation history yet.</p>
                  ) : null}
                </InfoSection>
                <InfoSection title="Activity timeline">
                  <ActivityTimeline items={recentActivity} />
                </InfoSection>
              </div>
            </TabsContent>

            <TabsContent value="conversation" className="flex flex-col gap-3 pt-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                  Full Gmail conversation for this lead.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    mutate(() => syncCrmGmail(lead.id), "Gmail conversation synced")
                  }
                >
                  <RefreshCw data-icon="inline-start" /> Sync Gmail
                </Button>
              </div>
              {lead.outreach_history.length ? (
                <section className="flex flex-col gap-2">
                  <h3 className="font-semibold">AI-generated email history</h3>
                  {lead.outreach_history.map((outreach) => (
                    <div key={outreach.id} className="rounded-lg border border-border/70 bg-card/55 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium">{outreach.subject_line || "Untitled draft"}</p>
                        <Badge variant="secondary">{outreach.status}</Badge>
                      </div>
                      <p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                        {outreach.cold_email || "Draft body unavailable."}
                      </p>
                      <p className="mt-3 text-xs text-muted-foreground">
                        Generated {dateTimeLabel(outreach.created_at)}
                      </p>
                    </div>
                  ))}
                </section>
              ) : null}
              <Separator />
              <h3 className="font-semibold">Gmail thread</h3>
              {lead.email_messages.map((message) => (
                <EmailMessage key={message.id} message={message} />
              ))}
              {!lead.email_messages.length ? (
                <p className="rounded-lg border border-dashed border-border/70 p-6 text-center text-sm text-muted-foreground">
                  No sent emails or replies have been stored yet.
                </p>
              ) : null}
            </TabsContent>

            <TabsContent value="notes" className="flex flex-col gap-3 pt-4">
              <Button className="self-start" size="sm" onClick={() => setNoteOpen(true)}>
                <MessageSquarePlus data-icon="inline-start" /> Add note
              </Button>
              {lead.note_history.map((item) => (
                <div key={item.id} className="rounded-lg border border-border/70 bg-card/55 p-4">
                  <p className="whitespace-pre-wrap leading-6">{item.body}</p>
                  <p className="mt-3 text-xs text-muted-foreground">
                    {item.created_by} · {dateTimeLabel(item.created_at)}
                  </p>
                </div>
              ))}
              {!lead.note_history.length ? (
                <p className="text-sm text-muted-foreground">No notes added yet.</p>
              ) : null}
            </TabsContent>

            <TabsContent value="timeline" className="pt-4">
              <ActivityTimeline items={lead.activity} />
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-h-[90svh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit lead</DialogTitle>
            <DialogDescription>Update company, contact, assignment, and tags.</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <EditField label="Business name" value={form.business_name} onChange={(value) => setForm({ ...form, business_name: value })} />
            <EditField label="Contact name" value={form.contact_name} onChange={(value) => setForm({ ...form, contact_name: value })} />
            <EditField label="Email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} />
            <EditField label="Phone" value={form.phone} onChange={(value) => setForm({ ...form, phone: value })} />
            <EditField label="Website" value={form.website} onChange={(value) => setForm({ ...form, website: value })} />
            <EditField label="Address" value={form.address} onChange={(value) => setForm({ ...form, address: value })} />
            <EditField label="Industry" value={form.industry} onChange={(value) => setForm({ ...form, industry: value })} />
            <EditField label="Tags" value={form.tags} onChange={(value) => setForm({ ...form, tags: value })} />
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button disabled={busy} onClick={saveEdit}>Save lead</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={noteOpen} onOpenChange={setNoteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add note</DialogTitle>
            <DialogDescription>Notes are saved to the lead timeline.</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="crm-note">Note</FieldLabel>
              <Textarea id="crm-note" value={note} onChange={(event) => setNote(event.target.value)} rows={6} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteOpen(false)}>Cancel</Button>
            <Button disabled={busy || !note.trim()} onClick={saveNote}>Add note</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={followUpOpen} onOpenChange={setFollowUpOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule follow-up</DialogTitle>
            <DialogDescription>Choose the next date and time for this lead.</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="crm-follow-up">Follow-up date</FieldLabel>
              <Input id="crm-follow-up" type="datetime-local" value={followUp} onChange={(event) => setFollowUp(event.target.value)} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFollowUpOpen(false)}>Cancel</Button>
            <Button disabled={busy} onClick={scheduleFollowUp}>Save follow-up</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function Property({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 text-sm sm:grid-cols-[110px_1fr] sm:gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

function ConversationPreview({ label, body, date }: { label: string; body: string; date: string }) {
  return (
    <div className="border-l-2 border-primary/50 pl-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{dateTimeLabel(date)}</p>
      </div>
      <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted-foreground">{body}</p>
    </div>
  );
}

function ActivityTimeline({ items }: { items: CrmActivity[] }) {
  return (
    <div className="flex flex-col">
      {items.map((item, index) => (
        <div key={item.id} className="grid grid-cols-[16px_1fr] gap-3">
          <div className="flex flex-col items-center">
            <span className="mt-1 size-2.5 rounded-full border-2 border-primary bg-popover" />
            {index < items.length - 1 ? <span className="min-h-8 w-px flex-1 bg-border" /> : null}
          </div>
          <div className="pb-4">
            <div className="flex items-start justify-between gap-3">
              <p className="font-medium">{item.title}</p>
              <span className="text-xs text-muted-foreground">{item.actor}</span>
            </div>
            {item.description ? <p className="mt-1 text-sm text-muted-foreground">{item.description}</p> : null}
            <p className="mt-1 text-xs text-muted-foreground">{dateTimeLabel(item.created_at)}</p>
          </div>
        </div>
      ))}
      {!items.length ? <p className="text-sm text-muted-foreground">No activity recorded yet.</p> : null}
    </div>
  );
}

function EmailMessage({ message }: { message: CrmEmailMessage }) {
  return (
    <article className="rounded-lg border border-border/70 bg-card/55 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Badge variant={message.direction === "sent" ? "secondary" : "outline"}>
            {message.direction === "sent" ? "Sent" : "Received"}
          </Badge>
          <p className="mt-2 font-medium">{message.subject || "No subject"}</p>
        </div>
        <p className="text-xs text-muted-foreground">{dateTimeLabel(message.message_at)}</p>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        {message.from_email} → {message.to_email}
      </p>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-6">
        {message.body_text || message.snippet || "Message body unavailable."}
      </p>
    </article>
  );
}

function EditField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = `crm-${label.toLowerCase().replaceAll(" ", "-")}`;
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input id={id} value={value} onChange={(event) => onChange(event.target.value)} />
    </Field>
  );
}
