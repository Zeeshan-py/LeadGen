"use client";

/**
 * Static-export compatible route adapter for the AI Calling Workspace.
 *
 * Next static export cannot prebuild arbitrary contact IDs, so the workspace
 * reads `contactId` and optional `callId` from the query string.
 */

import { useSearchParams } from "next/navigation";

import { AICallingWorkspace } from "./ai-calling-workspace";

export function AICallingRoute() {
  const searchParams = useSearchParams();
  const contactId = searchParams.get("contactId") || "mock-contact";
  const callId = searchParams.get("callId") || "";

  return <AICallingWorkspace contactId={contactId} callId={callId} />;
}
