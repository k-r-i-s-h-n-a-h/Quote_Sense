/** Tatva product suite — shared ecosystem app switcher config. */

export type TatvaAppId =
  | "ops"
  | "compare"
  | "direct"
  | "finance"
  | "vantage"
  | "vision";

export type TatvaApp = {
  id: TatvaAppId;
  name: string;
  description: string;
  href: string;
  nameClassName: string;
};

export const CURRENT_APP_ID: TatvaAppId = "compare";

export const CURRENT_APP_LABEL = "Connect";

function envUrl(key: string, fallback = ""): string {
  return process.env[key]?.trim() || fallback;
}

export function getTatvaEcosystemApps(): TatvaApp[] {
  return [
    {
      id: "ops",
      name: "Ops",
      description: "Site operations",
      href: envUrl("NEXT_PUBLIC_OPS_URL", "https://tatvaops.com/"),
      nameClassName:
        "bg-gradient-to-r from-orange-500 to-amber-500 bg-clip-text text-transparent",
    },
    {
      id: "compare",
      name: "Connect",
      description: "Projects & vendors",
      href:
        process.env.NEXT_PUBLIC_CONNECT_URL?.trim() ||
        process.env.NEXT_PUBLIC_COMPARE_URL?.trim() ||
        "/",
      nameClassName:
        "bg-gradient-to-r from-orange-500 to-violet-500 bg-clip-text text-transparent",
    },
    {
      id: "direct",
      name: "Direct",
      description: "Materials & e-commerce",
      href: envUrl(
        "NEXT_PUBLIC_DIRECT_URL",
        "https://tatva-direct-frontend-five.vercel.app"
      ),
      nameClassName:
        "bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent",
    },
    {
      id: "finance",
      name: "Finance",
      description: "Credit & payments",
      href: envUrl("NEXT_PUBLIC_FINANCE_URL", "https://finance.withtatva.ai"),
      nameClassName: "text-blue-600",
    },
    {
      id: "vantage",
      name: "Vantage",
      description: "Knowledge platform",
      href: envUrl("NEXT_PUBLIC_VANTAGE_URL", "https://vantage.withtatva.ai"),
      nameClassName:
        "bg-gradient-to-r from-violet-500 to-pink-500 bg-clip-text text-transparent",
    },
    {
      id: "vision",
      name: "Vision",
      description: "Site monitoring",
      href: envUrl("NEXT_PUBLIC_VISION_URL", "https://vision.withtatva.ai"),
      nameClassName: "text-blue-600",
    },
  ];
}
