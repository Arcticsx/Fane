import React, { useState, useEffect, useRef } from 'react';
import { api, getImageUrl } from '../api';
import { useNavigate } from 'react-router-dom';

export default function ChronicleSelector() {
  const [chronicles, setChronicles] = useState([]);
  const [personalities, setPersonalities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [showSearchMenu, setShowSearchMenu] = useState(false);
  const searchRef = useRef(null);
  const [editingChronicle, setEditingChronicle] = useState(null);
  const [selectedChronicle, setSelectedChronicle] = useState(null);
  const [processStatus, setProcessStatus] = useState(null);
  const [processLoading, setProcessLoading] = useState(false);
  const [editForm, setEditForm] = useState({ title: '', description: '', synopsis: '' });
  const [editSaving, setEditSaving] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadChronicles();
    loadPersonalities();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowSearchMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      if (editingChronicle) {
        setEditingChronicle(null);
        setEditForm({ title: '', description: '', synopsis: '' });
      }
      if (selectedChronicle) {
        setSelectedChronicle(null);
        setProcessStatus(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [editingChronicle, selectedChronicle]);

  const loadChronicles = async () => {
    setLoading(true);
    try {
      const rows = await api.listChronicles();
      setChronicles(rows || []);
    } catch (err) {
      console.error('Failed to load chronicles', err);
      setChronicles([]);
    } finally {
      setLoading(false);
    }
  };

  const loadPersonalities = async () => {
    try {
      const rows = await api.getPersonalities();
      setPersonalities(Object.values(rows || {}));
    } catch (err) {
      console.error('Failed to load personalities', err);
      setPersonalities([]);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!confirm('Delete this chronicle? This cannot be undone.')) return;
    try {
      await api.deleteChronicle(id);
      setChronicles((prev) => prev.filter((chronicle) => chronicle.id !== id));
    } catch (err) {
      console.error('Delete failed', err);
      alert('Delete failed: ' + (err.message || err));
    }
  };

  const handleEdit = (e, chronicle) => {
    e.stopPropagation();
    setEditingChronicle(chronicle);
    setEditForm({
      title: chronicle.title || '',
      description: chronicle.synopsis || '',
      synopsis: chronicle.synopsis || '',
    });
  };

  const handleEditSave = async (e) => {
    e.preventDefault();
    if (!editingChronicle) return;

    setEditSaving(true);
    try {
      const updated = await api.updateChronicle(editingChronicle.id, {
        title: editForm.title,
        synopsis: editForm.synopsis || editForm.description,
      });
      setChronicles((prev) => prev.map((item) => (item.id === editingChronicle.id ? { ...item, ...updated } : item)));
      setEditingChronicle(null);
      setEditForm({ title: '', description: '', synopsis: '' });
    } catch (err) {
      console.error('Edit failed', err);
      alert('Edit failed: ' + (err.message || err));
    } finally {
      setEditSaving(false);
    }
  };

  useEffect(() => {
    if (!selectedChronicle?.id) {
      setProcessStatus(null);
      setProcessLoading(false);
      return;
    }

    let cancelled = false;
    const loadProcessStatus = async () => {
      try {
        setProcessLoading(true);
        const data = await api.getChronicleProcessStatus(selectedChronicle.id);
        if (!cancelled) {
          setProcessStatus(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load process status', err);
          setProcessStatus(null);
        }
      } finally {
        if (!cancelled) {
          setProcessLoading(false);
        }
      }
    };

    loadProcessStatus();
    const interval = window.setInterval(loadProcessStatus, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedChronicle?.id]);

  const formatChronicleDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  };

  const normalizeStatusValue = (value) => String(value ?? '').toLowerCase().replace(/[_\s-]+/g, ' ').trim();

  const activePhase = processStatus?.phases?.find((phase) => phase.status !== 'completed') || processStatus?.phases?.[0] || null;
  const activeStep = activePhase?.steps?.find((step) => step.status !== 'completed') || activePhase?.steps?.[0] || null;
  const hasProcessData = Array.isArray(processStatus?.phases) && processStatus.phases.length > 0;
  const completedSteps = activePhase?.steps?.filter((step) => step.status === 'completed').length || 0;
  const totalSteps = activePhase?.steps?.length || 0;
  const progressPercent = hasProcessData && totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
  const setupStatus = normalizeStatusValue(selectedChronicle?.setup_status);
  const phaseStatus = normalizeStatusValue(activePhase?.status);
  const stepStatus = normalizeStatusValue(activeStep?.status);
  const activeStatusValues = ['processing', 'in progress', 'started', 'queued'];
  const isProcessing = Boolean(
    selectedChronicle && (
      activeStatusValues.includes(setupStatus) ||
      activeStatusValues.includes(phaseStatus) ||
      activeStatusValues.includes(stepStatus)
    )
  );
  const statusSummary = isProcessing
    ? (activePhase?.phase || activePhase?.status || 'Preparing your chronicle')
    : (setupStatus === 'not started' || phaseStatus === 'pending' || setupStatus === 'pending'
        ? 'Waiting to start'
        : (selectedChronicle?.setup_status || 'Ready'));
  const statusDetail = isProcessing
    ? 'We are currently setting up your chronicle.'
    : 'This chronicle is waiting to begin setup.';
  const stepSummary = activeStep && hasProcessData
    ? (activeStep.step || activeStep.status || 'Working through setup')
    : 'Waiting for the next step to begin';

  const searchTerm = search.trim().toLowerCase();

  const filtered = chronicles.filter((chronicle) => {
    const q = searchTerm;
    return (
      chronicle.title?.toLowerCase().includes(q) ||
      (chronicle.genre || '').toLowerCase().includes(q) ||
      (chronicle.synopsis || '').toLowerCase().includes(q) ||
      (chronicle.setup_status || '').toLowerCase().includes(q) ||
      String(chronicle.id).toLowerCase().includes(q)
    );
  });

  const filteredPersonalities = personalities.filter((persona) => {
    const q = searchTerm;
    return (
      (persona.name || '').toLowerCase().includes(q) ||
      (persona.description || '').toLowerCase().includes(q) ||
      (persona.key || '').toLowerCase().includes(q)
    );
  });

  const searchResults = searchTerm
    ? [
        ...filtered.map((chronicle) => ({
          type: 'chronicle',
          id: chronicle.id,
          title: chronicle.title || 'Untitled Chronicle',
          detail: chronicle.synopsis || chronicle.setup_status || 'Chronicle',
          item: chronicle,
        })),
        ...filteredPersonalities.slice(0, 4).map((persona) => ({
          type: 'persona',
          id: persona.key,
          title: persona.name || 'Untitled Persona',
          detail: persona.description || 'Persona',
          item: persona,
        })),
      ].slice(0, 8)
    : [];

  const openChronicle = (chronicle) => {
    setSelectedChronicle(chronicle);
    setProcessStatus(null);
  };

  return (
    <main className="flex h-full flex-col overflow-hidden px-6 pb-6 pt-0 text-text">
        <header className="flex flex-wrap items-center justify-between gap-4 py-5">
          <div ref={searchRef} className="group relative max-w-xl flex-1">
            <div className="flex items-center rounded-full border border-border/60 bg-surface/70 px-3 text-sm text-text transition focus-within:border-accent">
              <span className="material-symbols-outlined px-3 text-muted transition group-focus-within:text-accent">search</span>
              <input
                type="text"
                placeholder="Search chronicles and personas…"
                value={search}
                onFocus={() => setShowSearchMenu(true)}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setShowSearchMenu(true);
                }}
                className="w-full bg-transparent px-4 py-2.5 text-sm text-text outline-none placeholder:text-muted"
              />
            </div>

            {showSearchMenu && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-20 rounded-2xl border border-border/60 bg-surface/95 p-2 shadow-2xl shadow-surface/50 backdrop-blur-xl">
                {searchResults.map((result) => (
                  <button
                    key={`${result.type}-${result.id}`}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      if (result.type === 'chronicle') {
                        navigate(`/chronicle/${encodeURIComponent(result.item.id)}`);
                      } else {
                        navigate('/');
                      }
                      setSearch('');
                      setShowSearchMenu(false);
                    }}
                    className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-accent/10"
                  >
                    <div>
                      <p className="text-sm font-semibold text-text">{result.title}</p>
                      <p className="mt-0.5 text-xs text-muted">{result.detail}</p>
                    </div>
                    <span className="rounded-full border border-accent/25 bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-accent">
                      {result.type}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => navigate('/chronicle')}
            className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-text transition hover:-translate-y-0.5"
          >
            + Create Chronicle
          </button>
        </header>

        {editingChronicle && (
          <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-bg/70 p-4">
            <div className="w-full max-w-md rounded-3xl border border-border/60 bg-surface/90 p-6 shadow-2xl shadow-surface/40 backdrop-blur-xl">
              <h3 className="text-xl font-semibold text-text">Edit Chronicle</h3>
              <form onSubmit={handleEditSave} className="mt-4 space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Title</label>
                  <input
                    value={editForm.title}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                    className="w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Description</label>
                  <textarea
                    value={editForm.description}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value, synopsis: e.target.value }))}
                    rows={3}
                    className="min-h-[90px] w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted">Synopsis</label>
                  <textarea
                    value={editForm.synopsis}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, synopsis: e.target.value }))}
                    rows={3}
                    className="min-h-[100px] w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingChronicle(null);
                      setEditForm({ title: '', description: '', synopsis: '' });
                    }}
                    className="rounded-lg bg-surface/80 px-3 py-2 text-sm text-text"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={editSaving}
                    className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-text"
                  >
                    {editSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <section className="flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="py-20 text-center text-muted">Loading chronicles…</div>
          ) : filtered.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-surface/80 px-6 py-16 text-center text-muted">
              No chronicles yet. Create one to get started.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map((chronicle) => (
                <div key={chronicle.id} className="flex flex-col gap-3">
                  <div
                    className="group relative flex cursor-pointer items-center gap-4 rounded-2xl border border-border/60 bg-surface/70 p-4 shadow-lg shadow-surface/20 transition hover:-translate-y-1 hover:border-accent/40 h-32 overflow-hidden"
                    onClick={() => openChronicle(chronicle)}
                  >
                    <div className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-gradient-to-br from-accent2 to-accent">
                      {chronicle.avatar ? (
                        <img src={getImageUrl(chronicle.avatar)} alt={chronicle.title} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-2xl font-semibold text-text">
                          {chronicle.title?.charAt(0) || 'C'}
                        </div>
                      )}
                    </div>

                    <div className="flex h-24 flex-1 flex-col justify-between overflow-hidden">
                      <div className="min-h-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="truncate text-base font-semibold text-text">{chronicle.title}</h3>
                          <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-accent">
                            {chronicle.setup_status || 'ready'}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-muted line-clamp-2 break-words">{chronicle.synopsis || 'No description available.'}</p>
                      </div>

                      <div className="flex items-center justify-between text-xs text-muted">
                        <span>{formatChronicleDate(chronicle.created_at)}</span>
                        <div className="flex gap-2 opacity-0 transition group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(e) => handleEdit(e, chronicle)}
                            className="rounded-lg bg-surface/80 p-2 text-text hover:bg-accent/15 hover:text-accent"
                            title="Edit"
                          >
                            <span className="material-symbols-outlined text-base">edit</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDelete(e, chronicle.id)}
                            className="rounded-lg bg-surface/80 p-2 text-text hover:bg-accent2/15 hover:text-accent2"
                            title="Delete"
                          >
                            <span className="material-symbols-outlined text-base">delete</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                </div>
              ))}
            </div>
          )}
        </section>

        {selectedChronicle && (
          <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-bg/70 p-4 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-3xl border border-border/60 bg-surface/95 p-6 shadow-2xl shadow-surface/40">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.26em] text-accent">Chronicle</p>
                  <h3 className="mt-1 text-2xl font-semibold text-text">{selectedChronicle.title || 'Untitled Chronicle'}</h3>
                  <p className="mt-2 text-sm text-muted">{selectedChronicle.synopsis || 'No description available.'}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedChronicle(null);
                    setProcessStatus(null);
                  }}
                  className="rounded-full bg-surface/80 px-3 py-1.5 text-sm text-muted"
                >
                  Close
                </button>
              </div>

              <div className="mt-6 rounded-2xl border border-border/60 bg-surface/80 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Status</p>
                    <p className="mt-1 text-sm font-medium text-text">{statusSummary}</p>
                    <p className="mt-1 text-xs text-muted">{statusDetail}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate(`/chronicle/${encodeURIComponent(selectedChronicle.id)}`)}
                    disabled={isProcessing}
                    className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-text transition disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isProcessing ? 'Processing…' : 'Start Chronicle'}
                  </button>
                </div>

                <div className="mt-4 rounded-xl border border-border/40 bg-surface/70 p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-text">Progress</span>
                    <span className="text-accent">{isProcessing ? `${progressPercent}%` : '100%'}</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface/80">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent to-accent2 transition-all"
                      style={{ width: `${isProcessing ? progressPercent : 100}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    {isProcessing ? `${completedSteps}/${totalSteps} steps completed` : 'All setup steps completed'}
                  </p>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="rounded-xl border border-border/40 bg-surface/70 p-3">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Current phase</p>
                    <p className="mt-1 text-sm font-medium text-text">
                      {activePhase ? activePhase.phase || activePhase.status : 'Waiting for status...'}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {activePhase ? activePhase.status : 'No phase data yet'}
                    </p>
                  </div>

                  <div className="rounded-xl border border-border/40 bg-surface/70 p-3">
                    <p className="text-xs uppercase tracking-[0.2em] text-muted">Current step</p>
                    <p className="mt-1 text-sm font-medium text-text">{stepSummary}</p>
                    <p className="mt-1 text-xs text-muted">
                      {activeStep ? activeStep.status : 'No step data yet'}
                    </p>
                  </div>
                </div>

                {processLoading && (
                  <p className="mt-4 text-sm text-muted">Loading processing details…</p>
                )}
              </div>
            </div>
          </div>
        )}
    </main>
  );
}
