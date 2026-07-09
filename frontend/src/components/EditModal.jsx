import React, { useState, useEffect } from 'react';
import { getImageUrl } from '../api';

export default function EditModal({ open, initialData, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    system: '',
    scenario: '',
    opening_prompt: '',
    avatar: null
  });
  const [errors, setErrors] = useState({});
  const [preview, setPreview] = useState('');

  useEffect(() => {
    if (initialData) {
      // Handle both possible keys: "scenario" or "Scenario"
      const scenarioValue = initialData.scenario ?? initialData.Scenario ?? '';
      setForm({
        name: initialData.name || '',
        description: initialData.description || '',
        system: initialData.system || '',
        scenario: scenarioValue,
        opening_prompt: initialData.opening_prompt || '',
        avatar: null
      });
      setPreview(initialData.avatar ? getImageUrl(initialData.avatar) : '');
    } else {
      setForm({
        name: '',
        description: '',
        system: '',
        scenario: '',
        opening_prompt: '',
        avatar: null
      });
      setPreview('');
    }
    setErrors({});
  }, [initialData, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') onCancel && onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Name is required';
    if (!form.system.trim()) e.system = 'System prompt is required';
    return e;
  };

  const handleChange = (k, v) => setForm({ ...form, [k]: v });

  const handleFileChange = (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;

    setForm((s) => ({ ...s, avatar: f }));

    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result);
    };
    reader.readAsDataURL(f);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const eobj = validate();
    setErrors(eobj);
    if (Object.keys(eobj).length === 0) {
      // Ensure scenario is always a string (even empty) to satisfy backend
      const payload = {
        ...form,
        scenario: form.scenario ?? ''
      };
      onSave(payload);
    }
  };

  return (
    <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-bg/70 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] rounded-3xl border border-border/60 bg-surface/90 shadow-2xl shadow-surface/40 backdrop-blur-xl flex flex-col">
        {/* Fixed header */}
        <div className="flex-shrink-0 px-6 pt-6 pb-2">
          <h3 className="text-xl font-semibold text-text">
            {initialData ? 'Edit Personality' : 'Create Personality'}
          </h3>
        </div>

        {/* Scrollable form body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Name</label>
            <input
              className="w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text placeholder:text-muted outline-none transition focus:border-accent"
              value={form.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="Enter personality name"
            />
            {errors.name && <div className="mt-1 text-sm text-accent">{errors.name}</div>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Description</label>
            <textarea
              className="min-h-[80px] max-h-48 overflow-y-auto w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text placeholder:text-muted outline-none transition focus:border-accent"
              value={form.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Brief description"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Personality</label>
            <textarea
              className="min-h-[100px] max-h-48 overflow-y-auto w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text placeholder:text-muted outline-none transition focus:border-accent"
              value={form.system}
              onChange={(e) => handleChange('system', e.target.value)}
              placeholder="Define the system behavior"
            />
            {errors.system && <div className="mt-1 text-sm text-accent">{errors.system}</div>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Base Prompt / Scenario</label>
            <textarea
              className="min-h-[90px] max-h-48 overflow-y-auto w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text placeholder:text-muted outline-none transition focus:border-accent"
              value={form.scenario}
              onChange={(e) => handleChange('scenario', e.target.value)}
              placeholder="Scenario or context"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Opening Prompt</label>
            <textarea
              className="min-h-[90px] max-h-48 overflow-y-auto w-full rounded-xl border border-border/60 bg-surface px-3 py-2 text-sm text-text placeholder:text-muted outline-none transition focus:border-accent"
              value={form.opening_prompt}
              onChange={(e) => handleChange('opening_prompt', e.target.value)}
              placeholder="Initial assistant message"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Avatar Image</label>
            <div className="relative">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="absolute inset-0 cursor-pointer opacity-0"
                id="avatar-upload"
              />
              <label
                htmlFor="avatar-upload"
                className="inline-flex w-full cursor-pointer items-center justify-center rounded-xl border border-border/60 bg-surface/80 px-4 py-2.5 text-sm text-muted transition hover:border-accent hover:bg-surface/70"
              >
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {form.avatar ? 'Change Image' : 'Choose Image'}
              </label>
            </div>
            {preview && (
              <div className="mt-3 overflow-hidden rounded-xl border border-border/60">
                <img src={preview} alt="preview" className="h-24 w-24 object-cover" />
              </div>
            )}
          </div>
        </form>

        {/* Fixed footer */}
        <div className="flex-shrink-0 px-6 pb-6 pt-2 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg bg-surface/80 px-3 py-2 text-sm text-text transition hover:bg-surface/70"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded-lg bg-gradient-to-r from-accent to-accent2 px-3 py-2 text-sm font-semibold text-text transition hover:-translate-y-0.5"
            onClick={handleSubmit}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}