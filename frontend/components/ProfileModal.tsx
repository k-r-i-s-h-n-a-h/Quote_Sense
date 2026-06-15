"use client";

import React, { useEffect, useState } from "react";
import { getAuthToken, useAuth } from "@/lib/auth";

type ProfileModalProps = {
  open: boolean;
  onClose: () => void;
};

function FieldIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex w-4 h-4 text-slate-500 shrink-0">{children}</span>
  );
}

export default function ProfileModal({ open, onClose }: ProfileModalProps) {
  const { user, refreshProfile } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", username: "", email: "" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && user) {
      setForm({
        name: user.name || user.fullName || "",
        username: user.username || "",
        email: user.email || "",
      });
      setEditing(false);
      setError(null);
      refreshProfile();
    }
  }, [open, user, refreshProfile]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open || !user) return null;

  const displayName = user.name || user.fullName || "User";
  const userId = user._id || user.id;

  const handleSave = async () => {
    if (!userId) return;
    const token = getAuthToken();
    if (!token) return;

    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/auth/profile?userId=${userId}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: form.name,
          username: form.username,
          email: form.email,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.success === false) {
        setError(data.message || "Failed to update profile.");
        return;
      }
      await refreshProfile();
      setEditing(false);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <button
        type="button"
        className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="Close profile"
      />

      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white z-10 px-8 pt-8 pb-4 border-b border-slate-100">
          <button
            type="button"
            onClick={onClose}
            className="absolute top-5 right-5 w-8 h-8 flex items-center justify-center text-slate-400 hover:text-slate-600"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
          <h2 className="text-2xl font-bold text-slate-900">Customer Profile</h2>
          <p className="text-sm text-slate-500 mt-1">Manage your personal information</p>
        </div>

        <div className="px-8 py-6">
          <div className="border border-slate-200 rounded-2xl p-6">
            {/* Avatar + name */}
            <div className="flex flex-col items-center pb-6 border-b border-slate-100">
              <div className="relative">
                <div className="w-24 h-24 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center">
                  <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                </div>
                <span className="absolute bottom-0 right-0 w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center border-2 border-white">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </span>
              </div>
              <h3 className="mt-4 text-lg font-bold text-slate-900">{displayName}</h3>
              <p className="text-sm text-slate-500">Customer Account</p>
            </div>

            {/* Edit button */}
            <div className="flex justify-end py-4">
              {!editing ? (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 text-white text-sm font-medium rounded-lg hover:bg-slate-900 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                  Edit Profile
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setForm({
                        name: user.name || user.fullName || "",
                        username: user.username || "",
                        email: user.email || "",
                      });
                    }}
                    className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className="px-4 py-2 text-sm bg-[#c04a00] text-white rounded-lg hover:bg-[#a84000] disabled:opacity-50"
                  >
                    {saving ? "Saving…" : "Save Changes"}
                  </button>
                </div>
              )}
            </div>

            {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

            {/* Fields grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <ProfileField
                label="Full Name"
                icon={
                  <FieldIcon>
                    <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" /></svg>
                  </FieldIcon>
                }
                value={form.name}
                editing={editing}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
              />
              <ProfileField
                label="Username"
                icon={
                  <FieldIcon>
                    <svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" /></svg>
                  </FieldIcon>
                }
                value={form.username}
                editing={editing}
                onChange={(v) => setForm((f) => ({ ...f, username: v }))}
              />
              <ProfileField
                label="Email"
                icon={
                  <FieldIcon>
                    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                  </FieldIcon>
                }
                value={form.email}
                editing={editing}
                onChange={(v) => setForm((f) => ({ ...f, email: v }))}
              />
              <ProfileField
                label="Phone Number"
                icon={
                  <FieldIcon>
                    <svg fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                  </FieldIcon>
                }
                value={user.phoneNumber || ""}
                editing={false}
                verified
              />
            </div>

            {/* Account status */}
            <div className="mt-6 pt-6 border-t border-slate-100 flex items-center gap-3">
              <span className="text-sm font-medium text-slate-700">Account Status:</span>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                {user.status || "active"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProfileField({
  label,
  icon,
  value,
  editing,
  onChange,
  verified,
}: {
  label: string;
  icon: React.ReactNode;
  value: string;
  editing: boolean;
  onChange?: (v: string) => void;
  verified?: boolean;
}) {
  return (
    <div>
      <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-1.5">
        {icon}
        {label}
        {verified && (
          <svg className="w-4 h-4 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        )}
      </label>
      {editing && onChange ? (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#c04a00]/30 focus:border-[#c04a00]"
        />
      ) : (
        <div className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-slate-400 bg-slate-50/50">
          {value || "—"}
        </div>
      )}
    </div>
  );
}
