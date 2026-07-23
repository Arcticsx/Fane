import React, { useEffect, useRef } from 'react';

export default function ThemeModal({ open, onClose, children }) {
  const innerRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose && onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose && onClose();
      }}
    >
      <div ref={innerRef} className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl border border-border/60 bg-surface p-6 shadow-2xl shadow-surface/40">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-semibold text-text">Choose a theme</h3>
            <p className="text-sm text-muted">Select a custom theme or upload your own background image.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border/60 bg-surface/80 px-3 py-2 text-sm text-text transition hover:bg-surface/70"
          >
            Close
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}
