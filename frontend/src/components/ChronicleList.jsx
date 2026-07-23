import React, { useEffect, useState } from 'react';
import { api, getImageUrl } from '../api';
import { useNavigate } from 'react-router-dom';

export default function ChronicleList() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  function formatDate(s) {
    try {
      return s ? new Date(s).toLocaleString() : '—';
    } catch (e) {
      return s || '—';
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation();
    if (!confirm('Delete this chronicle? This cannot be undone.')) return;
    try {
      await api.deleteChronicle(id);
      setList((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.error('Failed to delete chronicle', err);
      alert('Failed to delete chronicle: ' + (err.message || err));
    }
  }

  useEffect(() => {
    let mounted = true;
    api.listChronicles()
      .then((rows) => {
        if (mounted) setList(rows || []);
      })
      .catch((e) => console.error('Failed to load chronicles', e))
      .finally(() => mounted && setLoading(false));
    return () => (mounted = false);
  }, []);

  if (loading) return <div className="p-6">Loading chronicles…</div>;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold mb-4">Chronicles</h2>
        <div>
          <button
            onClick={() => navigate('/chronicle')}
            className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-text"
          >
            + Create Chronicle
          </button>
        </div>
      </div>

      {list.length === 0 && (
        <div className="rounded-2xl border border-border/60 bg-surface/80 px-6 py-16 text-center text-muted">No chronicles yet. Create one to get started.</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {list.map((c) => (
          <div
            key={c.id}
            className="group relative flex cursor-pointer flex-col gap-3 rounded-2xl border border-border/60 bg-surface/70 p-4 shadow-lg transition hover:-translate-y-1"
            onClick={() => navigate(`/chronicle/${encodeURIComponent(c.id)}`)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-accent2 to-accent">
                {c.avatar ? (
                  <img src={getImageUrl(c.avatar)} alt={c.title} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-sm font-semibold text-text">
                    {(c.title || 'C').charAt(0).toUpperCase()}
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-semibold text-text truncate">{c.title}</h3>
                <p className="mt-1 text-xs text-muted/70">{c.setup_status}</p>
              </div>
            </div>

            <div className="mt-auto flex items-center justify-between">
              <div className="text-xs text-muted/60">{formatDate(c.created_at)}</div>
              <div className="flex gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); navigate(`/chronicle/${encodeURIComponent(c.id)}`); }}
                  className="rounded-full bg-accent px-3 py-1 text-text text-sm"
                >
                  Open
                </button>
                <button
                  onClick={(e) => handleDelete(e, c.id)}
                  className="rounded-full bg-red-600 px-3 py-1 text-white text-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
