import { Badge } from "@/components/ui/badge";
import { statusLabel } from "@/lib/format";

const tone: Record<string, string> = {
  completed: "border-primary/30 bg-primary/10 text-primary",
  running: "border-accent/30 bg-accent/10 text-accent",
  qualified: "border-primary/30 bg-primary/10 text-primary",
  sent: "border-accent/30 bg-accent/10 text-accent",
  opened: "border-chart-3/30 bg-chart-3/10 text-chart-3",
  replied: "border-primary/30 bg-primary/10 text-primary",
  closed: "border-border bg-secondary/60 text-muted-foreground",
  missing: "border-border bg-secondary/60 text-muted-foreground",
  failed: "border-destructive/30 bg-destructive/10 text-destructive",
  draft: "border-border bg-secondary/60 text-muted-foreground",
  not_started: "border-border bg-secondary/60 text-muted-foreground",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <Badge variant="outline" className={tone[value] ?? "border-border bg-secondary/60 text-muted-foreground"}>
      {statusLabel(value)}
    </Badge>
  );
}
