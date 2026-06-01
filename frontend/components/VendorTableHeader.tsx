"use client";

import { vendorCompanyName } from "../lib/format";

/** Table column header: company name + optional PDF on separate lines. */
export default function VendorTableHeader({ vendor }: { vendor: string }) {
  const company = vendorCompanyName(vendor);
  const fileMatch = vendor.match(/\(([^)]+)\)\s*$/);
  const file = fileMatch?.[1];

  return (
    <div
      className="min-w-[7.5rem] max-w-[11rem] ml-auto text-right"
      title={vendor}
    >
      <div className="text-[10px] font-bold leading-snug line-clamp-3 break-words normal-case tracking-normal text-gray-800">
        {company}
      </div>
      {file && (
        <div className="text-[9px] font-normal text-gray-400 truncate mt-0.5 normal-case tracking-normal">
          {file}
        </div>
      )}
    </div>
  );
}
