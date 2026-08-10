"use client";

import React, { useEffect, useRef } from "react";

const SUGGESTIONS = [
  "Which vendor is best value?",
  "Where is the cheapest vendor lower?",
  "Which categories are above market?",
  "What should I negotiate?",
];

type Message = { role: string; content: string };

type Props = {
  sessionId: string;
  chatHistory: Message[];
  chatInput: string;
  isChatting: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  onSuggestion?: (text: string) => void;
};

export default function CompareChat({
  sessionId,
  chatHistory,
  chatInput,
  isChatting,
  onInputChange,
  onSubmit,
  onSuggestion,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, isChatting]);

  if (!sessionId) return null;

  return (
    <section className="qs-card overflow-hidden">
      <div className="px-5 py-4 border-b border-stone-100 bg-[var(--ai-soft)]/40">
        <p className="qs-eyebrow !text-[var(--ai)]">Ask QuoteSense</p>
        <h2 className="qs-section-title mt-1">Questions about this comparison</h2>
        <p className="qs-section-sub">
          Answers are based on the quotes and matrix in the current session.
        </p>
      </div>

      <div className="px-5 pt-4 flex flex-wrap gap-2">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            type="button"
            disabled={isChatting}
            onClick={() => onSuggestion?.(text)}
            className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-600 hover:border-[var(--ai-border)] hover:text-[var(--ai)] transition-colors duration-150 disabled:opacity-50"
          >
            {text}
          </button>
        ))}
      </div>

      <div className="px-5 py-4 max-h-80 overflow-y-auto space-y-3">
        {chatHistory.length === 0 ? (
          <p className="text-sm text-stone-500 py-6 text-center">
            No messages yet. Ask about totals, categories, or negotiation focus.
          </p>
        ) : (
          chatHistory.map((msg, i) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={i}
                className={`flex ${isUser ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                    isUser
                      ? "bg-[var(--accent)] text-white"
                      : "bg-stone-100 text-stone-800"
                  }`}
                >
                  {!isUser && (
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--ai)] mb-1">
                      QuoteSense
                    </p>
                  )}
                  {msg.content}
                </div>
              </div>
            );
          })
        )}
        {isChatting && (
          <p className="text-xs text-stone-400">Analyzing this comparison…</p>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="border-t border-stone-100 p-4 flex gap-2"
      >
        <label className="flex-1 min-w-0">
          <span className="sr-only">Ask about this comparison</span>
          <input
            value={chatInput}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder="Ask about these vendor quotes…"
            disabled={isChatting}
            className="qs-input"
          />
        </label>
        <button
          type="submit"
          disabled={isChatting || !chatInput.trim()}
          className="qs-btn qs-btn-primary shrink-0"
        >
          Send
        </button>
      </form>
    </section>
  );
}
