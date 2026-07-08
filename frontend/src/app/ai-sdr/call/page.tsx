import { Suspense } from "react";

import { AICallingRoute } from "../../../../ai_sdr";

export default function AICallPage() {
  return (
    <Suspense
      fallback={
        <div className="fixed inset-0 z-[60] grid place-items-center bg-background text-sm text-muted-foreground">
          Loading AI Calling Workspace...
        </div>
      }
    >
      <AICallingRoute />
    </Suspense>
  );
}
