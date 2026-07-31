import { Suspense } from "react";

import { AICallingRoute } from "../../../../ai_sdr";
import { SubscriptionGate } from "@/components/subscription-gate";

export default function AICallPage() {
  return (
    <SubscriptionGate
      feature="ai_sdr"
      benefits={["AI SDR", "Automated Calling", "Live call workspace"]}
    >
      <Suspense
        fallback={
          <div className="fixed inset-0 z-[60] grid place-items-center bg-background text-sm text-muted-foreground">
            Loading AI Calling Workspace...
          </div>
        }
      >
        <AICallingRoute />
      </Suspense>
    </SubscriptionGate>
  );
}
