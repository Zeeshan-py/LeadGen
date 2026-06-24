"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, KeyRound, RefreshCw, Save, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getGoogleSheetsHealth, getSettings, saveSettings } from "@/lib/api";
import type { GoogleSheetsHealth } from "@/lib/types";

export default function SettingsPage() {
  const [form, setForm] = useState({
    gemini_api_key: "",
    apify_api_key: "",
    google_sheets_id: "",
    default_lead_limit: 50,
    gmail_client_id: "",
    gmail_client_secret: "",
    gmail_refresh_token: "",
    gmail_sender_email: "",
    include_screenshots: true,
  });
  const [googleHealth, setGoogleHealth] = useState<GoogleSheetsHealth | null>(null);
  const [testingGoogle, setTestingGoogle] = useState(false);

  useEffect(() => {
    getSettings()
      .then((settings) => {
        setForm((prev) => ({
          ...prev,
          google_sheets_id: String((settings.google_sheets_id as { value?: string } | undefined)?.value ?? ""),
          default_lead_limit: Number(settings.default_lead_limit ?? prev.default_lead_limit),
        }));
      })
      .catch((error) => toast.error(error.message));
    testGoogleConnection({ quiet: true });
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
        gmail_credentials: {
          client_id: form.gmail_client_id,
          client_secret: form.gmail_client_secret,
          refresh_token: form.gmail_refresh_token,
          sender_email: form.gmail_sender_email,
        },
        export_settings: {
          include_screenshots: form.include_screenshots,
        },
      });
      toast.success("Settings saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Settings save failed");
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
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="sheets">Google Sheets ID</FieldLabel>
                  <Input id="sheets" value={form.google_sheets_id} onChange={(event) => setForm((prev) => ({ ...prev, google_sheets_id: event.target.value }))} />
                </Field>
                <Field>
                  <FieldLabel htmlFor="gmail-sender">Gmail Sender Email</FieldLabel>
                  <Input id="gmail-sender" value={form.gmail_sender_email} onChange={(event) => setForm((prev) => ({ ...prev, gmail_sender_email: event.target.value }))} />
                </Field>
                <Field>
                  <FieldLabel htmlFor="gmail-client">Gmail Client ID</FieldLabel>
                  <Input id="gmail-client" value={form.gmail_client_id} onChange={(event) => setForm((prev) => ({ ...prev, gmail_client_id: event.target.value }))} />
                </Field>
                <Field>
                  <FieldLabel htmlFor="gmail-secret">Gmail Client Secret</FieldLabel>
                  <Input id="gmail-secret" type="password" value={form.gmail_client_secret} onChange={(event) => setForm((prev) => ({ ...prev, gmail_client_secret: event.target.value }))} />
                </Field>
                <Field>
                  <FieldLabel htmlFor="gmail-refresh">Gmail Refresh Token</FieldLabel>
                  <Input id="gmail-refresh" type="password" value={form.gmail_refresh_token} onChange={(event) => setForm((prev) => ({ ...prev, gmail_refresh_token: event.target.value }))} />
                </Field>
              </FieldGroup>
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
