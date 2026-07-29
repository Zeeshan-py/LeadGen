"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BrainCircuit, LockKeyhole, Mail, UserRound } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { trackEvent, trackSignUp, trackWorkspaceCreation } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const { signup, oauthUrl } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await signup({ full_name: fullName, email, password, remember_me: rememberMe });
      trackSignUp("email");
      trackWorkspaceCreation("signup");
      router.replace("/dashboard");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sign up failed");
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
              <CardTitle className="text-xl">Sign Up</CardTitle>
              <p className="text-sm text-muted-foreground">LeadForge AI</p>
            </div>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            <Button variant="outline" className="w-full justify-center" onClick={() => { trackEvent("sign_up_start", { method: "google" }); window.location.href = oauthUrl("google"); }}>
              <Mail data-icon="inline-start" />
              Continue with Google
            </Button>
          </div>

          <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
            <div className="h-px flex-1 bg-border" />
            <span>Email</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={onSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="full_name">Full Name</FieldLabel>
                <div className="relative">
                  <UserRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="full_name" value={fullName} onChange={(event) => setFullName(event.target.value)} className="pl-9" autoComplete="name" required />
                </div>
              </Field>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="pl-9" autoComplete="email" required />
                </div>
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <div className="relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="pl-9" autoComplete="new-password" minLength={8} required />
                </div>
              </Field>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox checked={rememberMe} onCheckedChange={(value) => setRememberMe(value === true)} />
                Remember me
              </label>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                Sign Up
                <ArrowRight data-icon="inline-end" />
              </Button>
            </FieldGroup>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link href="/login" className="text-primary hover:underline">
              Login
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
