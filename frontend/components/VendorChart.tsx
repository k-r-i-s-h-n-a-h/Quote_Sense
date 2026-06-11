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
  buildVendorLabels,
  formatInrFull,
  getChartYAxisConfig,
  truncateLabel,
  type VendorMeta,
} from "../lib/format";

type ChartRow = { vendor: string; total: number };

type ChartPoint = ChartRow & {
  key: string;
  line1: string;
  line2: string;
  labelFull: string;
};

/** Two-line tilted X-axis tick: company on top, variant / quote no. below. */
function makeTick(points: ChartPoint[]) {
  // Recharts' tick render prop is loosely typed (x/y can be string|number),
  // so accept a permissive props object and coerce to numbers here.
  return function VendorXAxisTick(props: {
    x?: string | number;
    y?: string | number;
    index?: number;
  }) {
    const { x, y, index } = props;
    if (x == null || y == null || index == null) return null;
    const px = Number(x);
    const py = Number(y);
    const p = points[index];
    if (!p) return null;
    return (
      <g transform={`translate(${px},${py}) rotate(-38)`}>
        <text x={0} y={0} textAnchor="end" fill="#475569" fontSize={9}>
          <tspan x={0} dy={10} fontWeight={600}>
            {p.line1}
          </tspan>
          {p.line2 ? (
            <tspan x={0} dy={11} fill="#64748b">
              {p.line2}
            </tspan>
          ) : null}
        </text>
      </g>
    );
  };
}

export default function VendorChart({
  data,
  meta,
}: {
  data: ChartRow[];
  meta?: Record<string, VendorMeta>;
}) {
  const points: ChartPoint[] = useMemo(() => {
    const labels = buildVendorLabels(
      data.map((d) => d.vendor),
      meta
    );
    const seen: Record<string, number> = {};
    return data.map((row) => {
      const info = labels[row.vendor];
      const company = truncateLabel(info.company, 18);
      // Second line: variant and/or quote number for separation.
      const secondBits: string[] = [];
      if (info.variant) secondBits.push(truncateLabel(info.variant, 16));
      if (info.quoteNumber) secondBits.push(`#${info.quoteNumber}`);
      const line2 = secondBits.join("  ");

      // Keep each category key unique so Recharts never merges bars.
      const base = info.label;
      const count = seen[base] ?? 0;
      seen[base] = count + 1;
      const key = base + "\u200B".repeat(count);

      return { ...row, key, line1: company, line2, labelFull: info.full };
    });
  }, [data, meta]);

  const totals = useMemo(() => data.map((d) => Number(d.total) || 0), [data]);
  const yAxis = useMemo(() => getChartYAxisConfig(totals), [totals]);

  return (
    <div className="h-[24rem] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 12, left: 8, bottom: 96 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="key"
            interval={0}
            height={108}
            tick={makeTick(points)}
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
            cursor={{ fill: "rgba(59,130,246,0.06)" }}
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
