"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BrainCircuit, LockKeyhole } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { resetPassword } = useAuth();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get("token") ?? "");
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await resetPassword(token, password);
      toast.success("Password reset");
      router.replace("/login");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Password reset failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="score-grid grid min-h-svh place-items-center px-4 py-10">
      <Card className="glass-panel w-full max-w-md">
        <CardHeader className="space-y-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
              <BrainCircuit className="size-5" />
            </div>
            <div>
              <CardTitle className="text-xl">Reset Password</CardTitle>
              <p className="text-sm text-muted-foreground">LeadForge AI</p>
            </div>
          </Link>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="token">Reset Token</FieldLabel>
                <Input id="token" value={token} onChange={(event) => setToken(event.target.value)} required />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">New Password</FieldLabel>
                <div className="relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="pl-9" autoComplete="new-password" minLength={8} required />
                </div>
              </Field>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                Reset Password
              </Button>
            </FieldGroup>
          </form>
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
