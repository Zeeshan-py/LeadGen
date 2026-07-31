"use client";

import { CrmWorkspace } from "@/components/crm/crm-workspace";
import { SubscriptionGate } from "@/components/subscription-gate";

export default function CrmPage() {
  return (
    <SubscriptionGate feature="crm" benefits={["CRM pipeline", "Lead notes and stages", "Follow-up tracking"]}>
      <CrmWorkspace />
    </SubscriptionGate>
  );
}
