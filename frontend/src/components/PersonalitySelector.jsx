import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, getImageUrl } from '../api';
import ConfirmModal from './ConfirmModal.jsx';
import EditModal from './EditModal.jsx';
import Sidebar from './Sidebar.jsx';
import ThemeSelector from './ThemeSelector.jsx';
import ThemeModal from './ThemeModal.jsx';

function PersonalitySelector({
  onPersonaSelected,
  selectedThemeId,
  customBackgroundUrl,
  onSelectTheme,
  onUploadBackground,
  onClearCustomBackground,
  onCreateCustomTheme,
  themes,
  onHoverPreview,
  onHoverPreviewEnd,
  onDeleteTheme,
  onUpdateTheme,
}) {
  const [personalities, setPersonalities] = useState({});
  const [chronicles, setChronicles] = useState([]);
  const [editingPersonaKey, setEditingPersonaKey] = useState(null);
  const [editingChronicle, setEditingChronicle] = useState(null);
  const [chronicleForm, setChronicleForm] = useState({ title: '', description: '', synopsis: '' });
  const [chronicleSaving, setChronicleSaving] = useState(false);
  const [chroniclesLoading, setChroniclesLoading] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [themeModalOpen, setThemeModalOpen] = useState(false);
  const [modalInitialData, setModalInitialData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState(null);
  const [query, setQuery] = useState('');
  const [activeView, setActiveView] = useState('discover');
  const navigate = useNavigate();

  useEffect(() => {
    loadPersonalities();
    loadChronicles();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

  const loadPersonalities = async () => {
    setError('');
    setLoading(true);
    try {
      const data = await api.getPersonalities();
      setPersonalities(data);
    } catch (error) {
      console.error('Failed to load personalities:', error);
      setError('Unable to load personalities. Confirm the backend is running.');
      setPersonalities({});
    }
    setLoading(false);
  };

  const loadChronicles = async () => {
    setChroniclesLoading(true);
    try {
      const rows = await api.listChronicles();
      setChronicles(rows || []);
    } catch (error) {
      console.error('Failed to load chronicles:', error);
      setChronicles([]);
    }
    setChroniclesLoading(false);
  };

  const handlePersonaClick = (persona) => {
    onPersonaSelected(persona);
  };

  const handleSavePersona = async (data) => {
    setLoading(true);
    setError('');
    setToast('');
    try {
      if (editingPersonaKey) {
        await api.updatePersonality(editingPersonaKey, data);
      } else {
        await api.createPersonality(data);
      }
      await loadPersonalities();
      setEditModalOpen(false);
      setEditingPersonaKey(null);
      setModalInitialData(null);
      setToast('Persona saved successfully');
    } catch (error) {
      console.error('Failed to save personality:', error);
      setError(`Failed to save personality: ${error.message}`);
      setToast(`Failed to save: ${error.message}`);
    }
    setLoading(false);
  };

  const handleEditPersona = (e, persona) => {
    e.stopPropagation();
    setEditingPersonaKey(persona.key);
    setModalInitialData(persona);
    setEditModalOpen(true);
  };

  const handleDeletePersona = (e, persona) => {
    e.stopPropagation();
    setConfirmTarget(persona);
    setConfirmOpen(true);
  };

  const handleEditChronicle = (e, chronicle) => {
    e.stopPropagation();
    setEditingChronicle(chronicle);
    setChronicleForm({
      title: chronicle.title || '',
      description: chronicle.synopsis || '',
      synopsis: chronicle.synopsis || '',
    });
  };

  const handleDeleteChronicle = async (e, chronicle) => {
    e.stopPropagation();
    if (!window.confirm(`Delete chronicle '${chronicle.title || 'Untitled'}'?`)) return;
    try {
      await api.deleteChronicle(chronicle.id);
      setChronicles((prev) => prev.filter((item) => item.id !== chronicle.id));
      setToast(`Deleted ${chronicle.title || 'chronicle'}`);
    } catch (error) {
      console.error('Failed to delete chronicle:', error);
      setToast(`Delete failed: ${error.message}`);
    }
  };

  const handleSaveChronicle = async (e) => {
    e.preventDefault();
    if (!editingChronicle) return;
    setChronicleSaving(true);
    try {
      const updated = await api.updateChronicle(editingChronicle.id, {
        title: chronicleForm.title,
        synopsis: chronicleForm.synopsis || chronicleForm.description,
      });
      setChronicles((prev) => prev.map((item) => (item.id === editingChronicle.id ? { ...item, ...updated } : item)));
      setEditingChronicle(null);
      setChronicleForm({ title: '', description: '', synopsis: '' });
      setToast('Chronicle updated');
    } catch (error) {
      console.error('Failed to update chronicle:', error);
      setToast(`Update failed: ${error.message}`);
    }
    setChronicleSaving(false);
  };

  const doDeleteConfirmed = async () => {
    if (!confirmTarget) return;
    setConfirmOpen(false);
    setLoading(true);
    setError('');
    setToast('');
    try {
      await api.deletePersonality(confirmTarget.key);
      setToast(`Deleted ${confirmTarget.name}`);
      await loadPersonalities();
    } catch (error) {
      console.error('Failed to delete personality:', error);
      setError(`Failed to delete personality: ${error.message}`);
      setToast(`Delete failed: ${error.message}`);
    }
    setConfirmTarget(null);
    setLoading(false);
  };

  const handleCancelEdit = () => {
    setEditModalOpen(false);
    setEditingPersonaKey(null);
    setModalInitialData(null);
  };

  const filteredList = Object.values(personalities).filter((p) => {
    const search = query.toLowerCase();
    return (
      p.name.toLowerCase().includes(search) ||
      (p.description || '').toLowerCase().includes(search) ||
      p.key.toLowerCase().includes(search)
    );
  });

  const filteredChronicles = chronicles.filter((chronicle) => {
    const search = query.toLowerCase();
    return (
      (chronicle.title || '').toLowerCase().includes(search) ||
      (chronicle.synopsis || '').toLowerCase().includes(search) ||
      (chronicle.setup_status || '').toLowerCase().includes(search) ||
      String(chronicle.id).toLowerCase().includes(search)
    );
  });

  const formatChronicleDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  return (
    <div className="flex h-screen text-text">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        onCreateClick={() => {
          setEditingPersonaKey(null);
          setModalInitialData(null);
          setEditModalOpen(true);
        }}
      />

      <main className="flex flex-1 flex-col overflow-hidden px-6 pb-6 pt-0">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border/40 py-5">
          <div className="group flex max-w-xl flex-1 items-center rounded-full border border-border/60 bg-surface/80 px-3 text-sm text-text shadow-sm shadow-surface/30 transition focus-within:border-accent focus-within:shadow-accent/10">
            <input
              type="text"
              placeholder="Search personalities…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-transparent px-4 py-2.5 text-sm text-text outline-none transition"
            />
            <span className="material-symbols-outlined px-3 text-muted transition group-focus-within:text-accent">search</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="rounded-full border border-border/50 bg-surface/80 px-4 py-2 text-sm font-semibold text-text shadow-sm shadow-surface/30 transition hover:-translate-y-0.5 hover:border-accent/40 hover:bg-surface/70"
              onClick={() => setThemeModalOpen(true)}
            >
              Theme
            </button>
            <button
              className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-text shadow-lg shadow-accent/20 transition hover:-translate-y-0.5"
              onClick={() => navigate('/chronicle')}
            >
              + Create Chronicle
            </button>
            <button
              className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-text shadow-lg shadow-accent/20 transition hover:-translate-y-0.5"
              onClick={() => {
                setEditingPersonaKey(null);
                setModalInitialData(null);
                setEditModalOpen(true);
              }}
            >
              + Create New Persona
            </button>
          </div>
        </header>

        {error && <div className="mb-3 rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-accent">{error}</div>}
        {toast && <div className="mb-3 rounded-xl border border-accent2/40 bg-accent2/10 px-4 py-3 text-sm text-accent2">{toast}</div>}

        <section className="flex-1 overflow-y-auto pr-1">
          <div className="mb-6 rounded-[24px] border border-border/40 bg-gradient-to-br from-surface/90 to-surface/70 p-4 shadow-sm shadow-surface/40">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-accent">Chronicles</h2>
              </div>
            </div>

            {chroniclesLoading ? (
              <div className="py-8 text-center text-muted">Loading chronicles…</div>
            ) : filteredChronicles.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-surface/80 px-6 py-10 text-center text-muted">
                No chronicles yet. Create one to get started.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredChronicles.map((chronicle) => (
                  <div
                    key={chronicle.id}
                    className="group relative flex h-32 cursor-pointer items-center gap-4 overflow-hidden rounded-[20px] border border-border/60 bg-surface/80 p-4 shadow-md shadow-surface/25 transition hover:-translate-y-1 hover:border-accent/40 hover:shadow-lg"
                    onClick={() => navigate(`/chronicle/${encodeURIComponent(chronicle.id)}`)}
                  >
                    <div className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-gradient-to-br from-accent2 to-accent">
                      <div className="flex h-full w-full items-center justify-center text-2xl font-semibold text-text">
                        {chronicle.title?.charAt(0) || 'C'}
                      </div>
                    </div>

                    <div className="flex h-24 flex-1 flex-col justify-between overflow-hidden">
                      <div className="min-h-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="truncate text-base font-semibold text-text">{chronicle.title}</h3>
                        </div>
                        <p className="mt-1 text-sm text-muted line-clamp-2 break-words">{chronicle.synopsis || 'No description available.'}</p>
                      </div>

                      <div className="flex items-center justify-between text-xs text-muted">
                        <span>{formatChronicleDate(chronicle.created_at)}</span>
                        <div className="flex gap-2 opacity-0 transition group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(e) => handleEditChronicle(e, chronicle)}
                            className="rounded-full border border-border/40 bg-surface/90 p-2 text-text shadow-sm shadow-surface/30 transition hover:-translate-y-0.5 hover:bg-accent/15 hover:text-accent"
                            title="Edit"
                          >
                            <span className="material-symbols-outlined text-base">edit</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteChronicle(e, chronicle)}
                            className="rounded-full border border-border/40 bg-surface/90 p-2 text-text shadow-sm shadow-surface/30 transition hover:-translate-y-0.5 hover:bg-accent2/15 hover:text-accent2"
                            title="Delete"
                          >
                            <span className="material-symbols-outlined text-base">delete</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {loading ? (
            <div className="py-20 text-center text-muted">Loading personalities…</div>
          ) : filteredList.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-surface/80 px-6 py-16 text-center text-muted">
              <p>No personalities found. Create one to get started.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <h2 className="mb-4 text-lg font-semibold text-accent">Discover</h2>
                {/* 4‑column grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {filteredList.map((persona) => (
                    <div
                      key={persona.key}
                      className="group relative flex h-32 cursor-pointer items-center gap-4 overflow-hidden rounded-[20px] border border-border/60 bg-surface/80 p-4 shadow-md shadow-surface/25 transition hover:-translate-y-1 hover:border-accent/40 hover:shadow-lg"
                      onClick={() => handlePersonaClick(persona)}
                    >
                      {/* Square avatar */}
                      <div className="h-24 w-24 shrink-0 overflow-hidden rounded-[16px] border border-white/10 bg-gradient-to-br from-accent2 to-accent shadow-inner">
                        {persona.avatar ? (
                          <img
                            src={getImageUrl(persona.avatar)}
                            alt={persona.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-2xl font-semibold text-text">
                            {persona.name.charAt(0)}
                          </div>
                        )}
                      </div>

                      {/* Info — fixed height */}
                      <div className="flex h-24 flex-1 flex-col justify-between overflow-hidden">
                        <div className="min-h-0 flex-1">
                          <h3 className="text-base font-semibold text-text truncate">{persona.name}</h3>
                          <p className="mt-1 text-sm text-muted line-clamp-2 break-words">
                            {persona.description || "No description"}
                          </p>
                        </div>

                        {/* Edit/Delete buttons */}
                        <div className="flex justify-end gap-2 opacity-0 transition group-hover:opacity-100">
                          <button
                            className="rounded-full border border-border/40 bg-surface/90 px-3 py-1.5 text-sm text-text shadow-sm shadow-surface/30 transition hover:-translate-y-0.5 hover:bg-accent/15 hover:text-accent"
                            onClick={(e) => handleEditPersona(e, persona)}
                            title="Edit"
                          >
                            <span className="material-symbols-outlined text-base">edit</span>
                          </button>
                          <button
                            className="rounded-full border border-border/40 bg-surface/90 px-3 py-1.5 text-sm text-text shadow-sm shadow-surface/30 transition hover:-translate-y-0.5 hover:bg-accent2/15 hover:text-accent2"
                            onClick={(e) => handleDeletePersona(e, persona)}
                            title="Delete"
                          >
                            <span className="material-symbols-outlined text-base">delete</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      <ThemeModal open={themeModalOpen} onClose={() => setThemeModalOpen(false)}>
        <ThemeSelector
          themes={themes}
          selectedThemeId={selectedThemeId}
          customBackgroundUrl={customBackgroundUrl}
          onSelectTheme={onSelectTheme}
          onUploadBackground={onUploadBackground}
          onClearCustomBackground={onClearCustomBackground}
          onCreateCustomTheme={onCreateCustomTheme}
          onHoverPreview={onHoverPreview}
          onHoverPreviewEnd={onHoverPreviewEnd}
          onDeleteTheme={onDeleteTheme}
            onUpdateTheme={onUpdateTheme}
        />
      </ThemeModal>

      {editingChronicle && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-bg/70 p-4">
          <div className="w-full max-w-md rounded-3xl border border-border/60 bg-surface/90 p-6 shadow-2xl shadow-surface/40 backdrop-blur-xl">
            <h3 className="text-xl font-semibold text-text">Edit Chronicle</h3>
            <form onSubmit={handleSaveChronicle} className="mt-4 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted">Title</label>
                <input
                  value={chronicleForm.title}
                  onChange={(e) => setChronicleForm((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted">Description</label>
                <textarea
                  value={chronicleForm.description}
                  onChange={(e) => setChronicleForm((prev) => ({ ...prev, description: e.target.value, synopsis: e.target.value }))}
                  rows={3}
                  className="min-h-[90px] w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted">Synopsis</label>
                <textarea
                  value={chronicleForm.synopsis}
                  onChange={(e) => setChronicleForm((prev) => ({ ...prev, synopsis: e.target.value }))}
                  rows={3}
                  className="min-h-[100px] w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEditingChronicle(null);
                    setChronicleForm({ title: '', description: '', synopsis: '' });
                  }}
                  className="rounded-lg bg-surface/80 px-3 py-2 text-sm text-text"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={chronicleSaving}
                  className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-text"
                >
                  {chronicleSaving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <EditModal
        open={editModalOpen}
        initialData={modalInitialData}
        onSave={handleSavePersona}
        onCancel={handleCancelEdit}
        saving={loading}
      />
      <ConfirmModal
        open={confirmOpen}
        title="Delete Persona"
        message={confirmTarget ? `Delete persona '${confirmTarget.name}'? This cannot be undone.` : ''}
        onConfirm={doDeleteConfirmed}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

export default PersonalitySelector;