"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, Send, X, Loader2, Search, BookOpen, Sparkles } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface Source {
  slug: string;
  score: number;
  snippet: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  status?: string;
  stage?: "searching" | "reading" | "generating" | "done";
}

// Use same-origin rewrite in production, direct in local dev
const API_URL =
  typeof window !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? "/api/backend"
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STAGE_ICONS = {
  searching: Search,
  reading: BookOpen,
  generating: Sparkles,
};

function PipelineStatus({ stage, message }: { stage: string; message: string }) {
  const Icon = STAGE_ICONS[stage as keyof typeof STAGE_ICONS] || Loader2;
  const stages = ["searching", "reading", "generating"];
  const currentIdx = stages.indexOf(stage);

  return (
    <div className="space-y-2">
      {/* Progress dots */}
      <div className="flex items-center gap-1.5">
        {stages.map((s, i) => (
          <div key={s} className="flex items-center gap-1.5">
            <div
              className={`h-1.5 w-1.5 rounded-full transition-colors ${
                i < currentIdx
                  ? "bg-green-500"
                  : i === currentIdx
                  ? "bg-blue-500 animate-pulse"
                  : "bg-slate-200"
              }`}
            />
            {i < stages.length - 1 && (
              <div className={`h-px w-3 ${i < currentIdx ? "bg-green-300" : "bg-slate-200"}`} />
            )}
          </div>
        ))}
      </div>
      {/* Current status */}
      <div className="flex items-center gap-1.5 text-xs text-slate-500">
        <Icon className="h-3 w-3 animate-pulse" />
        <span>{message}</span>
      </div>
    </div>
  );
}

function SourceCards({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;

  return (
    <div className="mt-2 border-t border-slate-200 pt-2">
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-1.5">
        Sources used
      </p>
      <div className="space-y-1">
        {sources.map((src, i) => (
          <a
            key={i}
            href={`/docs/${src.slug}`}
            className="flex items-start gap-2 rounded border border-slate-100 bg-slate-50 px-2 py-1.5 text-xs no-underline hover:border-slate-300 hover:bg-slate-100 transition-colors"
          >
            <BookOpen className="h-3 w-3 mt-0.5 shrink-0 text-slate-400" />
            <div className="min-w-0">
              <span className="font-medium text-slate-700">{src.slug}</span>
              <span className="ml-1.5 text-[10px] text-slate-400">
                {Math.round(src.score * 100)}% match
              </span>
              {src.snippet && (
                <p className="text-[10px] text-slate-400 truncate mt-0.5">{src.snippet}</p>
              )}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

export function DocsChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const userMsg: Message = { role: "user", content: trimmed };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setIsStreaming(true);

    // Add assistant placeholder with initial status
    const assistantMsg: Message = {
      role: "assistant",
      content: "",
      sources: [],
      stage: "searching",
      status: "Searching documentation...",
    };
    setMessages([...newMessages, assistantMsg]);

    try {
      const history = newMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await fetch(`${API_URL}/docs/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history }),
      });

      if (!res.ok || !res.body) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: `Connection error (HTTP ${res.status}). Is the backend running?`,
            stage: "done",
          };
          return updated;
        });
        setIsStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === "status") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  stage: event.stage,
                  status: event.message,
                };
                return updated;
              });
            } else if (event.type === "sources") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  sources: event.sources,
                };
                return updated;
              });
            } else if (event.type === "text") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + event.text,
                  stage: "generating",
                  status: undefined,
                };
                return updated;
              });
            } else if (event.type === "error") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: updated[updated.length - 1].content || `Error: ${event.error}`,
                  stage: "done",
                  status: undefined,
                };
                return updated;
              });
            } else if (event.type === "done") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  stage: "done",
                  status: undefined,
                };
                return updated;
              });
            }
          } catch {
            // Skip malformed events
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Connection error. Please check that the backend is running.",
          stage: "done",
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, isStreaming, messages]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage]
  );

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-slate-800 text-white shadow-lg hover:bg-slate-700 transition-colors"
        aria-label="Open documentation chat"
      >
        <MessageSquare className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 flex h-[36rem] w-[28rem] flex-col rounded-lg border border-slate-200 bg-white shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3 rounded-t-lg">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-slate-600" />
          <span className="text-sm font-medium text-slate-700">Docs Assistant</span>
          <span className="text-[10px] text-slate-400 bg-slate-200 rounded px-1.5 py-0.5">RAG</span>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
          aria-label="Close chat"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.length === 0 && (
          <div className="text-center mt-12 space-y-3">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
              <BookOpen className="h-5 w-5 text-slate-400" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Ask anything about Praxis.</p>
              <p className="text-xs text-slate-400 mt-1">
                I&apos;ll search the docs and give you an answer with sources.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-1.5 mt-4">
              {["How does the hot path work?", "What risk controls exist?", "How is PnL calculated?"].map(
                (q) => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); }}
                    className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-500 hover:border-slate-300 hover:bg-slate-50 transition-colors"
                  >
                    {q}
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-slate-800 text-white"
                  : "bg-slate-50 border border-slate-200 text-slate-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <div>
                  {/* Pipeline status indicator */}
                  {msg.stage && msg.stage !== "done" && !msg.content && (
                    <PipelineStatus stage={msg.stage} message={msg.status || ""} />
                  )}

                  {/* Answer content */}
                  {msg.content && (
                    <div className="prose prose-sm prose-slate max-w-none [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_pre]:my-2 [&_code]:text-xs [&_a]:text-blue-600">
                      <MarkdownRenderer content={msg.content} />
                    </div>
                  )}

                  {/* Source cards */}
                  {msg.sources && msg.sources.length > 0 && msg.stage === "done" && (
                    <SourceCards sources={msg.sources} />
                  )}
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 px-3 py-3">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the docs..."
            disabled={isStreaming}
            className="flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-40 transition-colors"
            aria-label="Send message"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
