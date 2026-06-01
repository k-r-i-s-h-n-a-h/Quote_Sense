"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  formatInrFull,
  getChartYAxisConfig,
  vendorChartLabel,
  vendorCompanyName,
} from "../lib/format";

type ChartRow = { vendor: string; total: number };

type ChartPoint = ChartRow & { labelShort: string; labelFull: string };

/** Tilted, truncated company name (no PDF filename). */
function VendorXAxisTick({
  x,
  y,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value?: string };
}) {
  if (x == null || y == null) return null;
  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={12}
        textAnchor="end"
        fill="#64748b"
        fontSize={9}
        transform="rotate(-38)"
      >
        {payload?.value ?? ""}
      </text>
    </g>
  );
}

export default function VendorChart({ data }: { data: ChartRow[] }) {
  const points: ChartPoint[] = useMemo(
    () =>
      data.map((row) => ({
        ...row,
        labelShort: vendorChartLabel(row.vendor, 14),
        labelFull: vendorCompanyName(row.vendor),
      })),
    [data]
  );

  const totals = useMemo(
    () => data.map((d) => Number(d.total) || 0),
    [data]
  );

  const yAxis = useMemo(() => getChartYAxisConfig(totals), [totals]);

  return (
    <div className="h-[22rem] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 12, left: 8, bottom: 80 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="labelShort"
            interval={0}
            height={92}
            tick={<VendorXAxisTick />}
          />
          <YAxis
            domain={yAxis.domain}
            ticks={yAxis.ticks}
            allowDecimals={false}
            tickFormatter={yAxis.formatTick}
            tick={{ fontSize: 10, fill: "#4b5563" }}
            width={48}
          />
          <Tooltip
            formatter={(value) => [formatInrFull(Number(value)), "Grand total"]}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as ChartPoint | undefined;
              return row?.labelFull ?? "";
            }}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "13px",
            }}
          />
          <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
