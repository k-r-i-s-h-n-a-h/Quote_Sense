"use client";

import React, { useState } from "react";
import MarketRatePanel from "@/components/quote/MarketRatePanel";

const PRICING_METHODS = [
  "Area (in sqft)",
  "Per Unit",
  "Area (in sqM)",
  "Lump Sum",
];

const SAMPLE_ITEMS = [
  { category: "Interiors", sub: "Wardrobes" },
  { category: "Interiors", sub: "Tiling" },
  { category: "Interiors", sub: "Modular Kitchen" },
];

export default function MarketRateDemoPage() {
  const [category, setCategory] = useState("Interiors");
  const [subService, setSubService] = useState("Wardrobes");
  const [pricingMethod, setPricingMethod] = useState("Area (in sqft)");
  const [rate, setRate] = useState("");

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-slate-900">Market rate recommendation demo</h1>
      <p className="mt-2 text-sm text-slate-600">
        Mirrors the Tatva PM work item form. The panel appears only when an exact bundle exists
        in <code className="text-xs bg-slate-100 px-1 rounded">market_moving_averages</code>.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Work Item 01</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Main Service</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              >
                {SAMPLE_ITEMS.map((s) => s.category).filter((v, i, a) => a.indexOf(v) === i).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Item / SKU</span>
              <select
                value={subService}
                onChange={(e) => setSubService(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              >
                {SAMPLE_ITEMS.map((s) => (
                  <option key={s.sub} value={s.sub}>{s.sub}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Pricing Method</span>
              <select
                value={pricingMethod}
                onChange={(e) => setPricingMethod(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              >
                {PRICING_METHODS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Rate (₹)</span>
              <input
                type="number"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                placeholder="0"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              />
            </label>
          </div>
        </section>

        <MarketRatePanel
          serviceCategory={category}
          subService={subService}
          pricingMethod={pricingMethod}
          enteredRate={rate ? Number.parseFloat(rate) : undefined}
        />
      </div>
    </div>
  );
}
