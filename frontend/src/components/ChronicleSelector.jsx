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

  const genreIcons = {
    'Drama': 'theater_comedy', 'Slice of Life': 'home', 'LGBTQ': 'favorite',
    'Fantasy': 'auto_awesome', 'Sci-Fi': 'rocket', 'Horror': 'skull',
    'Romance': 'favorite', 'Adventure': 'explore', 'Mystery': 'search',
    'Thriller': 'bolt', 'Action': 'sprint', 'Historical': 'history',
    'Cyberpunk': 'memory', 'Mythic': 'temple', 'Western': 'flag',
  };
  const selectedGenres = selectedChronicle?.genre
    ? selectedChronicle.genre.split(/[,|]/g).map(g => g.trim()).filter(Boolean)
    : [];

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
          <div className="absolute inset-0 bg-gradient-to-br from-bg to-bg z-0 pointer-events-none" />
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-accent/5 rounded-full blur-[100px] z-0 pointer-events-none" />
          <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-accent2/5 rounded-full blur-[120px] z-0 pointer-events-none" />

          <div className="glass-panel neon-glow relative z-10 w-full max-w-3xl rounded-[24px] overflow-hidden flex flex-col">
            
            <div className="flex flex-col md:flex-row p-6 gap-6 border-b border-border/30 bg-bg/50">
              <div className="w-full md:w-1/3 shrink-0">
                <div className="aspect-[2/3] rounded-xl overflow-hidden relative shadow-xl">
                  {selectedChronicle.avatar ? (
                    <img
                      src={getImageUrl(selectedChronicle.avatar)}
                      alt={selectedChronicle.title || 'Chronicle'}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-4xl font-bold text-text">
                      {selectedChronicle.title?.charAt(0).toUpperCase() || 'C'}
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                </div>
              </div>

              <div className="w-full md:w-2/3 flex flex-col justify-center">
                <div className="flex items-center gap-2 mb-2 text-accent">
                  <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>cruelty_free</span>
                  <span className="text-xs uppercase tracking-[0.2em] opacity-80 font-medium">{isProcessing ? 'Chronicle Processing' : 'Chronicle'}</span>
                </div>
                <h1 className="text-2xl font-semibold text-text mb-2">{selectedChronicle.title || 'Untitled Chronicle'}</h1>
                <p className="text-sm text-muted leading-relaxed">{selectedChronicle.synopsis || 'No description available.'}</p>

                {selectedGenres.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {selectedGenres.map((genre) => (
                      <div key={genre} className="px-3 py-1 rounded-full bg-surface/80 text-muted text-xs border border-border/20 flex items-center gap-1">
                        <span className="material-symbols-outlined text-[14px]">{genreIcons[genre] || 'auto_stories'}</span>
                        {genre}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="p-6 flex flex-col gap-6 bg-surface/50">
              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-end">
                  <h2 className="text-xl font-semibold text-text">Overall Status</h2>
                  {isProcessing ? (
                    <span className="text-sm font-bold text-accent">{progressPercent}%</span>
                  ) : (
                    <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400">Ready</span>
                  )}
                </div>
                <div className="h-2 w-full bg-surface-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full bg-gradient-to-r from-accent2 to-accent rounded-full ${isProcessing ? 'progress-glow animate-pulse-glow' : ''}`}
                    style={{ width: isProcessing ? `${progressPercent}%` : '100%' }}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-4 p-3 rounded-lg bg-surface/30 border border-border/10">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                    <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-text">Chronicle Initialized</p>
                    <p className="text-xs text-muted">Base lore and characters established.</p>
                  </div>
                </div>

                {isProcessing ? (
                  activePhase ? (
                    <div className="flex items-center gap-4 p-3 rounded-lg bg-accent/10 border border-accent/30 relative overflow-hidden">
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-accent/5 to-transparent animate-pulse" />
                      <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center shrink-0 relative z-10">
                        <span className="material-symbols-outlined animate-spin-slow">sync</span>
                      </div>
                      <div className="flex-1 relative z-10">
                        <p className="text-sm font-bold text-accent">{activePhase.phase || activePhase.status || 'Extracting Story Elements'}</p>
                        <p className="text-xs text-accent/80">{activeStep?.step || activeStep?.status || 'Analyzing narrative arcs and dynamic interactions...'}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-4 p-3 rounded-lg bg-surface/10 border border-border/10 opacity-50">
                      <div className="w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center shrink-0">
                        <div className="h-1.5 w-1.5 rounded-full bg-muted animate-pulse" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-muted">Loading status...</p>
                        <p className="text-xs text-muted/70">Fetching processing details</p>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-surface/30 border border-border/10">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-text">Story Elements Extracted</p>
                      <p className="text-xs text-muted">Narrative arcs and character dynamics analyzed.</p>
                    </div>
                  </div>
                )}

                {isProcessing ? (
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-surface/10 border border-border/10 opacity-50">
                    <div className="w-8 h-8 rounded-full bg-surface-2 text-muted flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined">schedule</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-muted">Generating Recommended Models</p>
                      <p className="text-xs text-muted/70">Awaiting extraction completion.</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-surface/30 border border-border/10">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-text">Models Generated</p>
                      <p className="text-xs text-muted">Recommended models generated and configured.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 bg-bg border-t border-border/20 flex justify-end">
              {isProcessing ? (
                <button className="px-6 py-2 rounded-full bg-surface-2 text-muted text-sm font-medium cursor-not-allowed opacity-70 flex items-center gap-2 transition-all" disabled>
                  <span className="material-symbols-outlined text-[18px]">close</span>
                  Cancel Processing
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => navigate(`/chronicle/${encodeURIComponent(selectedChronicle.id)}`)}
                  className="px-6 py-2 rounded-full bg-accent text-bg text-sm font-semibold transition hover:opacity-90 flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                  Start Chronicle
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => {
                setSelectedChronicle(null);
                setProcessStatus(null);
              }}
              className="absolute top-4 right-4 z-20 rounded-full p-2 text-muted transition-colors hover:bg-bg/40 hover:text-text"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

          </div>
        </div>
      )}
    </main>
  );
}
