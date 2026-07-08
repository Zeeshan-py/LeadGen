"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Play, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { PipelineProgress } from "@/components/pipeline-progress";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { generationEventsUrl, getGenerationJob, getLatestGenerationJob, startGeneration } from "@/lib/api";
import {
  businessTypes,
  continents,
  countriesByContinent,
  type Continent,
} from "@/lib/markets";
import type { GenerationJob } from "@/lib/types";

const leadLimits = [10, 25, 50, 100, 250, 500];
const lastGenerationJobKey = "leadforge.lastGenerationJobId";
const terminalStatuses = new Set(["completed", "failed"]);

function isTerminalJob(job: GenerationJob) {
  return terminalStatuses.has(job.status);
}

export default function LeadGeneratorPage() {
  const [form, setForm] = useState({
    continent: "North America" as Continent,
    country: "United States",
    city: "",
    business_type: "Dentists",
    website_mode: "withWebsite",
    max_leads: 25,
  });
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [running, setRunning] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const countries = countriesByContinent[form.continent];

  const canRun = useMemo(
    () => form.country.trim() && form.business_type.trim() && form.max_leads > 0,
    [form],
  );

  const closeStream = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const connectToJob = useCallback(
    (jobId: string) => {
      closeStream();
      const source = new EventSource(generationEventsUrl(jobId));
      sourceRef.current = source;
      setRunning(true);

      source.onmessage = (event) => {
        const next = JSON.parse(event.data) as GenerationJob;
        setJob(next);
        if (isTerminalJob(next)) {
          closeStream();
          setRunning(false);
          if (next.status === "completed") {
            toast.success("Lead generation completed");
          } else {
            toast.error("Lead generation failed");
          }
        }
      };

      source.onerror = () => {
        if (sourceRef.current !== source) {
          return;
        }
        closeStream();
        setRunning(false);
        toast.error("Pipeline stream disconnected");
      };
    },
    [closeStream],
  );

  useEffect(() => {
    let ignore = false;

    async function restoreLatestJob() {
      try {
        const storedJobId = window.localStorage.getItem(lastGenerationJobKey);
        let restoredJob: GenerationJob | null = null;
        if (storedJobId) {
          restoredJob = await getGenerationJob(storedJobId).catch(() => null);
        }
        restoredJob = restoredJob ?? (await getLatestGenerationJob());
        if (ignore || !restoredJob) {
          return;
        }
        setJob(restoredJob);
        setRunning(!isTerminalJob(restoredJob));
        if (!isTerminalJob(restoredJob)) {
          connectToJob(restoredJob.job_id);
        }
      } catch (error) {
        if (!ignore) {
          toast.error(error instanceof Error ? error.message : "Could not restore generation progress");
        }
      }
    }

    restoreLatestJob();
    return () => {
      ignore = true;
      closeStream();
    };
  }, [closeStream, connectToJob]);

  async function onGenerate() {
    if (!canRun || running) {
      return;
    }
    setRunning(true);
    try {
      const created = await startGeneration(form);
      window.localStorage.setItem(lastGenerationJobKey, created.job_id);
      toast.success("Lead generation started");
      connectToJob(created.job_id);
    } catch (error) {
      setRunning(false);
      toast.error(error instanceof Error ? error.message : "Generation failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[440px_1fr]">
      <Card className="glass-panel h-fit">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <Sparkles className="size-5 text-primary" />
            Generate Leads
          </CardTitle>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="continent">Continent</FieldLabel>
              <Select
                value={form.continent}
                onValueChange={(value) => {
                  const continent = value as Continent;
                  setForm((prev) => ({
                    ...prev,
                    continent,
                    country: countriesByContinent[continent][0],
                    city: "",
                  }));
                }}
              >
                <SelectTrigger id="continent">
                  <SelectValue placeholder="Select continent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {continents.map((continent) => (
                      <SelectItem key={continent} value={continent}>{continent}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="country">Country</FieldLabel>
              <Select
                value={form.country}
                onValueChange={(country) => setForm((prev) => ({ ...prev, country, city: "" }))}
              >
                <SelectTrigger id="country">
                  <SelectValue placeholder="Select country" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {countries.map((country) => (
                      <SelectItem key={country} value={country}>{country}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="city">City</FieldLabel>
              <Input
                id="city"
                value={form.city}
                onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))}
                placeholder="Optional, e.g. Dallas"
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="business_type">Business Type</FieldLabel>
              <Select value={form.business_type} onValueChange={(business_type) => setForm((prev) => ({ ...prev, business_type }))}>
                <SelectTrigger id="business_type">
                  <SelectValue placeholder="Select business type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {businessTypes.map((businessType) => (
                      <SelectItem key={businessType} value={businessType}>{businessType}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>Website Filter</FieldLabel>
              <Select value={form.website_mode} onValueChange={(value) => setForm((prev) => ({ ...prev, website_mode: value }))}>
                <SelectTrigger aria-label="Website Filter">
                  <SelectValue placeholder="Website filter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="withWebsite">With website</SelectItem>
                    <SelectItem value="withoutWebsite">Without Website</SelectItem>
                    <SelectItem value="allPlaces">All</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="max_leads">Number of Leads</FieldLabel>
              <Select value={String(form.max_leads)} onValueChange={(max_leads) => setForm((prev) => ({ ...prev, max_leads: Number(max_leads) }))}>
                <SelectTrigger id="max_leads">
                  <SelectValue placeholder="Select lead limit" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {leadLimits.map((limit) => (
                      <SelectItem key={limit} value={String(limit)}>{limit} leads</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Button size="lg" className="w-full" disabled={!canRun || running} onClick={onGenerate}>
              <Play data-icon="inline-start" />
              Generate Leads
            </Button>
          </FieldGroup>
        </CardContent>
      </Card>
      <PipelineProgress job={job} />
    </div>
  );
}
