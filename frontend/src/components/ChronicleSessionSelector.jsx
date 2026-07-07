import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import ConfirmModal from './ConfirmModal.jsx';

export default function ChronicleSessionSelector() {
  const [chronicles, setChronicles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadChronicles();
  }, []);

  const loadChronicles = async () => {
    setLoading(true);
    try {
      const data = await api.listChronicles();
      setChronicles(data || []);
    } catch (error) {
      console.error('Failed to load chronicles:', error);
      setChronicles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectChronicle = (chronicle) => {
    navigate(`/chronicle/${encodeURIComponent(chronicle.id)}`);
  };

  const handleNewChronicle = () => {
    navigate('/chronicle');
  };

  const handleDeleteChronicle = (e, chronicle) => {
    e.stopPropagation();
    setConfirmTarget(chronicle);
    setConfirmOpen(true);
  };

  const doDeleteConfirmed = async () => {
    if (!confirmTarget) return;
    setConfirmOpen(false);
    try {
      await api.deleteChronicle(confirmTarget.id);
      await loadChronicles();
    } catch (error) {
      console.error('Failed to delete chronicle:', error);
      alert('Failed to delete chronicle');
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

  const filteredChronicles = chronicles.filter((chronicle) => {
    const q = searchQuery.toLowerCase();
    return (
      chronicle.title?.toLowerCase().includes(q) ||
      chronicle.setup_status?.toLowerCase().includes(q) ||
      chronicle.id?.toLowerCase().includes(q)
    );
  });

  const grouped = filteredChronicles.reduce((acc, chronicle) => {
    const group = getDateGroup(chronicle.created_at || '');
    if (!acc[group]) acc[group] = [];
    acc[group].push(chronicle);
    return acc;
  }, {});

  const sortedGroups = ['Today', 'Yesterday', 'Older'].filter((g) => grouped[g]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden px-6 py-6 text-text">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-text flex items-center gap-2">
          <span className="material-symbols-outlined text-3xl text-accent">book</span>
          Chronicles
          <span className="ml-2 text-sm font-normal text-muted">({chronicles.length})</span>
        </h1>
        <div className="flex items-center gap-3 flex-1 max-w-sm">
          <div className="group flex flex-1 items-center rounded-full border border-border/60 bg-surface/70 px-3 text-sm text-text transition focus-within:border-accent">
            <span className="material-symbols-outlined px-2 text-muted transition group-focus-within:text-accent">search</span>
            <input
              type="text"
              placeholder="Search chronicles…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent px-4 py-2.5 text-sm text-text outline-none placeholder:text-muted"
            />
          </div>

          <button
            className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-accent to-accent2 px-4 py-2 text-sm font-semibold text-text shadow-lg shadow-accent/20 transition hover:-translate-y-0.5"
            onClick={handleNewChronicle}
          >
            <span className="material-symbols-outlined text-base">add</span>
            New Chronicle
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto pr-1">
        {loading && <p className="py-4 text-center text-muted">Loading chronicles…</p>}

        {!loading && filteredChronicles.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-border/60 bg-gradient-to-b from-surface/40 to-transparent px-6 py-16 text-center">
            <span className="material-symbols-outlined text-6xl text-muted/50">book</span>
            <h2 className="mt-4 text-2xl font-semibold text-text">No chronicles yet</h2>
            <p className="mt-2 max-w-sm text-sm text-muted">Create a chronicle and upload a PDF to start chat-based roleplay.</p>
            <button
              className="mt-6 flex items-center gap-2 rounded-full bg-gradient-to-r from-accent to-accent2 px-6 py-3 text-sm font-semibold text-text shadow-lg shadow-accent/30 transition hover:scale-105"
              onClick={handleNewChronicle}
            >
              <span className="material-symbols-outlined text-base">add</span>
              Create Chronicle
            </button>
          </div>
        )}

        {!loading && filteredChronicles.length > 0 && (
          <div className="space-y-6">
            {sortedGroups.map((groupName) => (
              <div key={groupName}>
                <div className="mb-3 flex items-center gap-2 border-b border-border/60 pb-2">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted">{groupName}</span>
                  <span className="text-xs text-muted">({grouped[groupName].length})</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {grouped[groupName].map((chronicle) => (
                    <div
                      key={chronicle.id}
                      className="group relative cursor-pointer rounded-2xl border border-border/60 bg-surface/70 p-4 shadow-lg transition-all hover:-translate-y-1 hover:border-accent/40 hover:shadow-xl"
                      onClick={() => handleSelectChronicle(chronicle)}
                    >
                      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-accent/10 to-transparent opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none" />
                      <div className="relative flex flex-col h-full">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <h3 className="text-base font-semibold text-text truncate">{chronicle.title}</h3>
                            <p className="mt-1 text-sm text-muted line-clamp-2">{chronicle.setup_status || 'No status'}</p>
                          </div>
                          <button
                            className="rounded-lg p-1 text-muted transition hover:bg-accent/10 hover:text-accent"
                            onClick={(e) => handleDeleteChronicle(e, chronicle)}
                            title="Delete chronicle"
                          >
                            <span className="material-symbols-outlined text-base">delete</span>
                          </button>
                        </div>

                        <div className="mt-4 flex items-center justify-between text-xs text-muted">
                          <span>{new Date(chronicle.created_at).toLocaleString()}</span>
                          <span className="flex items-center gap-1 text-accent opacity-0 transition group-hover:opacity-100">
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
        )}
      </div>

      <ConfirmModal
        open={confirmOpen}
        title="Delete Chronicle"
        message={confirmTarget ? `Delete chronicle '${confirmTarget.title}'? This cannot be undone.` : ''}
        onConfirm={doDeleteConfirmed}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
