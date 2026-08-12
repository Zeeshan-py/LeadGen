import Link from "next/link";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";

type Section = {
  title: string;
  body: string[];
};

export function PublicInfoPage({
  title,
  eyebrow,
  description,
  sections,
}: {
  title: string;
  eyebrow: string;
  description: string;
  sections: Section[];
}) {
  return (
    <main className="score-grid min-h-svh">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-5 md:px-6">
        <Link href="/" className="flex items-center gap-3">
          <BrandLogo />
          <div>
            <p className="text-sm font-semibold">LeadForge AI</p>
            <p className="text-xs text-muted-foreground">Private workspace SaaS</p>
          </div>
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 text-sm text-muted-foreground md:flex">
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/features">
            Features
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/pricing">
            Pricing
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/about">
            About
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/privacy">
            Privacy
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/terms">
            Terms
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/refund">
            Refunds
          </Link>
          <Link className="rounded-md px-3 py-2 hover:bg-secondary hover:text-foreground" href="/contact">
            Contact
          </Link>
        </nav>
        <Button asChild variant="outline">
          <Link href="/login">Login</Link>
        </Button>
      </header>

      <section className="mx-auto w-full max-w-5xl px-4 pb-16 pt-10 md:px-6 md:pt-16">
        <p className="text-sm font-medium text-primary">{eyebrow}</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-normal md:text-5xl">{title}</h1>
        <p className="mt-5 max-w-3xl text-base leading-7 text-muted-foreground md:text-lg">{description}</p>

        <div className="mt-10 grid gap-8 border-t border-border/70 pt-8">
          {sections.map((section) => (
            <section key={section.title} className="grid gap-3">
              <h2 className="text-xl font-semibold">{section.title}</h2>
              {section.body.map((paragraph) => (
                <p key={paragraph} className="max-w-4xl text-sm leading-7 text-muted-foreground">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}
        </div>
      </section>
    </main>
  );
}
