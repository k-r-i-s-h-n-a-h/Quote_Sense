"use client";

import { useEffect, useMemo, useState } from "react";
import { MailIcon } from "../MailIcon";
import { WhatsAppIcon } from "../WhatsAppIcon";
import type { VendorMeta } from "../../lib/format";
import type { CrossScopeRow, SpaceNote, SpaceRow, Vendor } from "../../lib/compare-types";
import {
  buildAskVendorPanels,
  formatVendorBrief,
  type AskVendorPanel,
} from "../../lib/vendor-questions";

type SendChannel = "whatsapp" | "email";

type PanelState = { checked: string[]; notes: string };

type Props = {
  vendors: Vendor[];
  vendorMeta?: Record<string, VendorMeta>;
  spaceNotes?: SpaceNote[];
  crossScope?: CrossScopeRow[];
  rows?: SpaceRow[];
  storageKey?: string;
};

function defaultState(panels: AskVendorPanel[]): Record<string, PanelState> {
  const next: Record<string, PanelState> = {};
  for (const panel of panels) {
    next[panel.key] = {
      checked: panel.questions.map((q) => q.id),
      notes: "",
    };
  }
  return next;
}

function Checklist({
  panel,
  state,
  onToggle,
  onNotes,
}: {
  panel: AskVendorPanel;
  state: PanelState;
  onToggle: (id: string) => void;
  onNotes: (notes: string) => void;
}) {
  return (
    <div>
      <ul className="space-y-3">
        {panel.questions.map((q) => {
          const on = state.checked.includes(q.id);
          return (
            <li key={`${panel.key}:${q.id}`}>
              <label className="flex gap-3 items-start cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-stone-300 text-[var(--accent)] focus:ring-[var(--accent)]"
                  checked={on}
                  onChange={() => onToggle(q.id)}
                />
                <span>
                  <span className="block text-sm text-stone-800 leading-snug">
                    {q.text}
                  </span>
                  {q.why ? (
                    <span className="block text-xs text-stone-500 mt-1 leading-relaxed">
                      {q.why}
                    </span>
                  ) : null}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <label className="block mt-5">
        <span className="block text-xs font-medium text-stone-500 mb-1.5">
          Your notes for {panel.company}
        </span>
        <textarea
          value={state.notes}
          onChange={(e) => onNotes(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30 focus:border-[var(--accent)]"
          placeholder="Anything else you want this vendor to confirm — finishes, brand, warranty, timeline, what’s excluded…"
        />
      </label>
    </div>
  );
}

export default function AskVendors({
  vendors,
  vendorMeta,
  spaceNotes,
  crossScope,
  rows,
  storageKey,
}: Props) {
  const { sameCompany, panels } = useMemo(
    () =>
      buildAskVendorPanels({
        vendors,
        vendorMeta,
        spaceNotes,
        crossScope,
        rows,
      }),
    [vendors, vendorMeta, spaceNotes, crossScope, rows]
  );

  const persistKey = storageKey || `qs-ask-vendors:${vendors.join("|")}`;
  const [byPanel, setByPanel] = useState<Record<string, PanelState>>(() =>
    defaultState(panels)
  );
  const [copiedKey, setCopiedKey] = useState("");
  const [statusKey, setStatusKey] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [sendingKey, setSendingKey] = useState("");
  const [sendingChannel, setSendingChannel] = useState<SendChannel | "">("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(persistKey);
      if (raw) {
        const saved = JSON.parse(raw) as Record<string, PanelState>;
        if (saved && typeof saved === "object") {
          setByPanel((prev) => ({ ...defaultState(panels), ...saved }));
          return;
        }
      }
    } catch {
      /* ignore a stale or broken payload */
    }
    setByPanel(defaultState(panels));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persistKey]);

  useEffect(() => {
    try {
      sessionStorage.setItem(persistKey, JSON.stringify(byPanel));
    } catch {
      /* quota / private mode */
    }
  }, [byPanel, persistKey]);

  const toggle = (key: string, id: string) => {
    setByPanel((prev) => {
      const cur = prev[key] || { checked: [], notes: "" };
      const checked = cur.checked.includes(id)
        ? cur.checked.filter((x) => x !== id)
        : [...cur.checked, id];
      return { ...prev, [key]: { ...cur, checked } };
    });
  };

  const setNotes = (key: string, notes: string) => {
    setByPanel((prev) => {
      const cur = prev[key] || { checked: [], notes: "" };
      return { ...prev, [key]: { ...cur, notes } };
    });
  };

  const copyPanel = async (panel: AskVendorPanel) => {
    const state = byPanel[panel.key] || { checked: [], notes: "" };
    const text = formatVendorBrief(
      panel.questions,
      state.checked,
      state.notes,
      panel.title + (panel.subtitle ? ` (${panel.subtitle})` : "")
    );
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(panel.key);
      window.setTimeout(() => setCopiedKey(""), 2000);
    } catch {
      setCopiedKey("");
    }
  };

  const sendToVendor = async (panel: AskVendorPanel, channel: SendChannel) => {
    const state = byPanel[panel.key] || { checked: [], notes: "" };
    if (channel === "whatsapp" && !panel.phone) {
      setStatusKey(panel.key);
      setStatusMessage("No vendor phone on this quote yet.");
      return;
    }
    if (channel === "email" && !panel.email) {
      setStatusKey(panel.key);
      setStatusMessage("No vendor email on this quote yet.");
      return;
    }
    const chosen = panel.questions
      .filter((q) => state.checked.includes(q.id))
      .map((q) => q.text);
    if (!chosen.length) return;
    setSendingKey(panel.key);
    setSendingChannel(channel);
    setStatusKey(panel.key);
    setStatusMessage("Sending…");
    const path =
      channel === "email" ? "/api/ask-vendors/email" : "/api/ask-vendors/whatsapp";
    const body =
      channel === "email"
        ? {
            email: panel.email,
            vendor_name: panel.company,
            quote_number: panel.quoteNumber,
            questions: chosen,
            notes: state.notes || "",
          }
        : {
            phone: panel.phone,
            vendor_name: panel.company,
            quote_number: panel.quoteNumber,
            questions: chosen,
            notes: state.notes || "",
          };
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await res.json()) as { status?: string };
      if (!res.ok || data.status === "error") {
        if (channel === "email" && res.status === 503) {
          setStatusMessage(
            "Email isn’t ready yet. Copy the questions or use WhatsApp."
          );
        } else if (channel === "email") {
          setStatusMessage(
            "Couldn’t send email. Try again or copy the questions."
          );
        } else {
          setStatusMessage(
            "Couldn’t send WhatsApp. Try again or copy the questions."
          );
        }
        return;
      }
      setStatusMessage("Sent.");
    } catch {
      setStatusMessage(
        channel === "email"
          ? "Couldn’t send email. Try again or copy the questions."
          : "Couldn’t send WhatsApp. Try again or copy the questions."
      );
    } finally {
      setSendingKey("");
      setSendingChannel("");
    }
  };

  return (
    <section className="qs-card p-5 md:p-6">
      <div className="mb-5">
        <h2 className="qs-section-title">Ask the vendors</h2>
        <p className="qs-section-sub">
          {sameCompany
            ? "Both quotes are from the same vendor — one checklist. Tick what they still need to confirm, then email, WhatsApp, or copy."
            : "Each vendor gets their own checklist. Tick what to send, then email, WhatsApp, or copy."}
        </p>
      </div>

      <div className="space-y-8">
        {panels.map((panel) => {
          const state = byPanel[panel.key] || {
            checked: panel.questions.map((q) => q.id),
            notes: "",
          };
          return (
            <div
              key={panel.key}
              className={
                panels.length > 1
                  ? "rounded-lg border border-stone-200 p-4 md:p-5"
                  : ""
              }
            >
              <div className="mb-4">
                <h3 className="text-base font-semibold text-stone-900">
                  {panel.title}
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">{panel.subtitle}</p>
              </div>
              <Checklist
                panel={panel}
                state={state}
                onToggle={(id) => toggle(panel.key, id)}
                onNotes={(notes) => setNotes(panel.key, notes)}
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => copyPanel(panel)}
                  disabled={!state.checked.length && !state.notes.trim()}
                  className="qs-btn qs-btn-secondary"
                >
                  {copiedKey === panel.key ? "Copied" : "Copy questions"}
                </button>
                <button
                  type="button"
                  onClick={() => sendToVendor(panel, "email")}
                  disabled={
                    !state.checked.length ||
                    !panel.email ||
                    sendingKey === panel.key
                  }
                  className="qs-btn qs-btn-primary inline-flex items-center gap-2"
                >
                  <MailIcon className="w-4 h-4 text-white" />
                  {sendingKey === panel.key && sendingChannel === "email"
                    ? "Sending…"
                    : `Email ${panel.company}`}
                </button>
                <button
                  type="button"
                  onClick={() => sendToVendor(panel, "whatsapp")}
                  disabled={
                    !state.checked.length ||
                    !panel.phone ||
                    sendingKey === panel.key
                  }
                  className="qs-btn inline-flex items-center gap-2 !bg-[#25D366] !text-white hover:!bg-[#1ebe5d] disabled:opacity-50"
                >
                  <WhatsAppIcon className="w-4 h-4 text-white" />
                  {sendingKey === panel.key && sendingChannel === "whatsapp"
                    ? "Sending…"
                    : `WhatsApp ${panel.company}`}
                </button>
                <p className="text-[11px] text-stone-400">
                  {state.checked.length} selected
                  {panel.email
                    ? ` · ${panel.email}`
                    : " · no email on this quote yet"}
                  {panel.phone
                    ? ` · ${panel.phone}`
                    : " · no phone on this quote yet"}
                </p>
              </div>
              {statusKey === panel.key && statusMessage ? (
                <p className="mt-2 text-xs text-stone-500">{statusMessage}</p>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
