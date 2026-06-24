"use client";

import { Check, Loader2, X } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import type { GenerationJob } from "@/lib/types";
import { cn } from "@/lib/utils";

const steps = [
  "Searching Google Maps",
  "Scraping Websites",
  "Finding Emails",
  "Finding Phone Numbers",
  "Analyzing Websites",
  "Generating AI Insights",
  "Creating Personalized Outreach",
  "Saving Leads",
];

export function PipelineProgress({ job }: { job: GenerationJob | null }) {
  const currentIndex = Math.max(0, steps.indexOf(job?.stage ?? ""));
  const failed = job?.status === "failed";
  return (
    <div className="glass-panel rounded-lg p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Real-time pipeline</p>
          <h2 className="text-2xl font-semibold tracking-normal">{job?.stage ?? "Ready to generate"}</h2>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Counter label="Campaign" value={`${job?.progress ?? 0}%`} />
          <Counter label="Leads" value={job?.lead_counter ?? 0} />
          <Counter label="Success" value={job?.success_counter ?? 0} />
          <Counter label="Failure" value={job?.failure_counter ?? 0} />
        </div>
      </div>
      <Progress value={job?.progress ?? 0} className="mt-5 h-2" />
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const done = (job?.progress ?? 0) === 100 || index < currentIndex;
          const active = step === job?.stage;
          return (
            <div
              key={step}
              className={cn(
                "flex items-center gap-3 rounded-lg border border-border/70 bg-secondary/30 p-3 text-sm",
                active && "border-primary/40 bg-primary/10 text-primary",
                done && "border-primary/25",
                failed && active && "border-destructive/40 bg-destructive/10 text-destructive",
              )}
            >
              <div className="grid size-8 shrink-0 place-items-center rounded-md bg-background/70">
                {failed && active ? <X /> : active ? <Loader2 className="animate-spin" /> : done ? <Check /> : <span className="text-xs">{index + 1}</span>}
              </div>
              <span className="min-w-0 truncate">{step}</span>
            </div>
          );
        })}
      </div>
      {job?.error ? <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{job.error}</p> : null}
    </div>
  );
}

function Counter({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-secondary/30 px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}
