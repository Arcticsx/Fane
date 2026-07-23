import React from 'react';
import { CircleCheck, CircleX } from 'lucide-react';

function ThemeSelector({ themes = [], selectedThemeId, gradientEnabled, onToggleGradient, onSelectTheme, onUploadBackground, customBackgroundUrl, onClearCustomBackground, onCreateCustomTheme, onHoverPreview, onHoverPreviewEnd, onDeleteTheme, onUpdateTheme }) {
  const [custom, setCustom] = React.useState({
    name: '',
    description: '',
    bgColor: '#08020f',
    surface: '#110520',
    surface2: '#1c0a38',
    border: '#3a1060',
    text: '#f0e8ff',
    muted: '#8a70aa',
    accent: '#aa00ff',
    accent2: '#ff00cc',
  });

  const handleCustomChange = (k, v) => setCustom((s) => ({ ...s, [k]: v }));
  const [editingId, setEditingId] = React.useState(null);

  const handleCreateOrUpdate = () => {
    if (!custom.name.trim()) return;
    if (typeof onCreateCustomTheme === 'function') {
      const payload = {
        name: custom.name,
        description: custom.description,
        bgColor: custom.bgColor,
        surface: custom.surface,
        surface2: custom.surface2,
        border: custom.border,
        text: custom.text,
        muted: custom.muted,
        accent: custom.accent,
        accent2: custom.accent2,
        background: `linear-gradient(180deg, ${custom.bgColor} 0%, ${custom.surface} 100%)`,
      };
      if (editingId && typeof onUpdateTheme === 'function') {
        onUpdateTheme(editingId, payload);
      } else {
        onCreateCustomTheme(payload);
      }
      setCustom((s) => ({ ...s, name: '', description: '' }));
      setEditingId(null);
      onHoverPreviewEnd && onHoverPreviewEnd();
    }
  };
  return (
    <div className="rounded-3xl border border-border/60 bg-surface/90 p-5 shadow-2xl shadow-surface/20">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text">Theme</h2>
          <p className="text-sm text-muted">Customize the app background and preview your style.</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {themes.map((theme) => (
          <button
            key={theme.id}
            type="button"
            onClick={() => onSelectTheme(theme.id)}
            className={`group rounded-3xl border p-4 text-left transition duration-200 ${
              selectedThemeId === theme.id
                ? 'border-accent bg-accent/10 shadow-[0_0_0_1px_rgba(204,99,255,0.3)]'
                : 'border-border/60 bg-surface/70 hover:border-accent/70 hover:bg-surface/80'
            }`}
          >
            <div className="mb-3 h-28 overflow-hidden rounded-3xl bg-surface/90 shadow-inner shadow-surface/20">
              <div className="h-full w-full grid grid-cols-3">
                <div className="border-r border-border/60" style={{ background: theme.bgColor }} aria-hidden />
                <div className="border-r border-border/60" style={{ background: theme.surface }} aria-hidden />
                <div style={{ background: theme.accent }} aria-hidden />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-text">{theme.name}</div>
                <p className="mt-1 text-xs text-muted">{theme.description}</p>
              </div>
              <div className="flex items-center gap-2">
                {selectedThemeId === theme.id && (
                  <span className="rounded-full bg-accent/20 px-2 py-1 text-[11px] font-semibold text-accent">Selected</span>
                )}
                {theme.custom && typeof onUpdateTheme === 'function' && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      // populate form for editing
                      setCustom({
                        name: theme.name || '',
                        description: theme.description || '',
                        bgColor: theme.bgColor || '#08020f',
                        surface: theme.surface || '#110520',
                        surface2: theme.surface2 || '#1c0a38',
                        border: theme.border || '#3a1060',
                        text: theme.text || '#f0e8ff',
                        muted: theme.muted || '#8a70aa',
                        accent: theme.accent || '#aa00ff',
                        accent2: theme.accent2 || '#ff00cc',
                      });
                      setEditingId(theme.id);
                      onHoverPreview && onHoverPreview({ ...theme });
                    }}
                    className="rounded-full bg-surface/80 px-2 py-1 text-[11px] font-semibold text-text hover:bg-accent/10"
                  >
                    Edit
                  </button>
                )}
                {theme.custom && typeof onDeleteTheme === 'function' && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!confirm(`Delete theme "${theme.name}"? This cannot be undone.`)) return;
                      onDeleteTheme(theme.id);
                    }}
                    className="rounded-full bg-surface/80 px-2 py-1 text-[11px] font-semibold text-text hover:bg-accent2/10"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>


      <div className="mt-5 rounded-3xl border border-border/60 bg-surface/80 p-4">
        <div className="flex items-center justify-between">
          <div className="flex w-full items-center gap-2 justify-between">
            <div>
              <div className="text-sm font-medium text-text">Background Gradient</div>
              <p className="text-xs text-muted">Toggle the gradient effect on the background</p>
            </div>
            <button
              type="button"
              aria-pressed={gradientEnabled}
              aria-label={gradientEnabled ? 'Disable background gradient' : 'Enable background gradient'}
              onClick={onToggleGradient}
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors duration-200 ${
                gradientEnabled
                  ? 'bg-accent text-white'
                  : 'bg-surface-2 text-muted hover:bg-surface-2/70'
              }`}
            >
              {gradientEnabled ? (
                <CircleCheck className="h-4 w-4" />
              ) : (
                <CircleX className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-3xl border border-border/60 bg-surface/80 p-4">
        <label className="flex cursor-pointer items-center justify-between gap-3 rounded-3xl border border-dashed border-border/60 bg-surface/80 px-4 py-3 text-sm text-text transition hover:border-accent/70 hover:bg-surface/90">
          <span>Use your own background image</span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                onUploadBackground(file);
              }
            }}
          />
        </label>

        {customBackgroundUrl ? (
          <div className="mt-4 flex flex-col gap-3 rounded-3xl border border-border/60 bg-surface/90 p-3">
            <div className="overflow-hidden rounded-3xl border border-border/60 bg-surface/80">
              <img
                src={customBackgroundUrl}
                alt="Custom background preview"
                className="h-40 w-full object-cover"
              />
            </div>
            <button
              type="button"
              onClick={onClearCustomBackground}
              className="rounded-full bg-surface/80 px-4 py-2 text-sm font-medium text-text transition hover:bg-surface/70"
            >
              Clear custom background
            </button>
          </div>
        ) : null}

        <p className="mt-4 text-xs text-muted">Supported formats: JPG, PNG, WEBP. The image is applied locally to your browser.</p>
      </div>
    </div>
  );
}

export default ThemeSelector;
