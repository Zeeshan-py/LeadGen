"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArrowLeft, Mail } from "lucide-react";
import { toast } from "sonner";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const { forgotPassword } = useAuth();
  const [email, setEmail] = useState("");
  const [resetUrl, setResetUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await forgotPassword(email);
      setResetUrl(response.reset_url ?? "");
      toast.success(response.message);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reset request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="score-grid grid min-h-svh place-items-center px-4 py-10">
      <Card className="glass-panel w-full max-w-md">
        <CardHeader className="space-y-4">
          <Link href="/" className="flex items-center gap-3">
            <BrandLogo />
            <div>
              <CardTitle className="text-xl">Forgot Password</CardTitle>
              <p className="text-sm text-muted-foreground">LeadForge AI</p>
            </div>
          </Link>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="pl-9" autoComplete="email" required />
                </div>
              </Field>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                Send Reset Link
              </Button>
            </FieldGroup>
          </form>
          {resetUrl ? (
            <div className="mt-5 rounded-lg border border-primary/25 bg-primary/10 p-3 text-sm">
              <Link href={resetUrl} className="break-all text-primary hover:underline">
                {resetUrl}
              </Link>
            </div>
          ) : null}
          <Button asChild variant="ghost" className="mt-4 w-full">
            <Link href="/login">
              <ArrowLeft data-icon="inline-start" />
              Back to Login
            </Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
