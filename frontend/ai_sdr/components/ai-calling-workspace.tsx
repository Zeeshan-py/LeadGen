"use client";

/**
 * Full-screen AI Calling Workspace.
 *
 * Starts a backend AI SDR call when providers are configured, polls live
 * transcript/brain state, and falls back to deterministic mock events in local
 * environments without telephony credentials.
 */

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  FileText,
  Mic,
  MicOff,
  Pause,
  Phone,
  PhoneOff,
  Play,
  Radio,
  type LucideIcon,
  UserRound,
  UserRoundCheck,
} from "lucide-react";
import { toast } from "sonner";

import { controlAISDRCall, getAISDRCall, getAISDRContact, startAISDROutboundCall } from "../api";
import type { AISDRCallSession, AISDRContact } from "../types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type Speaker = "ai" | "customer" | "system";

type BrainState = {
  currentGoal: string;
  stage: string;
  objection: string;
  sentiment: string;
  qualificationScore: number;
  nextAction: string;
};

type TranscriptLine = {
  id: string;
  speaker: Speaker;
  text: string;
  at: Date;
};

type MockEvent = {
  speaker: Speaker;
  text: string;
  delayMs: number;
  brain?: Partial<BrainState>;
};

const fallbackContact: AISDRContact = {
  id: "mock-contact",
  company: "Unknown Company",
  contact: "Unknown Owner",
  phone: "No phone",
  email: "No email",
  industry: "Uncategorized",
  status: "new",
  source: "mock",
  pipeline_stage: "new",
  next_follow_up: null,
  city: "",
  state: "",
  country: "",
  website: "",
  notes: "",
  last_contacted_at: null,
  source_record_id: null,
  source_batch_id: null,
  created_at: "1970-01-01T00:00:00.000Z",
  updated_at: "1970-01-01T00:00:00.000Z",
};

const initialBrain: BrainState = {
  currentGoal: "Confirm pain and book a qualified follow-up.",
  stage: "Opening",
  objection: "None detected",
  sentiment: "Neutral",
  qualificationScore: 42,
  nextAction: "Introduce the reason for the call.",
};

const mockEvents: MockEvent[] = [
  {
    speaker: "system",
    text: "Mock call connected. Twilio is not active.",
    delayMs: 500,
    brain: { stage: "Connected", nextAction: "Start with a short permission-based opener." },
  },
  {
    speaker: "ai",
    text: "Hi, this is Ava from LeadForge. Did I catch you with thirty seconds?",
    delayMs: 900,
    brain: { currentGoal: "Earn permission to continue.", stage: "Opening" },
  },
  {
    speaker: "customer",
    text: "I have a minute, but I am between appointments.",
    delayMs: 1200,
    brain: { sentiment: "Neutral", nextAction: "Acknowledge time pressure and stay concise." },
  },
  {
    speaker: "ai",
    text: "I will be brief. I noticed your site has strong service pages, but the booking path is hard to find on mobile.",
    delayMs: 1100,
    brain: {
      currentGoal: "Surface relevant business pain.",
      stage: "Discovery",
      qualificationScore: 54,
      nextAction: "Ask if mobile booking is a current priority.",
    },
  },
  {
    speaker: "customer",
    text: "That has come up before. We get calls, but online bookings are pretty inconsistent.",
    delayMs: 1300,
    brain: {
      sentiment: "Engaged",
      objection: "No objection detected",
      qualificationScore: 68,
      nextAction: "Quantify the booking gap.",
    },
  },
  {
    speaker: "ai",
    text: "Roughly how many appointment requests do you think are lost each month because people do not complete the form?",
    delayMs: 1200,
    brain: { stage: "Qualification", currentGoal: "Quantify impact.", qualificationScore: 72 },
  },
  {
    speaker: "customer",
    text: "Hard to say, maybe ten to fifteen. We have not measured it closely.",
    delayMs: 1300,
    brain: {
      sentiment: "Interested",
      qualificationScore: 78,
      nextAction: "Suggest a focused audit and ask for meeting time.",
    },
  },
  {
    speaker: "ai",
    text: "That is exactly the kind of gap we can validate quickly. Would a fifteen-minute review tomorrow afternoon be useful?",
    delayMs: 1200,
    brain: { stage: "Close", currentGoal: "Book the next step.", qualificationScore: 84 },
  },
  {
    speaker: "customer",
    text: "Send me a couple of times. If it looks practical, I am open to it.",
    delayMs: 1400,
    brain: {
      sentiment: "Positive",
      objection: "Needs schedule options",
      qualificationScore: 88,
      nextAction: "Confirm email and create meeting follow-up.",
    },
  },
  {
    speaker: "system",
    text: "Mock stream complete. Generate a summary or hang up when ready.",
    delayMs: 800,
    brain: { stage: "Wrap Up", nextAction: "Generate summary and schedule follow-up." },
  },
];

function formatClock(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function speakerLabel(speaker: Speaker) {
  if (speaker === "ai") return "AI";
  if (speaker === "customer") return "Customer";
  return "System";
}

function messageClass(speaker: Speaker) {
  if (speaker === "ai") {
    return "border-primary/30 bg-primary/10 text-foreground";
  }
  if (speaker === "customer") {
    return "border-accent/40 bg-accent/10 text-foreground";
  }
  return "border-border bg-muted/35 text-muted-foreground";
}

function sentimentVariant(sentiment: string) {
  if (["Positive", "Interested", "Engaged"].includes(sentiment)) return "default" as const;
  if (sentiment === "Negative") return "destructive" as const;
  return "secondary" as const;
}

function stringValue(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberValue(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function sourceLabel(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function AICallingWorkspace({ contactId, callId = "" }: { contactId: string; callId?: string }) {
  const [contact, setContact] = useState<AISDRContact>(fallbackContact);
  const [callSession, setCallSession] = useState<AISDRCallSession | null>(null);
  const [liveProviderError, setLiveProviderError] = useState("");
  const [loading, setLoading] = useState(true);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [eventIndex, setEventIndex] = useState(0);
  const [callState, setCallState] = useState<"connecting" | "live" | "ended">("connecting");
  const [muted, setMuted] = useState(false);
  const [aiPaused, setAiPaused] = useState(false);
  const [transferred, setTransferred] = useState(false);
  const [summary, setSummary] = useState("");
  const [brain, setBrain] = useState<BrainState>(initialBrain);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const startedContactRef = useRef<string | null>(null);
  const loadedCallRef = useRef<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function loadContact() {
      setLoading(true);
      if (!contactId || contactId === fallbackContact.id) {
        setContact(fallbackContact);
        setLoading(false);
        return;
      }
      try {
        const nextContact = await getAISDRContact(contactId);
        if (!ignore) {
          setContact(nextContact);
        }
      } catch (error) {
        if (!ignore) {
          toast.error(error instanceof Error ? error.message : "Could not load contact");
          setContact(fallbackContact);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    loadContact();
    return () => {
      ignore = true;
    };
  }, [contactId]);

  useEffect(() => {
    if (!callId || loadedCallRef.current === callId) return;
    loadedCallRef.current = callId;

    async function loadExistingCall() {
      try {
        const session = await getAISDRCall(callId);
        setCallSession(session);
        applyBackendSession(session);
        if (session.contact_id && session.contact_id !== fallbackContact.id) {
          const nextContact = await getAISDRContact(session.contact_id);
          setContact(nextContact);
        }
        setCallState(session.status === "completed" ? "ended" : "live");
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not load call session";
        setLiveProviderError(message);
        toast.error(message);
      }
    }

    loadExistingCall();
  }, [callId]);

  useEffect(() => {
    if (!loading && callState === "connecting") {
      setCallState("live");
    }
  }, [callState, loading]);

  useEffect(() => {
    if (callSession) return;
    if (callState !== "live") return;
    if (eventIndex >= mockEvents.length) return;
    const event = mockEvents[eventIndex];
    if (aiPaused && event.speaker === "ai") return;

    const timer = window.setTimeout(() => {
      addTranscript(event.speaker, event.text);
      if (event.brain) {
        setBrain((previous) => ({ ...previous, ...event.brain }));
      }
      setEventIndex((previous) => previous + 1);
    }, event.delayMs);
    return () => window.clearTimeout(timer);
  }, [aiPaused, callSession, callState, eventIndex]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript]);

  const conversationObjective = useMemo(() => {
    if (callSession?.objective) {
      return callSession.objective;
    }
    const industry = contact.industry || "their market";
    return `Qualify ${contact.company} for a practical website conversion review and book a follow-up with the owner. Focus on ${industry} demand, booking friction, urgency, and decision authority.`;
  }, [callSession?.objective, contact]);

  useEffect(() => {
    if (loading || !contactId || contactId === fallbackContact.id) return;
    if (callId) return;
    if (startedContactRef.current === contactId) return;
    startedContactRef.current = contactId;

    async function startCall() {
      try {
        const session = await startAISDROutboundCall(contactId, conversationObjective);
        setCallSession(session);
        setCallState(session.status === "completed" ? "ended" : "live");
        setTranscript([
          {
            id: `${session.id}-started`,
            speaker: "system",
            text: `Outbound call created through ${session.telephony_provider}. Waiting for live media stream.`,
            at: new Date(session.created_at),
          },
        ]);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Production calling is not configured";
        setLiveProviderError(message);
        addTranscript("system", `Production calling unavailable: ${message}. Mock call events are active.`);
      }
    }

    startCall();
  }, [callId, contactId, conversationObjective, loading]);

  useEffect(() => {
    if (!callSession || callState === "ended") return;
    const timer = window.setInterval(async () => {
      try {
        const nextSession = await getAISDRCall(callSession.id);
        setCallSession(nextSession);
        applyBackendSession(nextSession);
      } catch (error) {
        setLiveProviderError(error instanceof Error ? error.message : "Could not refresh live call");
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [callSession, callState]);

  function addTranscript(speaker: Speaker, text: string) {
    setTranscript((previous) => [
      ...previous,
      {
        id: `${Date.now()}-${previous.length}`,
        speaker,
        text,
        at: new Date(),
      },
    ]);
  }

  function applyBackendSession(session: AISDRCallSession) {
    if (session.transcript.length) {
      setTranscript(
        session.transcript.map((line) => ({
          id: `${session.id}-${line.sequence}`,
          speaker: line.role,
          text: line.text,
          at: line.created_at ? new Date(line.created_at) : new Date(session.updated_at),
        })),
      );
    }
    setBrain((previous) => ({
      ...previous,
      currentGoal: stringValue(session.brain.current_goal, previous.currentGoal),
      stage: stringValue(session.brain.conversation_stage, previous.stage),
      objection: stringValue(session.brain.detected_objection, previous.objection),
      sentiment: stringValue(session.brain.customer_sentiment, previous.sentiment),
      qualificationScore: numberValue(session.brain.qualification_score, previous.qualificationScore),
      nextAction: stringValue(session.brain.suggested_next_action, previous.nextAction),
    }));
    setMuted(session.muted);
    setAiPaused(session.ai_paused);
    setTransferred(session.transfer_requested);
    if (session.outcome) {
      setSummary(session.outcome.conversation_summary);
    }
    if (["completed", "failed", "busy", "no-answer", "canceled"].includes(session.status)) {
      setCallState("ended");
    }
  }

  async function runBackendControl(action: string) {
    if (!callSession) return false;
    try {
      const nextSession = await controlAISDRCall(callSession.id, action);
      setCallSession(nextSession);
      applyBackendSession(nextSession);
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Call control failed");
      return true;
    }
  }

  async function toggleMute() {
    if (await runBackendControl(muted ? "unmute" : "mute")) return;
    const nextMuted = !muted;
    setMuted(nextMuted);
    addTranscript("system", nextMuted ? "Microphone muted." : "Microphone unmuted.");
  }

  async function pauseAI() {
    if (await runBackendControl("pause_ai")) return;
    setAiPaused(true);
    addTranscript("system", "AI paused. Customer audio will remain visible in this mock workspace.");
  }

  async function resumeAI() {
    if (await runBackendControl("resume_ai")) return;
    setAiPaused(false);
    addTranscript("system", "AI resumed.");
  }

  async function hangUp() {
    if (await runBackendControl("hang_up")) return;
    setCallState("ended");
    addTranscript("system", "Call ended. Transcript retained in memory for this session.");
  }

  async function transferToOwner() {
    if (await runBackendControl("transfer_to_owner")) return;
    setTransferred(true);
    setBrain((previous) => ({
      ...previous,
      nextAction: "Owner transfer requested. Brief the owner before handoff.",
    }));
    addTranscript("system", "Transfer to owner requested.");
  }

  async function generateSummary() {
    if (await runBackendControl("generate_summary")) return;
    const customerLines = transcript.filter((line) => line.speaker === "customer").map((line) => line.text);
    const nextSummary = [
      `${contact.company} showed ${brain.sentiment.toLowerCase()} sentiment.`,
      customerLines.length ? `Customer signals: ${customerLines.join(" ")}` : "No customer responses captured yet.",
      `Recommended next action: ${brain.nextAction}`,
    ].join(" ");
    setSummary(nextSummary);
    addTranscript("system", "Summary generated from the in-memory transcript.");
  }

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-background text-foreground">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-border/70 bg-background/95 px-4 backdrop-blur-xl">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link href="/ai-sdr" scroll={false}>
              <ArrowLeft />
              <span className="sr-only">Back to AI SDR</span>
            </Link>
          </Button>
          <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Phone />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm text-muted-foreground">AI Calling Workspace</p>
            <h1 className="truncate text-lg font-semibold tracking-normal">{contact.company}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={callState === "ended" ? "secondary" : "default"}>
            {callState === "ended"
              ? "Call Ended"
              : callState === "connecting"
                ? "Connecting"
                : callSession
                  ? `${sourceLabel(callSession.telephony_provider)} Live`
                  : "Mock Live"}
          </Badge>
          {liveProviderError ? <Badge variant="outline">Provider Fallback</Badge> : null}
          {muted ? <Badge variant="outline">Muted</Badge> : null}
          {aiPaused ? <Badge variant="outline">AI Paused</Badge> : null}
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden p-3 xl:grid-cols-[320px_minmax(420px,1fr)_320px]">
        <aside className="min-h-0 overflow-y-auto rounded-lg border border-border/70 bg-card/80">
          <PanelHeader title="Customer Information" icon={UserRound} description="CRM context for the live call" />
          <div className="flex flex-col gap-5 p-4">
            <InfoRows
              rows={[
                ["Business Name", contact.company],
                ["Owner", contact.contact || "Unknown"],
                ["Website", contact.website || "No website"],
                ["Industry", contact.industry || "Uncategorized"],
                ["Phone", contact.phone || "No phone"],
                ["Email", contact.email || "No email"],
              ]}
            />
            <Separator />
            <TextBlock
              title="Website Analysis"
              body={
                contact.website
                  ? "Website is available for review. Use the opening to confirm whether mobile conversion and booking friction matter right now."
                  : "No website is recorded. Confirm whether the business has an active site before discussing conversion improvements."
              }
            />
            <TextBlock title="Previous Notes" body={contact.notes || "No previous SDR notes recorded."} />
            <TextBlock title="Conversation Objective" body={conversationObjective} />
          </div>
        </aside>

        <section className="flex min-h-0 flex-col rounded-lg border border-border/70 bg-card/70">
          <PanelHeader
            title="Live Transcript"
            icon={Radio}
            description={callSession ? "Streaming from the AI SDR calling backend" : "Mock events stream sentence by sentence"}
          />
          <div className="min-h-0 flex-1 overflow-y-auto p-4" aria-live="polite">
            <div className="flex flex-col gap-3">
              {transcript.map((line) => (
                <div
                  key={line.id}
                  className={cn("rounded-lg border p-3", messageClass(line.speaker))}
                >
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <Badge variant={line.speaker === "system" ? "outline" : "secondary"}>
                      {speakerLabel(line.speaker)}
                    </Badge>
                    <span className="font-mono text-xs text-muted-foreground">{formatClock(line.at)}</span>
                  </div>
                  <p className="text-sm leading-6">{line.text}</p>
                </div>
              ))}
              {!transcript.length ? (
                <div className="grid min-h-80 place-items-center rounded-lg border border-dashed border-border/70 text-center">
                  <div className="flex flex-col items-center gap-2 p-6">
                    <Radio className="text-muted-foreground" />
                    <p className="text-sm font-medium">
                      {callSession ? "Waiting for live call transcript" : "Waiting for mock call events"}
                    </p>
                    <p className="max-w-sm text-sm text-muted-foreground">
                      {callSession
                        ? "Transcript lines will appear here as soon as the provider media stream produces speech."
                        : "Transcript lines will appear here as soon as the simulated conversation starts."}
                    </p>
                  </div>
                </div>
              ) : null}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </section>

        <aside className="min-h-0 overflow-y-auto rounded-lg border border-border/70 bg-card/80">
          <PanelHeader title="AI Brain" icon={Bot} description="Live interpretation from mock events" />
          <div className="flex flex-col gap-5 p-4">
            <BrainItem label="Current Goal" value={brain.currentGoal} />
            <BrainItem label="Conversation Stage" value={brain.stage} />
            <BrainItem label="Detected Objection" value={brain.objection} />
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">Customer Sentiment</span>
              <Badge variant={sentimentVariant(brain.sentiment)}>{brain.sentiment}</Badge>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Qualification Score</span>
                <span className="text-sm font-medium">{brain.qualificationScore}%</span>
              </div>
              <Progress value={brain.qualificationScore} />
            </div>
            <BrainItem label="Suggested Next Action" value={brain.nextAction} />
            {summary ? (
              <>
                <Separator />
                <TextBlock title="Generated Summary" body={summary} />
              </>
            ) : null}
          </div>
        </aside>
      </main>

      <footer className="flex shrink-0 flex-wrap items-center justify-center gap-2 border-t border-border/70 bg-background/95 p-3">
        <Button variant={muted ? "secondary" : "outline"} onClick={toggleMute} disabled={callState === "ended"}>
          {muted ? <MicOff data-icon="inline-start" /> : <Mic data-icon="inline-start" />}
          Mute
        </Button>
        <Button variant="destructive" onClick={hangUp} disabled={callState === "ended"}>
          <PhoneOff data-icon="inline-start" />
          Hang Up
        </Button>
        <Button variant="outline" onClick={pauseAI} disabled={aiPaused || callState === "ended"}>
          <Pause data-icon="inline-start" />
          Pause AI
        </Button>
        <Button variant="outline" onClick={resumeAI} disabled={!aiPaused || callState === "ended"}>
          <Play data-icon="inline-start" />
          Resume AI
        </Button>
        <Button variant="outline" onClick={transferToOwner} disabled={transferred || callState === "ended"}>
          <UserRoundCheck data-icon="inline-start" />
          Transfer To Owner
        </Button>
        <Button variant="outline" onClick={generateSummary} disabled={!transcript.length}>
          <FileText data-icon="inline-start" />
          Generate Summary
        </Button>
      </footer>
    </div>
  );
}

function PanelHeader({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
}) {
  return (
    <div className="border-b border-border/70 p-4">
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <Icon />
          {title}
        </h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function InfoRows({ rows }: { rows: [string, string][] }) {
  return (
    <div className="grid gap-3">
      {rows.map(([label, value]) => (
        <div key={label} className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="break-words text-sm font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}

function TextBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-medium">{title}</h2>
      <p className="text-sm leading-6 text-muted-foreground">{body}</p>
    </div>
  );
}

function BrainItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium leading-6">{value}</span>
    </div>
  );
}
