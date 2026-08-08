import { getBackendBase } from "./backend-url";

export type MarketRateLookup = {
  recommend: boolean;
  message: string;
  service_type?: string;
  service_category?: string;
  sub_service?: string;
  pricing_method?: string;
  market_rate?: number;
  weight?: number;
  entered_rate?: number;
  verdict?: "low" | "fair" | "high";
};

export type MarketRateParams = {
  service_type?: string;
  service_category: string;
  sub_service: string;
  pricing_method: string;
  entered_rate?: number;
};

export async function lookupMarketRate(
  params: MarketRateParams
): Promise<MarketRateLookup> {
  const qs = new URLSearchParams({
    service_type: params.service_type || "ESSENTIAL",
    service_category: params.service_category,
    sub_service: params.sub_service,
    pricing_method: params.pricing_method,
  });
  const res = await fetch(`${getBackendBase()}/api/market-rate/lookup?${qs}`);
  if (!res.ok) {
    return { recommend: false, message: "Could not load market data." };
  }
  return res.json();
}

export async function recommendMarketRate(
  params: MarketRateParams
): Promise<MarketRateLookup> {
  const res = await fetch(`${getBackendBase()}/api/market-rate/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      service_type: params.service_type || "ESSENTIAL",
      service_category: params.service_category,
      sub_service: params.sub_service,
      pricing_method: params.pricing_method,
      entered_rate: params.entered_rate,
    }),
  });
  if (!res.ok) {
    return { recommend: false, message: "Could not load market data." };
  }
  return res.json();
}

export function verdictStyles(verdict?: string): {
  border: string;
  bg: string;
  text: string;
  badge: string;
} {
  if (verdict === "low") {
    return {
      border: "border-amber-300",
      bg: "bg-amber-50",
      text: "text-amber-900",
      badge: "bg-amber-100 text-amber-800",
    };
  }
  if (verdict === "high") {
    return {
      border: "border-red-300",
      bg: "bg-red-50",
      text: "text-red-900",
      badge: "bg-red-100 text-red-800",
    };
  }
  if (verdict === "fair") {
    return {
      border: "border-emerald-300",
      bg: "bg-emerald-50",
      text: "text-emerald-900",
      badge: "bg-emerald-100 text-emerald-800",
    };
  }
  return {
    border: "border-slate-200",
    bg: "bg-slate-50",
    text: "text-slate-700",
    badge: "bg-slate-100 text-slate-700",
  };
}
