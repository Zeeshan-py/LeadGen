import type { LucideIcon } from "lucide-react";
import { ArrowUpRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function MetricCard({
  title,
  value,
  detail,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="glass-panel">
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-3">
          <p className="text-3xl font-semibold tracking-normal">{value}</p>
          <ArrowUpRight className="mb-1 size-4 text-primary" />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}
