import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

function ChronicleCreator() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: '',
    synopsis: '',
    genre: '',
    magic_rules_md: '',
    context_token_limit: '',
    avatar: null,
  });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [docId, setDocId] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleAvatarChange = (e) => {
    setForm((prev) => ({ ...prev, avatar: e.target.files?.[0] || null }));
  };

  const pollStatus = async (sid, did) => {
    let attempts = 0;
    const maxAttempts = 30; // 30 * 2s = 60s timeout
    const interval = setInterval(async () => {
      attempts++;
      try {
        const data = await api.getDocumentStatus(sid, did);
        setStatus(`Processing… ${data.status} (chunks: ${data.chunk_count || 0})`);
        if (data.status === 'ready') {
          clearInterval(interval);
          setStatus('✅ Document processed successfully!');
        } else if (data.status === 'failed') {
          clearInterval(interval);
          setStatus(`❌ Failed: ${data.error_message || 'Unknown error'}`);
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          setStatus('⏱️ Processing timed out. Please check later.');
        }
      } catch (err) {
        console.error('Poll error:', err);
        clearInterval(interval);
        setStatus('⚠️ Error checking status.');
      }
    }, 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) {
      alert('Title is required');
      return;
    }
    if (!file) {
      alert('Please select a PDF file');
      return;
    }

    setLoading(true);
    setStatus('Creating chronicle...');

    try {
      // 1. Create session
      const sessionData = await api.createChronicle(form);
      const sid = sessionData.id;
      setSessionId(sid);
      setStatus(`Chronicle created (ID: ${sid}). Uploading PDF...`);

      // 2. Upload PDF
      const uploadData = await api.uploadChronicleDocument(sid, file);
      const did = uploadData.source_document_id;
      setDocId(did);
      setStatus('PDF uploaded. Processing started...');

      // 3. Start polling status
      pollStatus(sid, did);
      // Return to the chronicle home page after creation instead of jumping straight into chat
      if (sid) {
        navigate('/chronicle/discover');
      }
    } catch (err) {
      console.error('Creation error:', err);
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 text-text">
      <h1 className="text-3xl font-semibold mb-6">Create a New Chronicle</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Title *</label>
          <input
            type="text"
            name="title"
            value={form.title}
            onChange={handleChange}
            className="w-full rounded-xl border border-border/60 bg-surface px-4 py-2 text-text outline-none focus:border-accent"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Synopsis</label>
          <textarea
            name="synopsis"
            value={form.synopsis}
            onChange={handleChange}
            rows="3"
            className="w-full rounded-xl border border-border/60 bg-surface px-4 py-2 text-text outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Genre</label>
          <input
            type="text"
            name="genre"
            value={form.genre}
            onChange={handleChange}
            className="w-full rounded-xl border border-border/60 bg-surface px-4 py-2 text-text outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Magic Rules (Markdown)</label>
          <textarea
            name="magic_rules_md"
            value={form.magic_rules_md}
            onChange={handleChange}
            rows="4"
            className="w-full rounded-xl border border-border/60 bg-surface px-4 py-2 text-text outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Context Token Limit</label>
          <input
            type="number"
            name="context_token_limit"
            value={form.context_token_limit}
            onChange={handleChange}
            className="w-full rounded-xl border border-border/60 bg-surface px-4 py-2 text-text outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">Profile Image</label>
          <label className="flex w-full cursor-pointer flex-col gap-2 rounded-2xl border border-border/60 bg-surface/70 px-4 py-3 text-sm text-muted transition hover:border-accent/40 hover:bg-surface/80">
            <span className="font-medium text-text">{form.avatar ? form.avatar.name : 'Choose image'}</span>
            <input
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="sr-only"
            />
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium text-muted mb-1">PDF Document *</label>
          <label className="flex w-full cursor-pointer flex-col gap-2 rounded-2xl border border-border/60 bg-surface/70 px-4 py-3 text-sm text-muted transition hover:border-accent/40 hover:bg-surface/80">
            <span className="font-medium text-text">Choose PDF file</span>
            <span className="text-xs text-muted/80">{file ? file.name : 'No file selected'}</span>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="sr-only"
              required
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-full bg-gradient-to-r from-accent to-accent2 py-3 text-sm font-semibold text-text shadow-lg shadow-accent/20 transition hover:-translate-y-0.5 disabled:opacity-50"
        >
          {loading ? 'Working...' : 'Create Chronicle'}
        </button>
      </form>

      {status && (
        <div className="mt-6 p-4 rounded-xl border border-border/60 bg-surface/80 text-sm">
          <p className="text-muted">Status: {status}</p>
          {sessionId && <p className="text-xs text-muted/60 mt-1">Session ID: {sessionId}</p>}
          {docId && <p className="text-xs text-muted/60">Document ID: {docId}</p>}
        </div>
      )}
    </div>
  );
}

export default ChronicleCreator;