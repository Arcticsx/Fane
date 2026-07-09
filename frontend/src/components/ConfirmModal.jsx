import React from 'react';

export default function ConfirmModal({ open, title, message, onConfirm, onCancel }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-bg/70 p-4">
      <div className="w-full max-w-[420px] max-h-[80vh] rounded-2xl border border-border/60 bg-surface/90 p-5 shadow-2xl shadow-surface/30 flex flex-col">
        <h3 className="text-lg font-semibold text-text">{title || 'Confirm'}</h3>
        <div className="mt-2 flex-1 overflow-y-auto max-h-[50vh] pr-1">
          <p className="text-sm leading-6 text-muted whitespace-pre-wrap">{message}</p>
        </div>
        <div className="mt-5 flex justify-end gap-2 flex-shrink-0">
          <button
            className="rounded-lg bg-surface/80 px-3 py-2 text-sm text-text transition hover:bg-surface/70"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            className="rounded-lg bg-accent/80 px-3 py-2 text-sm font-semibold text-text transition hover:bg-accent"
            onClick={onConfirm}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}