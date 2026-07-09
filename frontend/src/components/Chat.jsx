import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, getImageUrl } from '../api';
import { ArrowUpIcon, PlusIcon } from 'lucide-react';

function Chat({ persona: propPersona, session: propSession, onBack }) {
  const { personaKey, sessionId: routeSessionId } = useParams();
  const navigate = useNavigate();
  const [persona, setPersona] = useState(propPersona);
  const [loadingPersona, setLoadingPersona] = useState(!propPersona);
  const [messages, setMessages] = useState([]);
  const [context, setContext] = useState([]);
  const [sessionId, setSessionId] = useState(propSession?.id || routeSessionId || null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Load persona from API if not provided (refresh case)
  useEffect(() => {
    if (propPersona) {
      setPersona(propPersona);
      setLoadingPersona(false);
      return;
    }
    if (!personaKey) {
      setLoadingPersona(false);
      return;
    }
    setLoadingPersona(true);
    api.getPersonalities()
      .then(data => {
        const found = data[personaKey];
        if (found) {
          setPersona(found);
        } else {
          alert('Personality not found');
        }
      })
      .catch(err => {
        console.error('Failed to load personality:', err);
        alert('Failed to load personality');
      })
      .finally(() => setLoadingPersona(false));
  }, [propPersona, personaKey]);

  const activeSession = propSession || (routeSessionId ? { id: parseInt(routeSessionId), persona_key: persona?.key } : null);
  const activeSessionId = activeSession?.id ?? null;

  // Load session when persona and session are ready
  useEffect(() => {
    if (!persona?.key) return;
    let cancelled = false;
    setInitializing(true);
    setMessages([]);
    setContext([]);

    api.loadSession(persona.key, activeSession)
      .then(data => {
        if (cancelled) return;
        setMessages(data.messages || []);
        setContext(data.context || []);
        setSessionId(activeSession?.id ?? null);
      })
      .catch(error => {
        if (cancelled) return;
        console.error('Failed to load session:', error);
        alert('Failed to load chat session');
      })
      .finally(() => {
        if (!cancelled) setInitializing(false);
      });

    return () => { cancelled = true; };
  }, [persona?.key, activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const userInput = input.trim();
    setInput('');
    setLoading(true);

    const optimisticMessages = [...messages, { role: 'user', content: userInput }];
    setMessages(optimisticMessages);

    try {
      const data = await api.sendMessage(persona.key, messages, context, sessionId, userInput);
      setMessages(data.messages);
      setContext(data.context);

      // Auto-save after each message
      await api.saveSession(persona.key, data.messages, data.context, sessionId)
        .then(saveData => setSessionId(saveData.session_id))
        .catch(err => console.warn('Auto-save failed:', err));

    } catch (error) {
      console.error('Failed to send message:', error);
      alert('Failed to send message');
    }

    setLoading(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    const textarea = e.target;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
    }
  };

  const handleNewChat = () => {
    // Start a fresh chat with the same persona – navigate to chat without session id
    navigate(`/chat/${persona.key}`, { state: { persona } });
  };

  if (loadingPersona) {
    return (
      <div className="flex min-h-screen items-center justify-center text-text">
        <p className="text-muted">Loading personality…</p>
      </div>
    );
  }

  if (!persona) {
    return (
      <div className="flex min-h-screen items-center justify-center text-text">
        <p className="text-muted">Personality not found.</p>
      </div>
    );
  }

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center text-text">
        <p className="text-muted">Loading chat...</p>
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
        {/* Redesigned Header */}
        <div className="mb-4 flex items-center justify-between rounded-2xl border border-border/60 bg-surface/70 px-4 py-3 shadow-lg shadow-surface/20">
          <div className="flex items-center gap-3">
            {/* Avatar */}
            <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-accent2 to-accent">
              {persona.avatar ? (
                <img
                  src={getImageUrl(persona.avatar)}
                  alt={persona.name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-text">
                  {persona.name.charAt(0)}
                </div>
              )}
            </div>
            <div>
              <div className="text-base font-semibold text-text">{persona.name}</div>
              <div className="text-xs text-muted">
                {sessionId ? `Session #${sessionId}` : 'New Chat'}
              </div>
            </div>
          </div>

          {/* Right side: New Chat button + Back button */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1 rounded-full bg-accent/20 px-3 py-1.5 text-sm font-medium text-accent transition hover:bg-accent/30 hover:text-text"
              title="Start a new chat with this persona"
            >
              <PlusIcon size={16} />
              <span className="hidden sm:inline">New</span>
            </button>
            <button
              onClick={onBack}
              className="rounded-full bg-surface/80 px-3 py-1.5 text-sm text-muted transition hover:bg-surface/70 hover:text-text"
            >
              ← Back
            </button>
          </div>
        </div>

        {/* Messages area */}
        <div className="scrollbar-themed mb-4 flex-1 overflow-y-auto rounded-2xl border border-border/50 bg-surface/60 p-4 shadow-inner shadow-surface/20">
          <div className="flex flex-col gap-4">
            {messages.map((msg, index) => {
              if (msg.role === 'system') return null;
              const isUser = msg.role === 'user';
              const roleLabel = isUser ? 'You' : persona.name;

              return (
                <div key={index} className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-7 ${isUser ? 'ml-auto bg-accent/15 text-text' : 'bg-surface/80 text-text'}`}>
                  <div className={`mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${isUser ? 'text-accent' : 'text-muted'}`}>{roleLabel}</div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              );
            })}

            {loading && (
              <div className="max-w-[80%] rounded-2xl bg-surface/80 px-4 py-3 text-sm leading-7 text-text">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">{persona.name}</div>
                <div className="animate-pulse text-muted">…</div>
              </div>
            )}
          </div>
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSendMessage} className="flex items-end gap-2 rounded-2xl border border-border/40 bg-surface/70 p-3 shadow-lg shadow-surface/20">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Type your message… (Shift+Enter for new line)"
            disabled={loading}
            autoFocus
            className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-text outline-none placeholder:text-muted overflow-y-auto"
          />
          <button
            type={loading ? 'button' : 'submit'}
            disabled={loading || !input.trim()}
            className="shrink-0 rounded-full border border-border/40 p-1.5 text-text transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-label="Stop"
              >
                <title>Stop</title>
                <rect x="6" y="6" width="12" height="12" />
              </svg>
            ) : (
              <ArrowUpIcon size={20} />
            )}
          </button>
        </form>
      </div>
    </>
  );
}

export default Chat;