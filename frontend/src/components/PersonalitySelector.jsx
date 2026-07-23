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
  gradientEnabled,
  onToggleGradient,
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
    <div className="flex h-screen bg-bg text-text">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        onCreateClick={() => {
          setEditingPersonaKey(null);
          setModalInitialData(null);
          setEditModalOpen(true);
        }}
      />

      <main className="flex flex-1 flex-col overflow-hidden px-6 pb-8 pt-4">
        {/* Header */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-border/30">
          {/* Search */}
          <div className="group flex max-w-xl flex-1 items-center rounded-2xl border border-border/40 bg-surface/70 backdrop-blur-sm px-2 text-sm shadow-sm transition-all focus-within:border-accent focus-within:shadow-accent/20 focus-within:bg-surface/90">
            <span className="material-symbols-outlined px-3 text-muted/70 transition group-focus-within:text-accent">
              search
            </span>
            <input
              type="text"
              placeholder="Search personalities or chronicles…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-transparent px-2 py-2.5 text-sm text-text outline-none placeholder:text-muted/50"
            />
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="flex items-center gap-1.5 rounded-xl border border-border/40 bg-surface/70 px-4 py-2.5 text-sm font-medium text-text shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/50 hover:bg-surface/90 hover:shadow-md active:scale-95"
              onClick={() => setThemeModalOpen(true)}
            >
              <span className="material-symbols-outlined text-lg">palette</span>
              Theme
            </button>
            <button
              className="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-text shadow-md shadow-accent/20 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-accent/30 active:scale-95"
              onClick={() => navigate('/chronicle')}
            >
              <span className="material-symbols-outlined text-lg">add</span>
              New Chronicle
            </button>
            <button
              className="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-text shadow-md shadow-accent/20 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-accent/30 active:scale-95"
              onClick={() => {
                setEditingPersonaKey(null);
                setModalInitialData(null);
                setEditModalOpen(true);
              }}
            >
              <span className="material-symbols-outlined text-lg">person_add</span>
              New Persona
            </button>
          </div>
        </header>

        {/* Notifications */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-300 backdrop-blur-sm">
            <span className="material-symbols-outlined text-base">error</span>
            {error}
          </div>
        )}
        {toast && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-emerald-400/40 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300 backdrop-blur-sm">
            <span className="material-symbols-outlined text-base">check_circle</span>
            {toast}
          </div>
        )}

        <section className="flex-1 overflow-y-auto pr-1 space-y-8">
          {/* Chronicles Section */}
          <div className="rounded-2xl border border-border/20 bg-surface/40 p-5 backdrop-blur-md shadow-lg">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-bold text-accent flex items-center gap-2">
                <span className="material-symbols-outlined text-3xl">
                    cruelty_free
                </span>
                <span>Chronicle</span>
              </h2>
            </div>

            {chroniclesLoading ? (
              <div className="flex items-center justify-center py-12 text-muted">
                <span className="material-symbols-outlined animate-spin mr-2">progress_activity</span>
                Loading chronicles…
              </div>
            ) : filteredChronicles.length === 0 ? (
              <div className="flex items-center justify-center">
                <div className="flex flex-row items-center  gap-2">
                  <span className="material-symbols-outlined text-3xl">
                    cruelty_free
                  </span>
                  <span>No chronicles yet. Create your first story.</span>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filteredChronicles.map((chronicle) => (
                  <div
                    key={chronicle.id}
                    className="group relative flex h-36 cursor-pointer items-center gap-4 overflow-hidden rounded-2xl border border-border/30 bg-surface/70 p-4 shadow-md transition-all duration-200 hover:-translate-y-1 hover:border-accent/50 hover:shadow-xl hover:bg-surface/90"
                    onClick={() => navigate(`/chronicle/${encodeURIComponent(chronicle.id)}`)}
                  >
                    {/* Chronicle avatar */}
                    <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-gradient-to-br from-accent/80 to-accent2/80 shadow-inner">
                      {chronicle.avatar ? (
                        <img
                          src={getImageUrl(chronicle.avatar)}
                          alt={chronicle.title}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-2xl font-bold text-white/90">
                          {chronicle.title?.charAt(0) || 'C'}
                        </div>
                      )}
                    </div>

                    <div className="flex h-20 flex-1 flex-col justify-between overflow-hidden">
                      <div>
                        <h3 className="truncate text-base font-semibold text-text">
                          {chronicle.title}
                        </h3>
                        <p className="mt-1 text-xs text-muted/80 line-clamp-2">
                          {chronicle.synopsis || 'No description available.'}
                        </p>
                      </div>

                      <div className="flex items-center justify-between text-xs text-muted/70">
                        <span>{formatChronicleDate(chronicle.created_at)}</span>
                        <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(e) => handleEditChronicle(e, chronicle)}
                            className="rounded-full border border-border/40 bg-surface/90 p-1.5 text-text/80 transition hover:-translate-y-0.5 hover:bg-accent/20 hover:text-accent"
                            title="Edit"
                          >
                            <span className="material-symbols-outlined text-sm">edit</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteChronicle(e, chronicle)}
                            className="rounded-full border border-border/40 bg-surface/90 p-1.5 text-text/80 transition hover:-translate-y-0.5 hover:bg-red-400/20 hover:text-red-400"
                            title="Delete"
                          >
                            <span className="material-symbols-outlined text-sm">delete</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Personalities Section */}
          <div>
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-bold text-accent flex items-center gap-2">
                <span className="material-symbols-outlined">groups</span>
                Discover Personalities
              </h2>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-20 text-muted">
                <span className="material-symbols-outlined animate-spin mr-2">progress_activity</span>
                Loading personalities…
              </div>
            ) : filteredList.length === 0 ? (

              <div className="flex items-center justify-center w-full">
                <div className="rounded-2xl w-full border border-dashed border-border/50 bg-surface/30 px-6 py-16 text-center text-muted/80 flex flex-row items-center justify-center gap-3">
                  <span className="material-symbols-outlined text-3xl">person_off</span>
                  <span>No personalities found. Create your first persona.</span>
                </div>
              </div>
              
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filteredList.map((persona) => (
                  <div
                    key={persona.key}
                    className="group relative flex h-36 cursor-pointer items-center gap-4 overflow-hidden rounded-2xl border border-border/30 bg-surface/70 p-4 shadow-md transition-all duration-200 hover:-translate-y-1 hover:border-accent/50 hover:shadow-xl hover:bg-surface/90"
                    onClick={() => handlePersonaClick(persona)}
                  >
                    {/* Avatar */}
                    <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl border-2 border-white/10 bg-gradient-to-br from-accent/80 to-accent2/80 shadow-inner">
                      {persona.avatar ? (
                        <img
                          src={getImageUrl(persona.avatar)}
                          alt={persona.name}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-2xl font-bold text-white/90">
                          {persona.name.charAt(0)}
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex h-20 flex-1 flex-col justify-between overflow-hidden">
                      <div>
                        <h3 className="truncate text-base font-semibold text-text">
                          {persona.name}
                        </h3>
                        <p className="mt-1 text-xs text-muted/80 line-clamp-2">
                          {persona.description || "No description"}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex justify-end gap-1 opacity-0 transition group-hover:opacity-100">
                        <button
                          className="rounded-full border border-border/40 bg-surface/90 p-1.5 text-text/80 transition hover:-translate-y-0.5 hover:bg-accent/20 hover:text-accent"
                          onClick={(e) => handleEditPersona(e, persona)}
                          title="Edit"
                        >
                          <span className="material-symbols-outlined text-sm">edit</span>
                        </button>
                        <button
                          className="rounded-full border border-border/40 bg-surface/90 p-1.5 text-text/80 transition hover:-translate-y-0.5 hover:bg-red-400/20 hover:text-red-400"
                          onClick={(e) => handleDeletePersona(e, persona)}
                          title="Delete"
                        >
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>

      <ThemeModal open={themeModalOpen} onClose={() => setThemeModalOpen(false)}>
        <ThemeSelector
          themes={themes}
          selectedThemeId={selectedThemeId}
          customBackgroundUrl={customBackgroundUrl}
          gradientEnabled={gradientEnabled}
          onToggleGradient={onToggleGradient}
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

      {/* Chronicle Edit Modal (refined) */}
      {editingChronicle && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-border/30 bg-surface/90 p-6 shadow-2xl shadow-black/30 backdrop-blur-xl">
            <h3 className="text-xl font-bold text-text mb-1">Edit Chronicle</h3>
            <p className="text-sm text-muted mb-5">Update the details of your story</p>
            <form onSubmit={handleSaveChronicle} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted">Title</label>
                <input
                  value={chronicleForm.title}
                  onChange={(e) => setChronicleForm((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full rounded-xl border border-border/40 bg-surface/80 px-4 py-2.5 text-sm text-text outline-none transition focus:border-accent focus:ring-1 focus:ring-accent/30"
                  placeholder="Chronicle title"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted">Synopsis</label>
                <textarea
                  value={chronicleForm.synopsis}
                  onChange={(e) =>
                    setChronicleForm((prev) => ({
                      ...prev,
                      synopsis: e.target.value,
                      description: e.target.value,
                    }))
                  }
                  rows={4}
                  className="w-full rounded-xl border border-border/40 bg-surface/80 px-4 py-2.5 text-sm text-text outline-none transition focus:border-accent focus:ring-1 focus:ring-accent/30 resize-none"
                  placeholder="Brief summary of your chronicle"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setEditingChronicle(null);
                    setChronicleForm({ title: '', description: '', synopsis: '' });
                  }}
                  className="rounded-xl border border-border/40 bg-surface/70 px-5 py-2.5 text-sm font-medium text-text transition hover:bg-surface/90 active:scale-95"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={chronicleSaving}
                  className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-text shadow-md shadow-accent/20 transition hover:bg-accent/90 active:scale-95 disabled:opacity-60"
                >
                  {chronicleSaving ? 'Saving...' : 'Save Changes'}
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