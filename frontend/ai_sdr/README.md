# AI SDR Frontend Module

The `frontend/ai_sdr` folder owns the AI SDR user interface, API client, and TypeScript contracts.

## Boundaries

Allowed shared dependencies:

- `@/components/ui/*` shadcn primitives
- `@/lib/utils` if shared styling helpers are needed
- authentication shell and app routing

Not allowed:

- imports from Lead Generator pages or components
- imports from `@/lib/api`
- Twilio or external telephony SDKs in this architecture-only phase

## Files

- `api.ts` owns AI SDR API calls under `/ai-sdr`
- `types.ts` owns SDR source, batch, record, and contact contracts
- `components/ai-sdr-workspace.tsx` owns the SDR workspace UI
- `components/ai-calling-workspace.tsx` owns the full-screen mock AI Calling Workspace
- `components/ai-calling-route.tsx` reads `contactId` from the static-export compatible call route
- `../src/app/ai-sdr/page.tsx` mounts the module into the Next app
- `../src/app/ai-sdr/call/page.tsx` mounts the calling workspace at `/ai-sdr/call?contactId=<crm_lead_id>`

## Source Coverage

The UI and contracts expose CSV, Excel, Google Sheets, Manual Entry, REST API, CRM, and future integrations. Manual Entry is available from the workspace. File, sheet, CRM, and future connectors should emit contact dictionaries into the same `/ai-sdr/imports` contract.

## Calling Workspace

Clicking the Call action on a contact opens `/ai-sdr/call?contactId=<crm_lead_id>` as a full-screen workspace over the LeadForge shell.

The workspace is UI-only and uses mock events. It does not import Twilio, start phone calls, or persist call transcripts yet.

The screen contains:

- Customer Information with CRM fields, website analysis, notes, and the conversation objective
- Live Transcript with separate visual treatments for AI, customer, and system messages
- AI Brain with goal, stage, objection, sentiment, qualification score, and suggested next action
- Bottom call controls for Mute, Hang Up, Pause AI, Resume AI, Transfer To Owner, and Generate Summary

Transcript lines are stored in component memory for the active session. Mock events stream sentence by sentence and auto-scroll the transcript panel.
