const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const BACKEND_URL = API_BASE;

export function getImageUrl(path) {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  if (path.startsWith('/')) return `${BACKEND_URL}${path}`;
  return `${BACKEND_URL}/${path}`;
}

async function handleResponse(res) {
  const text = await res.text();
  let payload = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch (err) {
    payload = null;
  }

  if (!res.ok) {
    const message = Array.isArray(payload?.detail)
      ? payload.detail.map(e => `${e.loc?.join('.')} — ${e.msg}`).join(', ')
      : payload?.detail || payload?.message || text || res.statusText;
    throw new Error(message || 'Request failed');
  }

  return payload;
}

export const api = {
  // Personalities
  async getPersonalities() {
    const res = await fetch(`${API_BASE}/personalities`);
    return handleResponse(res);
  },

  async createPersonality(data) {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.description) formData.append('description', data.description);
    formData.append('system', data.system);
    formData.append('scenario', data.scenario);
    formData.append('opening_prompt', data.opening_prompt);
    if (data.avatar instanceof File) {
      formData.append('avatar', data.avatar);
    }

    const res = await fetch(`${API_BASE}/personalities`, {
      method: 'POST',
      body: formData
    });
    return handleResponse(res);
  },

  async pickPersonality(choice) {
    const res = await fetch(`${API_BASE}/personalities/pick`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice })
    });
    return handleResponse(res);
  },

  async updatePersonality(personaKey, data) {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.description) formData.append('description', data.description);
    formData.append('system', data.system);
    formData.append('scenario', data.scenario);
    formData.append('opening_prompt', data.opening_prompt);
    if (data.avatar instanceof File) {
      formData.append('avatar', data.avatar);
    }

    const res = await fetch(`${API_BASE}/personalities/${encodeURIComponent(personaKey)}`, {
      method: 'PUT',
      body: formData
    });
    return handleResponse(res);
  },

  async deletePersonality(personaKey) {
    const res = await fetch(`${API_BASE}/personalities/${encodeURIComponent(personaKey)}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  // Sessions
  async getRecentSessions() {
    const res = await fetch(`${API_BASE}/sessions/recent`);
    return handleResponse(res);
  },

  async getRecentChronicles() {
    const res = await fetch(`${API_BASE}/story`);
    return handleResponse(res);
  },

  async getSessions(personaName, personaId) {
    const qs = personaId ? `?persona_id=${encodeURIComponent(personaId)}` : '';
    const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(personaName)}${qs}`);
    return handleResponse(res);
  },

  async pickSession(personaName, personaId, index) {
    const res = await fetch(`${API_BASE}/sessions/pick`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona_name: personaName,
        persona_id: personaId,
        index
      })
    });
    return handleResponse(res);
  },

  async loadSession(personaKey, session) {
    const res = await fetch(`${API_BASE}/sessions/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona_key: personaKey,
        session: session ? session : null
      })
    });
    return handleResponse(res);
  },

  async saveSession(personaKey, messages, context, sessionId) {
    const res = await fetch(`${API_BASE}/sessions/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona_key: personaKey,
        messages,
        context,
        session_id: sessionId
      })
    });
    return handleResponse(res);
  },

  async deleteSession(personaName, personaId, sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(personaName)}/${sessionId}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  // Chat
  async sendMessage(personaKey, messages, context, sessionId, userInput) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persona_key: personaKey,
        messages,
        context: context,
        session_id: sessionId,
        user_input: userInput
      })
    });
    return handleResponse(res);
  },

  // --- Chronicle ---
  async createChronicle(data) {
    const formData = new FormData();
    formData.append('title', data.title);
    if (data.synopsis) formData.append('synopsis', data.synopsis);
    if (data.genre) formData.append('genre', data.genre);
    if (data.magic_rules_md) formData.append('magic_rules_md', data.magic_rules_md);
    if (data.context_token_limit) formData.append('context_token_limit', data.context_token_limit);
    if (data.avatar instanceof File) {
      formData.append('avatar', data.avatar);
    }

    const res = await fetch(`${API_BASE}/story`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  async uploadChronicleDocument(sessionId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/story/${sessionId}/docs`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  async getDocumentStatus(sessionId, docId) {
    const res = await fetch(`${API_BASE}/story/${sessionId}/docs/${docId}/status`);
    return handleResponse(res);
  },

  async getChronicleProcessStatus(sessionId) {
    const res = await fetch(`${API_BASE}/story/${sessionId}/process-status`);
    return handleResponse(res);
  },
  // Chronicle helpers
  async listChronicles() {
    const res = await fetch(`${API_BASE}/story`);
    return handleResponse(res);
  },
  async getChronicle(id) {
    const res = await fetch(`${API_BASE}/story/${id}`);
    return handleResponse(res);
  },
  async chatChronicle(id, user_input) {
    const res = await fetch(`${API_BASE}/story/${id}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_input })
    });
    return handleResponse(res);
  },

  async updateChronicle(id, data) {
    const formData = new FormData();
    if (data.title !== undefined) formData.append('title', data.title ?? '');
    if (data.synopsis !== undefined) formData.append('synopsis', data.synopsis ?? '');
    if (data.genre !== undefined) formData.append('genre', data.genre ?? '');
    if (data.magic_rules_md !== undefined) formData.append('magic_rules_md', data.magic_rules_md ?? '');
    if (data.context_token_limit !== undefined) formData.append('context_token_limit', data.context_token_limit);
    if (data.avatar instanceof File) {
      formData.append('avatar', data.avatar);
    }

    const res = await fetch(`${API_BASE}/story/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: formData,
    });
    return handleResponse(res);
  },

  async deleteChronicle(id) {
    const res = await fetch(`${API_BASE}/story/${id}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  }
};