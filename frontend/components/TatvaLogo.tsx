import Image from "next/image";

type TatvaLogoProps = {
  size?: "sm" | "md" | "lg";
  className?: string;
};

const sizes = {
  sm: { w: 120, h: 36 },
  md: { w: 160, h: 48 },
  lg: { w: 200, h: 60 },
};

export default function TatvaLogo({ size = "md", className = "" }: TatvaLogoProps) {
  const { w, h } = sizes[size];
  return (
    <Image
      src="/tatva_assets.jpg"
      alt="Tatva Ops"
      width={w}
      height={h}
      className={`object-contain ${className}`}
      priority
      unoptimized
    />
  );
}
