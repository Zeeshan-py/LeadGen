"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BrainCircuit, LockKeyhole, Mail, SquareCode } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, oauthUrl } = useAuth();
  const [nextPath, setNextPath] = useState("/dashboard");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const next = params.get("next");
    if (next?.startsWith("/") && !next.startsWith("//")) {
      setNextPath(next);
    }
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await login({ email, password, remember_me: rememberMe });
      router.replace(nextPath);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
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
              <CardTitle className="text-xl">Login</CardTitle>
              <p className="text-sm text-muted-foreground">LeadForge AI</p>
            </div>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            <Button variant="outline" className="w-full justify-center" onClick={() => { window.location.href = oauthUrl("google", nextPath); }}>
              <Mail data-icon="inline-start" />
              Continue with Google
            </Button>
            <Button variant="outline" className="w-full justify-center" onClick={() => { window.location.href = oauthUrl("github", nextPath); }}>
              <SquareCode data-icon="inline-start" />
              Continue with GitHub
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
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="pl-9" autoComplete="email" required />
                </div>
              </Field>
              <Field>
                <div className="flex items-center justify-between gap-3">
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Link href="/forgot-password" className="text-xs text-primary hover:underline">
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="pl-9" autoComplete="current-password" required />
                </div>
              </Field>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox checked={rememberMe} onCheckedChange={(value) => setRememberMe(value === true)} />
                Remember me
              </label>
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                Login
                <ArrowRight data-icon="inline-end" />
              </Button>
            </FieldGroup>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            New to LeadForge?{" "}
            <Link href="/signup" className="text-primary hover:underline">
              Sign up
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
