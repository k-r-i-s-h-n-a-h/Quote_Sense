"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import { vendorColor } from "../lib/vendor-colors";

type ChartRow = { vendor: string; total: number };

type ChartPoint = ChartRow & {
  key: string;
  line1: string;
  line2: string;
  labelFull: string;
  color: string;
};

/** Two-line tilted X-axis tick: company on top, variant / quote no. below. */
function makeTick(points: ChartPoint[]) {
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
        <text x={0} y={0} textAnchor="end" fill="#57534e" fontSize={9}>
          <tspan x={0} dy={10} fontWeight={600}>
            {p.line1}
          </tspan>
          {p.line2 ? (
            <tspan x={0} dy={11} fill="#78716c">
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
    return data.map((row, index) => {
      const info = labels[row.vendor];
      const company = truncateLabel(info.company, 18);
      const secondBits: string[] = [];
      if (info.variant) secondBits.push(truncateLabel(info.variant, 16));
      if (info.quoteNumber) secondBits.push(`#${info.quoteNumber}`);
      const line2 = secondBits.join("  ");

      const base = info.label;
      const count = seen[base] ?? 0;
      seen[base] = count + 1;
      const key = base + "\u200B".repeat(count);

      return {
        ...row,
        key,
        line1: company,
        line2,
        labelFull: info.full,
        color: vendorColor(index),
      };
    });
  }, [data, meta]);

  const totals = useMemo(() => data.map((d) => Number(d.total) || 0), [data]);
  const yAxis = useMemo(() => getChartYAxisConfig(totals), [totals]);

  return (
    <div className="h-[22rem] sm:h-[24rem] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          margin={{ top: 8, right: 12, left: 8, bottom: 96 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7e5e4" />
          <XAxis
            dataKey="key"
            interval={0}
            height={108}
            tick={makeTick(points)}
            axisLine={{ stroke: "#d6d3d1" }}
            tickLine={false}
          />
          <YAxis
            domain={yAxis.domain}
            ticks={yAxis.ticks}
            allowDecimals={false}
            tickFormatter={yAxis.formatTick}
            tick={{ fontSize: 10, fill: "#78716c" }}
            width={48}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(28, 25, 23, 0.04)" }}
            formatter={(value) => [formatInrFull(Number(value)), "Grand total"]}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as ChartPoint | undefined;
              return row?.labelFull ?? "";
            }}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e7e5e4",
              fontSize: "13px",
              boxShadow: "0 4px 12px rgba(28,25,23,0.08)",
            }}
          />
          <Bar dataKey="total" radius={[4, 4, 0, 0]}>
            {points.map((entry) => (
              <Cell key={entry.key} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
