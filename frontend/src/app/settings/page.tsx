"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  KeyRound,
  Mail,
  Mic2,
  PhoneCall,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Unplug,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  checkGmailConnection,
  checkTwilioConnection,
  connectTwilio,
  disconnectTwilio,
  disconnectGmail,
  getGmailConnection,
  getGoogleSheetsHealth,
  getSettings,
  getTwilioConnection,
  getVoiceSettings,
  gmailConnectUrl,
  saveSettings,
  saveVoiceSettings,
} from "@/lib/api";
import type { GmailConnectionStatus, GoogleSheetsHealth, TwilioConnectionStatus, VoiceSettingsStatus, VoiceSpeed } from "@/lib/types";

export default function SettingsPage() {
  const [form, setForm] = useState({
    gemini_api_key: "",
    apify_api_key: "",
    google_sheets_id: "",
    default_lead_limit: 50,
    include_screenshots: true,
  });
  const [googleHealth, setGoogleHealth] = useState<GoogleSheetsHealth | null>(null);
  const [gmailStatus, setGmailStatus] = useState<GmailConnectionStatus | null>(null);
  const [twilioStatus, setTwilioStatus] = useState<TwilioConnectionStatus | null>(null);
  const [twilioForm, setTwilioForm] = useState({
    account_sid: "",
    auth_token: "",
    phone_sid: "",
  });
  const [voiceForm, setVoiceForm] = useState({
    voice_provider: "cartesia" as const,
    voice_id: "",
    voice_name: "",
    speaking_speed: "normal" as VoiceSpeed,
    language: "en",
    ai_greeting: "",
    business_name: "",
    assistant_name: "",
    cartesia_api_key: "",
  });
  const [voiceHasCartesiaKey, setVoiceHasCartesiaKey] = useState(false);
  const [testingGoogle, setTestingGoogle] = useState(false);
  const [checkingGmail, setCheckingGmail] = useState(false);
  const [disconnectingGmail, setDisconnectingGmail] = useState(false);
  const [connectingTwilio, setConnectingTwilio] = useState(false);
  const [checkingTwilio, setCheckingTwilio] = useState(false);
  const [disconnectingTwilio, setDisconnectingTwilio] = useState(false);
  const [savingVoice, setSavingVoice] = useState(false);

  useEffect(() => {
    Promise.all([getSettings(), getGmailConnection(), getTwilioConnection(), getVoiceSettings()])
      .then(([settings, gmail, twilio, voice]) => {
        setForm((prev) => ({
          ...prev,
          google_sheets_id: String((settings.google_sheets_id as { value?: string } | undefined)?.value ?? ""),
          default_lead_limit: Number(settings.default_lead_limit ?? prev.default_lead_limit),
        }));
        setGmailStatus(gmail);
        setTwilioStatus(twilio);
        applyVoiceSettings(voice);
      })
      .catch((error) => toast.error(error.message));
    testGoogleConnection({ quiet: true });

    const gmailResult = new URLSearchParams(window.location.search).get("gmail");
    if (gmailResult === "connected") {
      toast.success("Gmail connected");
      window.history.replaceState(null, "", window.location.pathname);
    } else if (gmailResult === "cancelled") {
      toast.info("Gmail connection cancelled");
      window.history.replaceState(null, "", window.location.pathname);
    } else if (gmailResult === "error") {
      toast.error("Gmail connection failed. Check the Railway Gmail OAuth settings.");
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  async function testGoogleConnection(options: { quiet?: boolean } = {}) {
    setTestingGoogle(true);
    try {
      const health = await getGoogleSheetsHealth();
      setGoogleHealth(health);
      if (!options.quiet) {
        if (health.status === "ok") {
          toast.success("Google Sheets connected");
        } else {
          toast.error(health.message || "Google Sheets connection failed");
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Google Sheets connection failed";
      setGoogleHealth({
        status: "error",
        google_sheets: false,
        spreadsheet_access: false,
        code: "request_failed",
        message,
        credentials_source: "",
        spreadsheet_id_configured: false,
        service_account_email: "",
      });
      if (!options.quiet) {
        toast.error(message);
      }
    } finally {
      setTestingGoogle(false);
    }
  }

  async function onSave() {
    try {
      await saveSettings({
        gemini_api_key: form.gemini_api_key || undefined,
        apify_api_key: form.apify_api_key || undefined,
        google_sheets_id: form.google_sheets_id || undefined,
        default_lead_limit: form.default_lead_limit,
        export_settings: {
          include_screenshots: form.include_screenshots,
        },
      });
      toast.success("Settings saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Settings save failed");
    }
  }

  async function refreshGmailStatus() {
    try {
      setGmailStatus(await getGmailConnection());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Gmail status failed");
    }
  }

  async function onCheckGmail() {
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

  function applyVoiceSettings(settings: VoiceSettingsStatus) {
    setVoiceHasCartesiaKey(settings.has_cartesia_api_key);
    setVoiceForm((previous) => ({
      ...previous,
      voice_provider: "cartesia",
      voice_id: settings.voice_id || "",
      voice_name: settings.voice_name || "",
      speaking_speed: settings.speaking_speed || "normal",
      language: settings.language || "en",
      ai_greeting: settings.ai_greeting || "",
      business_name: settings.business_name || "",
      assistant_name: settings.assistant_name || "",
      cartesia_api_key: "",
    }));
  }

  async function refreshTwilioStatus() {
    try {
      setTwilioStatus(await getTwilioConnection());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Twilio status failed");
    }
  }

  async function onConnectTwilio() {
    if (!twilioForm.account_sid.trim() || !twilioForm.auth_token.trim()) {
      toast.error("Enter Twilio Account SID and Auth Token");
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
        toast.info("Choose the Twilio phone number for AI SDR calls");
      } else {
        toast.success("Twilio connected");
        setTwilioForm({ account_sid: "", auth_token: "", phone_sid: "" });
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Twilio connection failed");
    } finally {
      setConnectingTwilio(false);
    }
  }

  async function onCheckTwilio() {
    setCheckingTwilio(true);
    try {
      const status = await checkTwilioConnection();
      setTwilioStatus(status);
      toast.success("Twilio connection healthy");
    } catch (error) {
      await refreshTwilioStatus();
      toast.error(error instanceof Error ? error.message : "Twilio health check failed");
    } finally {
      setCheckingTwilio(false);
    }
  }

  async function onDisconnectTwilio() {
    setDisconnectingTwilio(true);
    try {
      setTwilioStatus(await disconnectTwilio());
      setTwilioForm({ account_sid: "", auth_token: "", phone_sid: "" });
      toast.success("Twilio disconnected");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Twilio disconnect failed");
    } finally {
      setDisconnectingTwilio(false);
    }
  }

  async function onSaveVoiceSettings() {
    setSavingVoice(true);
    try {
      const status = await saveVoiceSettings(voiceForm);
      applyVoiceSettings(status);
      toast.success("Voice settings saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Voice settings save failed");
    } finally {
      setSavingVoice(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5 text-primary" />
            API Keys and Integrations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="ai">
            <TabsList>
              <TabsTrigger value="ai">AI + Apify</TabsTrigger>
              <TabsTrigger value="google">Google</TabsTrigger>
              <TabsTrigger value="voice">Voice</TabsTrigger>
              <TabsTrigger value="defaults">Defaults</TabsTrigger>
            </TabsList>
            <TabsContent value="ai" className="mt-6">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="gemini">Gemini API Key</FieldLabel>
                  <Input id="gemini" type="password" value={form.gemini_api_key} onChange={(event) => setForm((prev) => ({ ...prev, gemini_api_key: event.target.value }))} />
                  <FieldDescription>Used for website analysis, opportunity scoring, and outreach generation.</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="apify">Apify API Key</FieldLabel>
                  <Input id="apify" type="password" value={form.apify_api_key} onChange={(event) => setForm((prev) => ({ ...prev, apify_api_key: event.target.value }))} />
                  <FieldDescription>Used for Google Maps discovery and JavaScript website fallback crawling.</FieldDescription>
                </Field>
              </FieldGroup>
            </TabsContent>
            <TabsContent value="google" className="mt-6">
              <FieldGroup className="mb-6">
                <Field>
                  <FieldLabel htmlFor="sheets">Google Sheets ID</FieldLabel>
                  <Input id="sheets" value={form.google_sheets_id} onChange={(event) => setForm((prev) => ({ ...prev, google_sheets_id: event.target.value }))} />
                </Field>
              </FieldGroup>
              <div className="rounded-lg border border-border/70 bg-secondary/25 p-4">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Mail className="size-5 text-primary" />
                      <h3 className="font-semibold">Email Integration</h3>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {gmailStatus?.is_connected
                        ? "Outbound emails are sent from the connected Gmail account."
                        : "Connect Gmail before sending outreach emails."}
                    </p>
                  </div>
                  <Badge variant={gmailStatus?.is_connected ? "default" : "secondary"}>
                    {gmailStatus?.is_connected ? "Connected" : "Not Connected"}
                  </Badge>
                </div>
                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                  <StatusLine label="Gmail Address" value={gmailStatus?.gmail_email || "Not connected"} />
                  <StatusLine label="Connected Since" value={dateTimeLabel(gmailStatus?.connected_at)} />
                  <StatusLine label="Connection Health" value={gmailHealthLabel(gmailStatus)} />
                </div>
                {gmailStatus?.last_error ? (
                  <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {gmailStatus.last_error}
                  </p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button asChild>
                    <a href={gmailConnectUrl()}>
                      <Mail data-icon="inline-start" />
                      {gmailStatus?.is_connected ? "Reconnect Gmail" : "Connect Gmail"}
                    </a>
                  </Button>
                  <Button variant="outline" onClick={onCheckGmail} disabled={!gmailStatus?.is_connected || checkingGmail}>
                    <RefreshCw data-icon="inline-start" className={checkingGmail ? "animate-spin" : ""} />
                    Check Health
                  </Button>
                  <Button variant="outline" onClick={onDisconnectGmail} disabled={!gmailStatus?.is_connected || disconnectingGmail}>
                    <Unplug data-icon="inline-start" />
                    Disconnect Gmail
                  </Button>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="voice" className="mt-6">
              <div className="grid gap-4">
                <div className="rounded-lg border border-border/70 bg-secondary/25 p-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <PhoneCall className="size-5 text-primary" />
                        <h3 className="font-semibold">Twilio Connection</h3>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {twilioStatus?.is_connected
                          ? "AI SDR calls are placed from the connected Twilio number."
                          : "Connect Twilio before starting AI SDR calls."}
                      </p>
                    </div>
                    <Badge variant={twilioStatus?.is_connected ? "default" : "secondary"}>
                      {twilioStatus?.is_connected ? "Connected" : "Not Connected"}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                    <StatusLine label="Connected Phone Number" value={twilioStatus?.phone_number || "Not connected"} />
                    <StatusLine label="Account SID" value={twilioStatus?.account_sid_masked || "Not connected"} />
                    <StatusLine label="Connected Since" value={dateTimeLabel(twilioStatus?.connected_at)} />
                    <StatusLine label="Account Status" value={twilioStatus?.account_status || "Unknown"} />
                    <StatusLine label="Connection Health" value={twilioHealthLabel(twilioStatus)} />
                    <StatusLine label="Phone Label" value={twilioStatus?.friendly_name || "None"} />
                  </div>
                  {twilioStatus?.last_error ? (
                    <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {twilioStatus.last_error}
                    </p>
                  ) : null}
                  <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
                    <Field>
                      <FieldLabel htmlFor="twilio-sid">Twilio Account SID</FieldLabel>
                      <Input
                        id="twilio-sid"
                        value={twilioForm.account_sid}
                        onChange={(event) => setTwilioForm((prev) => ({ ...prev, account_sid: event.target.value }))}
                        placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="twilio-token">Twilio Auth Token</FieldLabel>
                      <Input
                        id="twilio-token"
                        type="password"
                        value={twilioForm.auth_token}
                        onChange={(event) => setTwilioForm((prev) => ({ ...prev, auth_token: event.target.value }))}
                        placeholder="Auth token"
                      />
                    </Field>
                    <div className="flex items-end">
                      <Button onClick={onConnectTwilio} disabled={connectingTwilio}>
                        <PhoneCall data-icon="inline-start" />
                        {connectingTwilio ? "Connecting" : twilioStatus?.is_connected ? "Reconnect" : "Connect"}
                      </Button>
                    </div>
                  </div>
                  {twilioStatus?.requires_phone_selection && twilioStatus.phone_numbers.length ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                      <Field>
                        <FieldLabel>Twilio Phone Number</FieldLabel>
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

                <div className="rounded-lg border border-border/70 bg-secondary/25 p-4">
                  <div className="flex items-center gap-2">
                    <Mic2 className="size-5 text-primary" />
                    <h3 className="font-semibold">Voice Settings</h3>
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <Field>
                      <FieldLabel>Voice Provider</FieldLabel>
                      <Select value={voiceForm.voice_provider} disabled>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem value="cartesia">Cartesia</SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="voice-id">Voice Selection</FieldLabel>
                      <Input
                        id="voice-id"
                        value={voiceForm.voice_id}
                        onChange={(event) => setVoiceForm((prev) => ({ ...prev, voice_id: event.target.value }))}
                        placeholder="Cartesia voice ID"
                      />
                    </Field>
                    <Field>
                      <FieldLabel>Speaking Speed</FieldLabel>
                      <Select
                        value={voiceForm.speaking_speed}
                        onValueChange={(value) => setVoiceForm((prev) => ({ ...prev, speaking_speed: value as VoiceSpeed }))}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {["slowest", "slower", "normal", "faster", "fastest"].map((speed) => (
                              <SelectItem key={speed} value={speed}>
                                {speedLabel(speed)}
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
                        placeholder="Ava"
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="business-name">Business Name</FieldLabel>
                      <Input
                        id="business-name"
                        value={voiceForm.business_name}
                        onChange={(event) => setVoiceForm((prev) => ({ ...prev, business_name: event.target.value }))}
                        placeholder="LeadForge"
                      />
                    </Field>
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr]">
                    <Field>
                      <FieldLabel htmlFor="cartesia-key">Cartesia API Key</FieldLabel>
                      <Input
                        id="cartesia-key"
                        type="password"
                        value={voiceForm.cartesia_api_key}
                        onChange={(event) => setVoiceForm((prev) => ({ ...prev, cartesia_api_key: event.target.value }))}
                        placeholder="Leave blank to keep saved key"
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="voice-name">Voice Name</FieldLabel>
                      <Input
                        id="voice-name"
                        value={voiceForm.voice_name}
                        onChange={(event) => setVoiceForm((prev) => ({ ...prev, voice_name: event.target.value }))}
                        placeholder="Internal label"
                      />
                    </Field>
                  </div>
                  <Field className="mt-4">
                    <FieldLabel htmlFor="ai-greeting">AI Greeting</FieldLabel>
                    <Textarea
                      id="ai-greeting"
                      value={voiceForm.ai_greeting}
                      onChange={(event) => setVoiceForm((prev) => ({ ...prev, ai_greeting: event.target.value }))}
                      placeholder="Hi, this is {assistant_name} with {assistant_business_name}. Am I speaking with someone from {business_name}?"
                      className="min-h-24"
                    />
                  </Field>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm text-muted-foreground">
                      Cartesia key: {voiceForm.cartesia_api_key ? "Ready to save" : voiceHasCartesiaKey ? "Saved" : "Not saved"}
                    </div>
                    <Button onClick={onSaveVoiceSettings} disabled={savingVoice}>
                      <Save data-icon="inline-start" />
                      {savingVoice ? "Saving" : "Save Voice Settings"}
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="defaults" className="mt-6">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="default-limit">Default Lead Limits</FieldLabel>
                  <Input id="default-limit" type="number" min={1} max={500} value={form.default_lead_limit} onChange={(event) => setForm((prev) => ({ ...prev, default_lead_limit: Number(event.target.value) }))} />
                </Field>
                <Field orientation="horizontal">
                  <Switch id="screenshots" checked={form.include_screenshots} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, include_screenshots: checked }))} />
                  <div>
                    <FieldLabel htmlFor="screenshots">Export Settings</FieldLabel>
                    <FieldDescription>Include website screenshot links in exported lead records.</FieldDescription>
                  </div>
                </Field>
              </FieldGroup>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <div className="flex justify-end">
        <Button size="lg" onClick={onSave}>
          <Save data-icon="inline-start" />
          Save Settings
        </Button>
      </div>
      <Card className="glass-panel">
        <CardHeader className="items-start gap-3 sm:grid-cols-[1fr_auto]">
          <CardTitle className="flex items-center gap-2">
            {googleHealth?.status === "ok" ? (
              <CheckCircle2 className="size-5 text-primary" />
            ) : (
              <AlertCircle className="size-5 text-destructive" />
            )}
            Google Sheets Status
          </CardTitle>
          <Button variant="outline" onClick={() => testGoogleConnection()} disabled={testingGoogle}>
            <RefreshCw data-icon="inline-start" className={testingGoogle ? "animate-spin" : ""} />
            Test Google Sheets Connection
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={googleHealth?.status === "ok" ? "default" : "destructive"}>
              {googleStatusLabel(googleHealth)}
            </Badge>
            {googleHealth?.service_account_email ? (
              <span className="text-sm text-muted-foreground">{googleHealth.service_account_email}</span>
            ) : null}
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <StatusLine label="Credentials" value={googleHealth?.google_sheets ? "Ready" : "Needs setup"} />
            <StatusLine label="Spreadsheet ID" value={googleHealth?.spreadsheet_id_configured ? "Configured" : "Missing"} />
            <StatusLine label="Spreadsheet Access" value={googleHealth?.spreadsheet_access ? "Allowed" : "Not verified"} />
          </div>
          {googleHealth?.message ? (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {googleHealth.message}
            </p>
          ) : null}
          {googleHealth?.credentials_source ? (
            <p className="text-xs text-muted-foreground">Credentials source: {googleHealth.credentials_source}</p>
          ) : null}
        </CardContent>
      </Card>
      <Card className="glass-panel">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="size-5 text-accent" />
            Runtime Notes
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-6 text-muted-foreground">
          Values saved here are stored in PostgreSQL and used as runtime overrides. Environment variables still work as defaults for Railway and local Docker.
        </CardContent>
      </Card>
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

function dateTimeLabel(value: string | null | undefined) {
  if (!value) {
    return "Not connected";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function gmailHealthLabel(status: GmailConnectionStatus | null) {
  if (!status?.is_connected) {
    return "Disconnected";
  }
  if (status.last_error || status.health === "error") {
    return "Needs reconnect";
  }
  if (status.health === "ok") {
    return "Healthy";
  }
  return "Connected";
}

function twilioHealthLabel(status: TwilioConnectionStatus | null) {
  if (!status?.is_connected) {
    if (status?.requires_phone_selection) {
      return "Choose number";
    }
    return "Disconnected";
  }
  if (status.last_error || status.health === "error") {
    return "Needs reconnect";
  }
  if (status.health === "ok") {
    return "Healthy";
  }
  return "Connected";
}

function speedLabel(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function googleStatusLabel(health: GoogleSheetsHealth | null) {
  if (!health) {
    return "Checking";
  }
  if (health.status === "ok") {
    return "Connected";
  }
  if (health.code === "missing_credentials") {
    return "Missing File";
  }
  if (health.code === "invalid_json") {
    return "Invalid JSON";
  }
  if (health.code === "api_disabled") {
    return "API Disabled";
  }
  if (["no_spreadsheet_access", "spreadsheet_not_found"].includes(health.code)) {
    return "No Spreadsheet Access";
  }
  return "Not Connected";
}
