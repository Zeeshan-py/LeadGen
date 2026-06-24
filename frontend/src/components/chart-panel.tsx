"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const leadConfig = {
  leads: { label: "Leads", color: "var(--chart-1)" },
  emails: { label: "Emails", color: "var(--chart-2)" },
  count: { label: "Count", color: "var(--chart-3)" },
} satisfies ChartConfig;

export function AreaPanel({
  title,
  data,
  dataKey,
}: {
  title: string;
  data: Record<string, string | number>[];
  dataKey: "leads" | "emails";
}) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={leadConfig} className="h-[260px] w-full">
          <AreaChart data={data}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={32} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={`var(--color-${dataKey})`}
              fill={`var(--color-${dataKey})`}
              fillOpacity={0.2}
              strokeWidth={2}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

export function BarPanel({
  title,
  data,
  labelKey,
}: {
  title: string;
  data: Record<string, string | number>[];
  labelKey: "city" | "niche";
}) {
  return (
    <Card className="glass-panel">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={leadConfig} className="h-[260px] w-full">
          <BarChart data={data}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey={labelKey} tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={32} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" radius={6} fill="var(--color-count)" />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
