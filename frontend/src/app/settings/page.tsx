"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bell,
  BookOpen,
  Bot,
  ChevronRight,
  CreditCard,
  Download,
  FileText,
  Globe2,
  HelpCircle,
  KeyRound,
  Languages,
  LifeBuoy,
  LockKeyhole,
  Mail,
  MessageSquarePlus,
  Monitor,
  PhoneCall,
  RefreshCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Unplug,
  UserRound,
  Webhook,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PlanBadge } from "@/components/subscription-gate";
import {
  checkGmailConnection,
  checkTwilioConnection,
  connectTwilio,
  createBillingPortalSession,
  csvExportUrl,
  disconnectGmail,
  disconnectTwilio,
  getBillingOverview,
  getGmailConnection,
  getSettings,
  getTwilioConnection,
  getVoiceSettings,
  gmailConnectUrl,
  saveSettings,
  saveVoiceSettings,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSubscription } from "@/lib/subscription";
import type {
  BillingOverview,
  FeatureKey,
  GmailConnectionStatus,
  TwilioConnectionStatus,
  VoiceSettingsStatus,
  VoiceSpeed,
} from "@/lib/types";

const planLeadLimits: Record<string, number> = {
  free: 10,
  basic: 400,
  agent: 800,
  agency: 1500,
};

export default function SettingsPage() {
  const { user } = useAuth();
  const subscription = useSubscription();
  const [settingsForm, setSettingsForm] = useState({
    default_lead_limit: 50,
    include_screenshots: true,
  });
  const [workspaceForm, setWorkspaceForm] = useState({
    workspace_name: "LeadForge AI",
    company: "",
    business_type: "",
    country: "",
    default_industry: "",
    default_location: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    language: "English",
  });
  const [notifications, setNotifications] = useState({
    email: true,
    marketing: false,
    campaigns: true,
    billing: true,
    security: true,
  });
  const [preferences, setPreferences] = useState({
    dark_mode: true,
    default_view: "dashboard",
    items_per_page: "50",
    table_density: "comfortable",
  });
  const [gmailStatus, setGmailStatus] = useState<GmailConnectionStatus | null>(null);
  const [twilioStatus, setTwilioStatus] = useState<TwilioConnectionStatus | null>(null);
  const [billing, setBilling] = useState<BillingOverview | null>(null);
  const [twilioForm, setTwilioForm] = useState({
    account_sid: "",
    auth_token: "",
    phone_sid: "",
  });
  const [voiceForm, setVoiceForm] = useState({
    voice_id: "",
    voice_name: "",
    speaking_speed: "normal" as VoiceSpeed,
    language: "en",
    ai_greeting: "",
    business_name: "",
    assistant_name: "",
  });
  const [loading, setLoading] = useState(true);
  const [checkingGmail, setCheckingGmail] = useState(false);
  const [disconnectingGmail, setDisconnectingGmail] = useState(false);
  const [connectingTwilio, setConnectingTwilio] = useState(false);
  const [checkingTwilio, setCheckingTwilio] = useState(false);
  const [disconnectingTwilio, setDisconnectingTwilio] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingVoice, setSavingVoice] = useState(false);
  const [openingPortal, setOpeningPortal] = useState(false);
  const canOutreach = !subscription.loading && subscription.hasFeature("outreach");
  const canTwilio = !subscription.loading && subscription.hasFeature("twilio");
  const canExport = !subscription.loading && subscription.hasFeature("csv_export");

  useEffect(() => {
    if (subscription.loading) return;
    let mounted = true;
    setLoading(true);
    Promise.allSettled([
      getSettings(),
      canOutreach ? getGmailConnection() : Promise.resolve(null),
      canTwilio ? getTwilioConnection() : Promise.resolve(null),
      canTwilio ? getVoiceSettings() : Promise.resolve(null),
      getBillingOverview(),
    ])
      .then(([settings, gmail, twilio, voice, billingOverview]) => {
        if (!mounted) return;
        if (settings.status === "fulfilled") {
          const exportSettings = settings.value.export_settings as { include_screenshots?: boolean } | undefined;
          setSettingsForm((prev) => ({
            ...prev,
            default_lead_limit: Number(settings.value.default_lead_limit ?? prev.default_lead_limit),
            include_screenshots: exportSettings?.include_screenshots ?? prev.include_screenshots,
          }));
        }
        if (gmail.status === "fulfilled") setGmailStatus(gmail.value);
        if (twilio.status === "fulfilled") setTwilioStatus(twilio.value);
        if (voice.status === "fulfilled" && voice.value) applyVoiceSettings(voice.value);
        if (billingOverview.status === "fulfilled") setBilling(billingOverview.value);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Settings failed to load"))
      .finally(() => {
        if (mounted) setLoading(false);
      });

    const gmailResult = new URLSearchParams(window.location.search).get("gmail");
    if (gmailResult === "connected") {
      toast.success("Gmail connected");
      window.history.replaceState(null, "", window.location.pathname);
    } else if (gmailResult === "cancelled") {
      toast.info("Gmail connection cancelled");
      window.history.replaceState(null, "", window.location.pathname);
    } else if (gmailResult === "error") {
      toast.error("Gmail connection failed. Please try reconnecting.");
      window.history.replaceState(null, "", window.location.pathname);
    }

    return () => {
      mounted = false;
    };
  }, [canOutreach, canTwilio, subscription.loading]);

  const planKey = subscription.access?.plan_key || billing?.subscription?.access_plan || "free";
  const leadLimit = subscription.access?.lead_limit ?? planLeadLimits[planKey] ?? planLeadLimits.free;
  const leadsUsed = subscription.access?.leads_used ?? 0;
  const planName = titleCase(planKey);
  const renewalDate = billing?.subscription?.next_billed_at || billing?.subscription?.access_until || "";
  const billingStatus = billing?.subscription?.status || "None";

  const integrationCards = useMemo(
    () => [
      {
        title: "Google",
        detail: user?.provider === "google" ? "Connected for account sign-in." : "Available for account sign-in.",
        status: user?.provider === "google" ? "Connected" : "Available",
        icon: Globe2,
        active: user?.provider === "google",
      },
      {
        title: "Gmail",
        detail: gmailStatus?.is_connected ? gmailStatus.gmail_email || "Connected for outreach sending." : "Connect your mailbox for outreach sending.",
        status: canOutreach ? (gmailStatus?.is_connected ? "Connected" : "Not connected") : "Locked",
        icon: Mail,
        active: Boolean(gmailStatus?.is_connected),
        feature: "outreach" as FeatureKey,
        locked: !canOutreach,
      },
      {
        title: "Calling",
        detail: twilioStatus?.is_connected ? twilioStatus.phone_number || "Connected for AI SDR calls." : "Connect a phone account for AI SDR calls.",
        status: canTwilio ? (twilioStatus?.is_connected ? "Connected" : "Not connected") : "Locked",
        icon: PhoneCall,
        active: Boolean(twilioStatus?.is_connected),
        feature: "twilio" as FeatureKey,
        locked: !canTwilio,
      },
      {
        title: "Slack",
        detail: "Team alerts and campaign summaries.",
        status: "Coming soon",
        icon: MessageSquarePlus,
        active: false,
      },
      {
        title: "Zapier",
        detail: "Automation recipes for external tools.",
        status: "Coming soon",
        icon: Zap,
        active: false,
      },
      {
        title: "Webhooks",
        detail: "Send workspace events to your stack.",
        status: "Coming soon",
        icon: Webhook,
        active: false,
      },
    ],
    [canOutreach, canTwilio, gmailStatus, twilioStatus, user],
  );

  function onConnectGmail() {
    if (!canOutreach) {
      subscription.openUpgrade("outreach");
      return;
    }
    window.location.href = gmailConnectUrl();
  }

  async function onSavePreferences() {
    setSavingSettings(true);
    try {
      await saveSettings({
        default_lead_limit: settingsForm.default_lead_limit,
        export_settings: {
          include_screenshots: settingsForm.include_screenshots,
        },
      });
      toast.success("Workspace preferences saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Settings save failed");
    } finally {
      setSavingSettings(false);
    }
  }

  async function refreshGmailStatus() {
    if (!canOutreach) return;
    try {
      setGmailStatus(await getGmailConnection());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Gmail status failed");
    }
  }

  async function onCheckGmail() {
    if (!canOutreach) {
      subscription.openUpgrade("outreach");
      return;
    }
    setCheckingGmail(true);
    try {
      const status = await checkGmailConnection();
      setGmailStatus(status);
      toast.success("Gmail connection healthy");
    } catch (error) {
      await refreshGmailStatus();
      toast.error(error instanceof Error ? error.message : "Gmail health check failed");
    } finally {
      setCheckingGmail(false);
    }
  }

  async function onDisconnectGmail() {
    if (!canOutreach) {
      subscription.openUpgrade("outreach");
      return;
    }
    setDisconnectingGmail(true);
    try {
      setGmailStatus(await disconnectGmail());
      toast.success("Gmail disconnected");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Gmail disconnect failed");
    } finally {
      setDisconnectingGmail(false);
    }
  }

  async function onConnectTwilio() {
    if (!canTwilio) {
      subscription.openUpgrade("twilio");
      return;
    }
    if (!twilioForm.account_sid.trim() || !twilioForm.auth_token.trim()) {
      toast.error("Enter your calling account credentials");
      return;
    }
    setConnectingTwilio(true);
    try {
      const status = await connectTwilio({
        account_sid: twilioForm.account_sid.trim(),
        auth_token: twilioForm.auth_token.trim(),
        phone_sid: twilioForm.phone_sid,
      });
      setTwilioStatus(status);
      if (status.requires_phone_selection) {
        toast.info("Choose the phone number for AI SDR calls");
      } else {
        toast.success("Calling connected");
        setTwilioForm({ account_sid: "", auth_token: "", phone_sid: "" });
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Calling connection failed");
    } finally {
      setConnectingTwilio(false);
    }
  }

  async function onCheckTwilio() {
    if (!canTwilio) {
      subscription.openUpgrade("twilio");
      return;
    }
    setCheckingTwilio(true);
    try {
      const status = await checkTwilioConnection();
      setTwilioStatus(status);
      toast.success("Calling connection healthy");
    } catch (error) {
      setTwilioStatus(await getTwilioConnection().catch(() => twilioStatus));
      toast.error(error instanceof Error ? error.message : "Calling health check failed");
    } finally {
      setCheckingTwilio(false);
    }
  }

  async function onDisconnectTwilio() {
    if (!canTwilio) {
      subscription.openUpgrade("twilio");
      return;
    }
    setDisconnectingTwilio(true);
    try {
      setTwilioStatus(await disconnectTwilio());
      setTwilioForm({ account_sid: "", auth_token: "", phone_sid: "" });
      toast.success("Calling disconnected");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Calling disconnect failed");
    } finally {
      setDisconnectingTwilio(false);
    }
  }

  async function onSaveVoiceSettings() {
    if (!canTwilio) {
      subscription.openUpgrade("twilio");
      return;
    }
    setSavingVoice(true);
    try {
      const status = await saveVoiceSettings({
        voice_provider: "cartesia",
        ...voiceForm,
      });
      applyVoiceSettings(status);
      toast.success("Voice profile saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Voice profile save failed");
    } finally {
      setSavingVoice(false);
    }
  }

  async function openBillingPortal() {
    setOpeningPortal(true);
    try {
      const session = await createBillingPortalSession();
      window.location.href = session.url;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Billing portal failed");
    } finally {
      setOpeningPortal(false);
    }
  }

  function applyVoiceSettings(settings: VoiceSettingsStatus) {
    setVoiceForm({
      voice_id: settings.voice_id || "",
      voice_name: settings.voice_name || "",
      speaking_speed: settings.speaking_speed || "normal",
      language: settings.language || "en",
      ai_greeting: settings.ai_greeting || "",
      business_name: settings.business_name || "",
      assistant_name: settings.assistant_name || "",
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
      <section className="glass-panel rounded-lg p-5 md:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
              Account Settings
            </Badge>
            <h2 className="mt-4 text-3xl font-semibold tracking-normal md:text-4xl">Workspace controls</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Manage your profile, subscription, integrations, preferences, and support options from one place.
            </p>
          </div>
          <Button onClick={onSavePreferences} disabled={savingSettings || loading}>
            <Save data-icon="inline-start" />
            {savingSettings ? "Saving" : "Save preferences"}
          </Button>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.72fr_1fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserRound className="size-5 text-primary" />
              Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex items-center gap-4">
              <div className="grid size-14 shrink-0 place-items-center rounded-lg border border-border/70 bg-primary/10 text-lg font-semibold text-primary">
                {initials(user?.full_name || user?.email)}
              </div>
              <div className="min-w-0">
                <p className="truncate font-medium">{user?.full_name || "LeadForge user"}</p>
                <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
              </div>
            </div>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="profile-name">Name</FieldLabel>
                <Input id="profile-name" value={user?.full_name || ""} readOnly />
              </Field>
              <Field>
                <FieldLabel htmlFor="profile-email">Email</FieldLabel>
                <Input id="profile-email" value={user?.email || ""} readOnly />
              </Field>
              <Field>
                <FieldLabel htmlFor="profile-company">Company</FieldLabel>
                <Input
                  id="profile-company"
                  value={workspaceForm.company}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, company: event.target.value }))}
                  placeholder="Company name"
                />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel>Timezone</FieldLabel>
                  <Select
                    value={workspaceForm.timezone}
                    onValueChange={(value) => setWorkspaceForm((prev) => ({ ...prev, timezone: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {["UTC", "Asia/Karachi", "America/New_York", "America/Los_Angeles", "Europe/London"].map((zone) => (
                          <SelectItem key={zone} value={zone}>
                            {zone}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel>Language</FieldLabel>
                  <Select
                    value={workspaceForm.language}
                    onValueChange={(value) => setWorkspaceForm((prev) => ({ ...prev, language: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {["English", "Spanish", "French", "German"].map((language) => (
                          <SelectItem key={language} value={language}>
                            {language}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              </div>
            </FieldGroup>
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <CreditCard className="size-5 text-primary" />
              Billing
            </CardTitle>
            <Badge variant={billing?.subscription?.access_active ? "default" : "secondary"}>
              {billingStatus}
            </Badge>
          </CardHeader>
          <CardContent className="grid gap-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <InfoTile label="Current Plan" value={planName} />
              <InfoTile label="Lead Usage" value={`${leadsUsed} / ${leadLimit}`} />
              <InfoTile label="Renewal Date" value={renewalDate ? dateLabel(renewalDate) : "Not scheduled"} />
            </div>
            <div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Lead quota</span>
                <span>{leadsUsed} / {leadLimit} monthly leads</span>
              </div>
              <Progress className="mt-2 h-2" value={leadLimit ? Math.min((leadsUsed / leadLimit) * 100, 100) : 0} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/pricing">
                  <Sparkles data-icon="inline-start" />
                  Upgrade Plan
                </Link>
              </Button>
              <Button variant="outline" onClick={openBillingPortal} disabled={!billing?.customer || openingPortal}>
                <CreditCard data-icon="inline-start" />
                Manage Subscription
              </Button>
              <Button asChild variant="outline">
                <Link href="/billing">
                  <FileText data-icon="inline-start" />
                  Invoices
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <SettingsSection icon={Globe2} title="Workspace">
          <FieldGroup>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="workspace-name">Workspace Name</FieldLabel>
                <Input
                  id="workspace-name"
                  value={workspaceForm.workspace_name}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, workspace_name: event.target.value }))}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="business-type">Business Type</FieldLabel>
                <Input
                  id="business-type"
                  value={workspaceForm.business_type}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, business_type: event.target.value }))}
                  placeholder="Agency, SaaS, services"
                />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="workspace-country">Country</FieldLabel>
                <Input
                  id="workspace-country"
                  value={workspaceForm.country}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, country: event.target.value }))}
                  placeholder="United States"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="default-industry">Default Industry</FieldLabel>
                <Input
                  id="default-industry"
                  value={workspaceForm.default_industry}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, default_industry: event.target.value }))}
                  placeholder="Restaurants, dentists, real estate"
                />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="default-location">Default Lead Location</FieldLabel>
                <Input
                  id="default-location"
                  value={workspaceForm.default_location}
                  onChange={(event) => setWorkspaceForm((prev) => ({ ...prev, default_location: event.target.value }))}
                  placeholder="New York"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="default-limit">Default Lead Volume</FieldLabel>
                <Input
                  id="default-limit"
                  type="number"
                  min={1}
                  max={500}
                  value={settingsForm.default_lead_limit}
                  onChange={(event) => setSettingsForm((prev) => ({ ...prev, default_lead_limit: Number(event.target.value) }))}
                />
              </Field>
            </div>
          </FieldGroup>
        </SettingsSection>

        <SettingsSection icon={ShieldCheck} title="Security">
          <div className="grid gap-3">
            <ActionRow icon={LockKeyhole} title="Change Password" detail="Update your account password." action="Open" disabled />
            <ActionRow icon={KeyRound} title="Two-factor Authentication" detail="Add an extra layer of account protection." action="Coming soon" disabled />
            <ActionRow icon={Monitor} title="Active Sessions" detail="Review signed-in devices for this account." action="View" disabled />
            <div className="flex items-center justify-between gap-4 rounded-lg border border-border/70 bg-secondary/25 p-4">
              <div className="flex min-w-0 items-start gap-3">
                <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Unplug className="size-4" />
                </div>
                <div>
                  <p className="text-sm font-medium">Log Out Other Devices</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">End other sessions after a password change.</p>
                </div>
              </div>
              <Button variant="outline" disabled>Log out</Button>
            </div>
          </div>
        </SettingsSection>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_0.78fr]">
        <SettingsSection icon={Bell} title="Notifications">
          <div className="grid gap-3 sm:grid-cols-2">
            <ToggleRow label="Email Notifications" checked={notifications.email} onChange={(value) => setNotifications((prev) => ({ ...prev, email: value }))} />
            <ToggleRow label="Marketing Emails" checked={notifications.marketing} onChange={(value) => setNotifications((prev) => ({ ...prev, marketing: value }))} />
            <ToggleRow label="Campaign Notifications" checked={notifications.campaigns} onChange={(value) => setNotifications((prev) => ({ ...prev, campaigns: value }))} />
            <ToggleRow label="Billing Emails" checked={notifications.billing} onChange={(value) => setNotifications((prev) => ({ ...prev, billing: value }))} />
            <ToggleRow label="Security Alerts" checked={notifications.security} onChange={(value) => setNotifications((prev) => ({ ...prev, security: value }))} />
          </div>
        </SettingsSection>

        <SettingsSection icon={SlidersHorizontal} title="Preferences">
          <FieldGroup>
            <Field orientation="horizontal">
              <Switch
                id="dark-mode"
                checked={preferences.dark_mode}
                onCheckedChange={(checked) => setPreferences((prev) => ({ ...prev, dark_mode: checked }))}
              />
              <div>
                <FieldLabel htmlFor="dark-mode">Dark Mode</FieldLabel>
                <FieldDescription>The current workspace theme is optimized for dark mode.</FieldDescription>
              </div>
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel>Default View</FieldLabel>
                <Select value={preferences.default_view} onValueChange={(value) => setPreferences((prev) => ({ ...prev, default_view: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="dashboard">Dashboard</SelectItem>
                      <SelectItem value="leads">Leads</SelectItem>
                      <SelectItem value="crm">CRM</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>Items Per Page</FieldLabel>
                <Select value={preferences.items_per_page} onValueChange={(value) => setPreferences((prev) => ({ ...prev, items_per_page: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {["25", "50", "100"].map((value) => (
                        <SelectItem key={value} value={value}>
                          {value}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            <Field>
              <FieldLabel>Lead Table Density</FieldLabel>
              <Select value={preferences.table_density} onValueChange={(value) => setPreferences((prev) => ({ ...prev, table_density: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="comfortable">Comfortable</SelectItem>
                    <SelectItem value="compact">Compact</SelectItem>
                    <SelectItem value="spacious">Spacious</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field orientation="horizontal">
              <Switch
                id="export-screenshots"
                checked={settingsForm.include_screenshots}
                onCheckedChange={(checked) => setSettingsForm((prev) => ({ ...prev, include_screenshots: checked }))}
              />
              <div>
                <FieldLabel htmlFor="export-screenshots">Include Screenshots In Exports</FieldLabel>
                <FieldDescription>Add website screenshot links to CSV exports.</FieldDescription>
              </div>
            </Field>
          </FieldGroup>
        </SettingsSection>
      </section>

      <SettingsSection icon={Zap} title="Integrations">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {integrationCards.map((item) => (
            <IntegrationCard key={item.title} item={item} />
          ))}
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <div className="rounded-lg border border-border/70 bg-secondary/20 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="flex items-center gap-2 font-semibold">
                  <Mail className="size-4 text-primary" />
                  Gmail
                </h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Use your connected Gmail account for outreach sending and reply sync.
                </p>
              </div>
              {canOutreach ? (
                <Badge variant={gmailStatus?.is_connected ? "default" : "secondary"}>
                  {gmailStatus?.is_connected ? "Connected" : "Not connected"}
                </Badge>
              ) : (
                <PlanBadge feature="outreach" />
              )}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <InfoTile label="Mailbox" value={gmailStatus?.gmail_email || "Not connected"} />
              <InfoTile label="Connected Since" value={dateTimeLabel(gmailStatus?.connected_at)} />
              <InfoTile label="Health" value={gmailHealthLabel(gmailStatus)} />
            </div>
            {gmailStatus?.last_error ? <ErrorMessage message={gmailStatus.last_error} /> : null}
            {!canOutreach ? (
              <LockedInline feature="outreach" message="Gmail outreach is included with the Basic plan and higher." />
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button onClick={onConnectGmail}>
                {!canOutreach ? <LockKeyhole data-icon="inline-start" /> : <Mail data-icon="inline-start" />}
                {gmailStatus?.is_connected ? "Reconnect Gmail" : "Connect Gmail"}
              </Button>
              <Button variant="outline" onClick={onCheckGmail} disabled={!gmailStatus?.is_connected || checkingGmail}>
                <RefreshCw data-icon="inline-start" className={checkingGmail ? "animate-spin" : ""} />
                Check Health
              </Button>
              <Button variant="outline" onClick={onDisconnectGmail} disabled={!gmailStatus?.is_connected || disconnectingGmail}>
                <Unplug data-icon="inline-start" />
                Disconnect
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-border/70 bg-secondary/20 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="flex items-center gap-2 font-semibold">
                  <PhoneCall className="size-4 text-primary" />
                  Calling
                </h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Connect a phone account for AI SDR calling workflows.
                </p>
              </div>
              {canTwilio ? (
                <Badge variant={twilioStatus?.is_connected ? "default" : "secondary"}>
                  {twilioStatus?.is_connected ? "Connected" : "Not connected"}
                </Badge>
              ) : (
                <PlanBadge feature="twilio" />
              )}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <InfoTile label="Phone Number" value={twilioStatus?.phone_number || "Not connected"} />
              <InfoTile label="Connected Since" value={dateTimeLabel(twilioStatus?.connected_at)} />
              <InfoTile label="Health" value={twilioHealthLabel(twilioStatus)} />
            </div>
            {twilioStatus?.last_error ? <ErrorMessage message={twilioStatus.last_error} /> : null}
            {!canTwilio ? (
              <LockedInline feature="twilio" message="Automated calling and voice settings are included with the Agency plan." />
            ) : null}
            <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <Field>
                <FieldLabel htmlFor="calling-account">Account SID</FieldLabel>
                <Input
                  id="calling-account"
                  value={twilioForm.account_sid}
                  onChange={(event) => setTwilioForm((prev) => ({ ...prev, account_sid: event.target.value }))}
                  disabled={!canTwilio}
                  placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="calling-token">Auth Token</FieldLabel>
                <Input
                  id="calling-token"
                  type="password"
                  value={twilioForm.auth_token}
                  onChange={(event) => setTwilioForm((prev) => ({ ...prev, auth_token: event.target.value }))}
                  disabled={!canTwilio}
                  placeholder="Token"
                />
              </Field>
              <div className="flex items-end">
                <Button onClick={onConnectTwilio} disabled={connectingTwilio}>
                  {!canTwilio ? <LockKeyhole data-icon="inline-start" /> : <PhoneCall data-icon="inline-start" />}
                  {connectingTwilio ? "Connecting" : twilioStatus?.is_connected ? "Reconnect" : "Connect"}
                </Button>
              </div>
            </div>
            {canTwilio && twilioStatus?.requires_phone_selection && twilioStatus.phone_numbers.length ? (
              <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                <Field>
                  <FieldLabel>Phone Number</FieldLabel>
                  <Select
                    value={twilioForm.phone_sid}
                    onValueChange={(value) => setTwilioForm((prev) => ({ ...prev, phone_sid: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a phone number" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {twilioStatus.phone_numbers.map((number) => (
                          <SelectItem key={number.phone_sid} value={number.phone_sid}>
                            {number.phone_number} {number.friendly_name ? `- ${number.friendly_name}` : ""}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <div className="flex items-end">
                  <Button onClick={onConnectTwilio} disabled={connectingTwilio || !twilioForm.phone_sid}>
                    <Save data-icon="inline-start" />
                    Save Number
                  </Button>
                </div>
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="outline" onClick={onCheckTwilio} disabled={!twilioStatus?.is_connected || checkingTwilio}>
                <RefreshCw data-icon="inline-start" className={checkingTwilio ? "animate-spin" : ""} />
                Test Connection
              </Button>
              <Button variant="outline" onClick={onDisconnectTwilio} disabled={!twilioStatus?.is_connected || disconnectingTwilio}>
                <Unplug data-icon="inline-start" />
                Disconnect
              </Button>
            </div>
          </div>
        </div>
      </SettingsSection>

      <section className="grid gap-5 xl:grid-cols-[1fr_0.82fr]">
        <SettingsSection icon={Bot} title="AI Voice">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Field>
              <FieldLabel htmlFor="voice-id">Voice Selection</FieldLabel>
              <Input
                id="voice-id"
                value={voiceForm.voice_id}
                onChange={(event) => setVoiceForm((prev) => ({ ...prev, voice_id: event.target.value }))}
                disabled={!canTwilio}
                placeholder="Voice ID"
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="voice-name">Voice Name</FieldLabel>
              <Input
                id="voice-name"
                value={voiceForm.voice_name}
                onChange={(event) => setVoiceForm((prev) => ({ ...prev, voice_name: event.target.value }))}
                disabled={!canTwilio}
                placeholder="Voice profile label"
              />
            </Field>
            <Field>
              <FieldLabel>Speaking Speed</FieldLabel>
              <Select
                value={voiceForm.speaking_speed}
                onValueChange={(value) => setVoiceForm((prev) => ({ ...prev, speaking_speed: value as VoiceSpeed }))}
                disabled={!canTwilio}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {["slowest", "slower", "normal", "faster", "fastest"].map((speed) => (
                      <SelectItem key={speed} value={speed}>
                        {titleCase(speed)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="voice-language">Language</FieldLabel>
              <Input
                id="voice-language"
                value={voiceForm.language}
                onChange={(event) => setVoiceForm((prev) => ({ ...prev, language: event.target.value }))}
                disabled={!canTwilio}
                placeholder="en"
              />
            </Field>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="assistant-name">AI Assistant Name</FieldLabel>
              <Input
                id="assistant-name"
                value={voiceForm.assistant_name}
                onChange={(event) => setVoiceForm((prev) => ({ ...prev, assistant_name: event.target.value }))}
                disabled={!canTwilio}
                placeholder="Ava"
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="voice-business">Business Name</FieldLabel>
              <Input
                id="voice-business"
                value={voiceForm.business_name}
                onChange={(event) => setVoiceForm((prev) => ({ ...prev, business_name: event.target.value }))}
                disabled={!canTwilio}
                placeholder="LeadForge"
              />
            </Field>
          </div>
          <Field className="mt-4">
            <FieldLabel htmlFor="ai-greeting">AI Greeting</FieldLabel>
            <Textarea
              id="ai-greeting"
              value={voiceForm.ai_greeting}
              onChange={(event) => setVoiceForm((prev) => ({ ...prev, ai_greeting: event.target.value }))}
              disabled={!canTwilio}
              placeholder="Hi, this is {assistant_name}. Am I speaking with someone from {business_name}?"
              className="min-h-24"
            />
          </Field>
          <div className="mt-4 flex justify-end">
            <Button onClick={onSaveVoiceSettings} disabled={savingVoice}>
              {!canTwilio ? <LockKeyhole data-icon="inline-start" /> : <Save data-icon="inline-start" />}
              {savingVoice ? "Saving" : "Save voice profile"}
            </Button>
          </div>
        </SettingsSection>

        <SettingsSection icon={Download} title="Data & Privacy">
          <div className="grid gap-3">
            <Button
              variant="outline"
              className="justify-between"
              onClick={() => {
                if (!canExport) {
                  subscription.openUpgrade("csv_export");
                  return;
                }
                window.location.href = csvExportUrl({ scope: "all" });
              }}
            >
              <span className="inline-flex items-center gap-2">
                {!canExport ? <LockKeyhole className="size-4" /> : <Download className="size-4" />}
                Export Data
                {!canExport ? <PlanBadge feature="csv_export" /> : null}
              </span>
              <ChevronRight className="size-4" />
            </Button>
            <Button asChild variant="outline" className="justify-between">
              <Link href="/privacy">
                <span className="inline-flex items-center gap-2">
                  <ShieldCheck className="size-4" />
                  Privacy Policy
                </span>
                <ChevronRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-between">
              <Link href="/terms">
                <span className="inline-flex items-center gap-2">
                  <FileText className="size-4" />
                  Terms
                </span>
                <ChevronRight className="size-4" />
              </Link>
            </Button>
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
              <p className="flex items-center gap-2 text-sm font-medium text-destructive">
                <Trash2 className="size-4" />
                Danger Zone
              </p>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Workspace and account deletion are permanent actions. Contact support to verify ownership before deletion.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" disabled>Delete Workspace</Button>
                <Button variant="outline" disabled>Delete Account</Button>
              </div>
            </div>
          </div>
        </SettingsSection>
      </section>

      <SettingsSection icon={LifeBuoy} title="Support">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SupportLink icon={HelpCircle} title="Help Center" href="/contact" />
          <SupportLink icon={BookOpen} title="Documentation" href="/features" />
          <SupportLink icon={MessageSquarePlus} title="Report Bug" href="mailto:support@leadforage.pro" />
          <SupportLink icon={Languages} title="Feature Request" href="mailto:support@leadforage.pro" />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/70 bg-secondary/20 p-4">
          <div>
            <p className="text-sm font-medium">Need help with your workspace?</p>
            <p className="mt-1 text-xs text-muted-foreground">Contact support@leadforage.pro for billing, account, or product support.</p>
          </div>
          <Button asChild variant="outline">
            <a href="mailto:support@leadforage.pro">Contact Support</a>
          </Button>
        </div>
      </SettingsSection>
    </div>
  );
}

function SettingsSection({ children, icon: Icon, title }: { children: React.ReactNode; icon: LucideIcon; title: string }) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-5 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/25 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-medium">{value}</p>
    </div>
  );
}

function ToggleRow({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border/70 bg-secondary/25 p-4">
      <span className="text-sm font-medium">{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  );
}

function IntegrationCard({
  item,
}: {
  item: { active: boolean; detail: string; feature?: FeatureKey; icon: LucideIcon; locked?: boolean; status: string; title: string };
}) {
  const Icon = item.icon;
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-background/70 text-primary">
          <Icon className="size-4" />
        </div>
        {item.locked && item.feature ? <PlanBadge feature={item.feature} /> : <Badge variant={item.active ? "default" : "secondary"}>{item.status}</Badge>}
      </div>
      <p className="mt-3 text-sm font-medium">{item.title}</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.detail}</p>
    </div>
  );
}

function LockedInline({ feature, message }: { feature: FeatureKey; message: string }) {
  return (
    <div className="mt-4 flex items-start gap-3 rounded-lg border border-primary/25 bg-primary/10 p-3 text-sm">
      <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
      <div>
        <p className="font-medium">Upgrade required</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{message}</p>
      </div>
      <div className="ml-auto">
        <PlanBadge feature={feature} />
      </div>
    </div>
  );
}

function ActionRow({
  action,
  detail,
  disabled,
  icon: Icon,
  title,
}: {
  action: string;
  detail: string;
  disabled?: boolean;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border/70 bg-secondary/25 p-4">
      <div className="flex min-w-0 items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" />
        </div>
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p>
        </div>
      </div>
      <Button variant="outline" disabled={disabled}>
        {action}
      </Button>
    </div>
  );
}

function SupportLink({ href, icon: Icon, title }: { href: string; icon: LucideIcon; title: string }) {
  const external = href.startsWith("mailto:");
  const className = "flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-secondary/20 p-4 text-sm font-medium transition-colors hover:border-primary/35 hover:bg-primary/10";
  const content = (
    <>
      <span className="inline-flex items-center gap-2">
        <Icon className="size-4 text-primary" />
        {title}
      </span>
      <ChevronRight className="size-4 text-muted-foreground" />
    </>
  );
  if (external) {
    return (
      <a href={href} className={className}>
        {content}
      </a>
    );
  }
  return (
    <Link href={href} className={className}>
      {content}
    </Link>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{message}</p>;
}

function dateTimeLabel(value: string | null | undefined) {
  if (!value) return "Not connected";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function gmailHealthLabel(status: GmailConnectionStatus | null) {
  if (!status?.is_connected) return "Disconnected";
  if (status.last_error || status.health === "error") return "Needs reconnect";
  if (status.health === "ok") return "Healthy";
  return "Connected";
}

function twilioHealthLabel(status: TwilioConnectionStatus | null) {
  if (!status?.is_connected) {
    return status?.requires_phone_selection ? "Choose number" : "Disconnected";
  }
  if (status.last_error || status.health === "error") return "Needs reconnect";
  if (status.health === "ok") return "Healthy";
  return "Connected";
}

function titleCase(value: string) {
  if (!value) return "Free";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function initials(value: string | undefined) {
  if (!value) return "LF";
  const parts = value.replace("@", " ").split(/\s+/).filter(Boolean);
  return `${parts[0]?.[0] || "L"}${parts[1]?.[0] || parts[0]?.[1] || "F"}`.toUpperCase();
}
