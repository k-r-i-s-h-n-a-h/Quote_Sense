"use client";

import React, { useState } from "react";
import MarketRatePanel from "@/components/quote/MarketRatePanel";
import { PageHeader } from "@/components/ui/PageHeader";

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
    <div className="qs-container py-8 md:py-10">
      <PageHeader
        eyebrow="Market rates"
        title="Market rate recommendation demo"
        description={
          <>
            Mirrors the Tatva PM work item form. The panel appears only when an
            exact bundle exists in{" "}
            <code className="text-xs bg-stone-100 px-1.5 py-0.5 rounded">
              market_moving_averages
            </code>
            .
          </>
        }
      />

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        <section className="qs-card p-6">
          <h2 className="font-semibold text-stone-800">Work item 01</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium text-stone-700">Main service</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="qs-select mt-1"
              >
                {SAMPLE_ITEMS.map((s) => s.category)
                  .filter((v, i, a) => a.indexOf(v) === i)
                  .map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-stone-700">Item / SKU</span>
              <select
                value={subService}
                onChange={(e) => setSubService(e.target.value)}
                className="qs-select mt-1"
              >
                {SAMPLE_ITEMS.map((s) => (
                  <option key={s.sub} value={s.sub}>
                    {s.sub}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-stone-700">Pricing method</span>
              <select
                value={pricingMethod}
                onChange={(e) => setPricingMethod(e.target.value)}
                className="qs-select mt-1"
              >
                {PRICING_METHODS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-stone-700">Entered rate</span>
              <input
                type="number"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                placeholder="e.g. 1850"
                className="qs-input mt-1"
              />
            </label>
          </div>
        </section>

        <MarketRatePanel
          serviceCategory={category}
          subService={subService}
          pricingMethod={pricingMethod}
          enteredRate={rate ? Number(rate) : undefined}
        />
      </div>
    </div>
  );
}
