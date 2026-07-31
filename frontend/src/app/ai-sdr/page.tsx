import { AISDRWorkspace } from "../../../ai_sdr";
import { SubscriptionGate } from "@/components/subscription-gate";

export default function AISDRPage() {
  return (
    <SubscriptionGate feature="ai_sdr" benefits={["AI SDR", "Automated Calling", "Campaign Automation"]}>
      <AISDRWorkspace />
    </SubscriptionGate>
  );
}
