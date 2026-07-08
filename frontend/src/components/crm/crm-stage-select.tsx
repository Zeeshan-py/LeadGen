"use client";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  crmStageLabels,
  crmStages,
  type CrmStage,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export function CrmStageSelect({
  value,
  onValueChange,
  className,
}: {
  value: CrmStage;
  onValueChange: (value: CrmStage) => void;
  className?: string;
}) {
  return (
    <Select
      value={value}
      onValueChange={(next) => onValueChange(next as CrmStage)}
    >
      <SelectTrigger
        className={cn("border-primary/30 bg-primary/10 text-primary", className)}
        aria-label="CRM stage"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {crmStages.map((stage) => (
            <SelectItem key={stage} value={stage}>
              {crmStageLabels[stage]}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
