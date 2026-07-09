import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { PlusIcon } from 'lucide-react';

export default function ChronicleChat({ chronicleId, onBack }) {
  const navigate = useNavigate();
  const [chronicle, setChronicle] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    if (!chronicleId) return;

    setInitializing(true);
    api.getChronicle(chronicleId)
      .then((data) => {
        if (!mounted) return;
        setChronicle(data);
        setMessages(data.messages || []);
      })
      .catch((e) => {
        if (!mounted) return;
        console.error('Failed to load chronicle', e);
      })
      .finally(() => {
        if (mounted) setInitializing(false);
      });

    return () => {
      mounted = false;
    };
  }, [chronicleId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput('');
    setLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: userText }]);

    try {
      const res = await api.chatChronicle(chronicleId, userText);
      if (res?.messages) {
        setMessages(res.messages);
      } else if (res?.response || res?.message) {
        setMessages((prev) => [...prev, { role: 'assistant', content: res.response || res.message }]);
      }
    } catch (err) {
      console.error('Chat failed', err);
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Error: ' + err.message }]);
    } finally {
      setLoading(false);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const handleNewChat = () => {
    setMessages([]);
    setInput('');
  };

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center text-text">
        <p className="text-muted">Loading chronicle chat…</p>
      </div>
    );
  }

  return (
    <>
      <style>{`
        .scrollbar-themed::-webkit-scrollbar {
          width: 6px;
        }
        .scrollbar-themed::-webkit-scrollbar-track {
          background: transparent;
        }
        .scrollbar-themed::-webkit-scrollbar-thumb {
          background: var(--color-accent);
          border-radius: 3px;
        }
        .scrollbar-themed::-webkit-scrollbar-thumb:hover {
          background: var(--color-accent-2);
        }
        .scrollbar-themed {
          scrollbar-width: thin;
          scrollbar-color: var(--color-accent) transparent;
        }
      `}</style>

      <div className="mx-auto flex h-full max-w-5xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <div className="mb-4 flex items-center justify-between rounded-2xl border border-border/60 bg-surface/70 px-4 py-3 shadow-lg shadow-surface/20">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-accent2 to-accent">
              <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-text">C</div>
            </div>
            <div>
              <div className="text-base font-semibold text-text">{chronicle?.title || 'Chronicle Chat'}</div>
              <div className="text-xs text-muted">{chronicleId ? `Chronicle #${chronicleId}` : 'New Chat'}</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (onBack) {
                  onBack();
                } else {
                  navigate('/chronicle/discover');
                }
              }}
              className="rounded-full bg-surface/80 px-3 py-1.5 text-sm text-muted transition hover:bg-surface/70 hover:text-text"
            >
              ← Back
            </button>
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1 rounded-full bg-accent/20 px-3 py-1.5 text-sm font-medium text-accent transition hover:bg-accent/30 hover:text-text"
            >
              <PlusIcon size={16} />
              <span className="hidden sm:inline">New</span>
            </button>
          </div>
        </div>

        <div className="scrollbar-themed mb-4 flex-1 overflow-y-auto rounded-2xl border border-border/50 bg-surface/60 p-4 shadow-inner shadow-surface/20">
          <div className="flex flex-col gap-4">
            {messages.map((msg, index) => {
              if (msg.role === 'system') return null;
              const isUser = msg.role === 'user';
              const roleLabel = isUser ? 'You' : 'Chronicle';

              return (
                <div
                  key={index}
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-7 ${
                    isUser ? 'ml-auto bg-accent/15 text-text' : 'bg-surface/80 text-text'
                  }`}
                >
                  <div className={`mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${isUser ? 'text-accent' : 'text-muted'}`}>
                    {roleLabel}
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              );
            })}

            {loading && (
              <div className="max-w-[80%] rounded-2xl bg-surface/80 px-4 py-3 text-sm leading-7 text-text">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">Chronicle</div>
                <div className="animate-pulse text-muted">…</div>
              </div>
            )}
          </div>
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSend} className="flex items-end gap-2 rounded-2xl border border-border/40 bg-surface/70 p-3">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask the chronicle about the PDF... (Shift+Enter for newline, Enter to send)"
            disabled={loading}
            className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-text outline-none placeholder:text-muted overflow-y-auto"
          />
          <button type="submit" disabled={loading || !input.trim()} className="shrink-0 rounded-full border border-border/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-text transition hover:bg-accent/20 disabled:opacity-50">
            {loading ? '...' : 'Send'}
          </button>
        </form>
      </div>
    </>
  );
}
