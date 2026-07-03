import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import ConfirmModal from './ConfirmModal.jsx';

function SessionSelector({ persona, onSessionSelected, onBack }) {
  const { personaKey } = useParams();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState(null);

  useEffect(() => {
    if (!persona?.key) return;
    loadSessions();
  }, [persona, personaKey]);

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await api.getSessions(persona.key);
      setSessions(data.sessions || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
      alert('Failed to load sessions');
    }
    setLoading(false);
  };

  const handleSelectSession = (session) => onSessionSelected(session);
  const handleNewSession = () => {
    // Start fresh chat – navigate directly to chat without session
    navigate(`/chat/${persona.key}`, { state: { persona } });
  };

  const handleDeleteSession = (e, session) => {
    e.stopPropagation();
    setConfirmTarget(session);
    setConfirmOpen(true);
  };

  const doDeleteConfirmed = async () => {
    if (!confirmTarget) return;
    setConfirmOpen(false);
    try {
      await api.deleteSession(persona.key, confirmTarget.id);
      await loadSessions();
    } catch (error) {
      console.error('Failed to delete session:', error);
      alert('Failed to delete session');
    }
    setConfirmTarget(null);
  };

  const getDateGroup = (dateStr) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return 'Older';
  };

  const filteredSessions = sessions.filter((session) => {
    const q = searchQuery.toLowerCase();
    return (
      session.id.toString().includes(q) ||
      session.preview.toLowerCase().includes(q) ||
      new Date(session.updated_at).toLocaleString().toLowerCase().includes(q)
    );
  });

  const grouped = filteredSessions.reduce((acc, session) => {
    const group = getDateGroup(session.updated_at || session.created_at);
    if (!acc[group]) acc[group] = [];
    acc[group].push(session);
    return acc;
  }, {});

  const sortedGroups = ['Today', 'Yesterday', 'Older'].filter((g) => grouped[g]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden px-6 py-6 text-text">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-text flex items-center gap-2">
          <span className="material-symbols-outlined text-3xl text-accent">chat</span>
          Sessions
          <span className="ml-2 text-sm font-normal text-muted">({sessions.length})</span>
        </h1>
        <div className="flex items-center gap-3 flex-1 max-w-sm">
          {/* ─── Resized search bar ─── */}
          <div className="group flex flex-1 items-center rounded-full border border-border/60 bg-surface/70 px-3 text-sm text-text transition focus-within:border-accent">
            <span className="material-symbols-outlined px-2 text-muted transition group-focus-within:text-accent">search</span>
            <input
              type="text"
              placeholder="Search sessions…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent px-4 py-2.5 text-sm text-text outline-none placeholder:text-muted"
            />
          </div>

          <button
            className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-accent to-accent2 px-4 py-2 text-sm font-semibold text-text shadow-lg shadow-accent/20 transition hover:-translate-y-0.5"
            onClick={handleNewSession}
          >
            <span className="material-symbols-outlined text-base">add</span>
            New Chat
          </button>
        </div>
      </header>

      {loading && <p className="py-4 text-center text-muted">Loading sessions…</p>}

      <div className="flex-1 overflow-y-auto pr-1">
        {sortedGroups.length === 0 && !loading && (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-border/60 bg-gradient-to-b from-surface/40 to-transparent px-6 py-16 text-center">
            <span className="material-symbols-outlined text-6xl text-muted/50">chat</span>
            <h2 className="mt-4 text-2xl font-semibold text-text">No sessions yet</h2>
            <p className="mt-2 max-w-sm text-sm text-muted">
              Start your first chat with <strong>{persona.name}</strong>
            </p>
            <button
              className="mt-6 flex items-center gap-2 rounded-full bg-gradient-to-r from-accent to-accent2 px-6 py-3 text-sm font-semibold text-text shadow-lg shadow-accent/30 transition hover:scale-105"
              onClick={handleNewSession}
            >
              <span className="material-symbols-outlined text-base">add</span>
              Start New Chat
            </button>
          </div>
        )}

        {sortedGroups.map((groupName) => (
          <div key={groupName} className="mb-6">
            <div className="mb-3 flex items-center gap-2 border-b border-border/60 pb-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted">{groupName}</span>
              <span className="text-xs text-muted">({grouped[groupName].length})</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {grouped[groupName].map((session) => (
                <div
                  key={session.id}
                  className="group relative cursor-pointer rounded-2xl border border-border/60 bg-surface/70 p-4 shadow-lg shadow-surface/20 transition-all hover:-translate-y-1 hover:border-accent/40 hover:shadow-accent/10 hover:shadow-xl"
                  onClick={() => handleSelectSession(session)}
                >
                  {/* Gradient border accent on hover */}
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-accent/20 to-accent2/20 opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none" />
                  
                  <div className="relative flex flex-col h-full">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-xl text-accent">history</span>
                        <span className="font-medium text-text">Session #{session.id}</span>
                      </div>
                      <button
                        className="rounded-lg p-1 text-muted transition hover:bg-accent/10 hover:text-accent"
                        onClick={(e) => handleDeleteSession(e, session)}
                        title="Delete session"
                      >
                        <span className="material-symbols-outlined text-base">delete</span>
                      </button>
                    </div>
                    <div className="mt-2 flex-1">
                      <p className="text-sm text-muted line-clamp-2 break-words">
                        {session.preview}
                      </p>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-muted">
                      <span>{new Date(session.updated_at).toLocaleString()}</span>
                      <span className="flex items-center gap-0.5 text-accent opacity-0 transition group-hover:opacity-100">
                        Open
                        <span className="material-symbols-outlined text-sm">arrow_forward</span>
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <ConfirmModal
        open={confirmOpen}
        title="Delete Session"
        message={confirmTarget ? `Delete session #${confirmTarget.id}? This cannot be undone.` : ''}
        onConfirm={doDeleteConfirmed}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

export default SessionSelector;