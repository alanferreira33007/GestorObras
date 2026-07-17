/**
 * API Client — Comunicação com serverless functions
 */
const API = {
  baseUrl: '',

  getToken() {
    return localStorage.getItem('gp_token');
  },

  getUser() {
    try {
      return JSON.parse(localStorage.getItem('gp_user') || 'null');
    } catch { return null; }
  },

  headers() {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.getToken()}`,
    };
  },

  async request(url, options = {}) {
    try {
      const res = await fetch(this.baseUrl + url, {
        ...options,
        headers: this.headers(),
      });
      if (res.status === 401) {
        localStorage.removeItem('gp_token');
        localStorage.removeItem('gp_user');
        window.location.href = '/login.html';
        return null;
      }
      return await res.json();
    } catch (err) {
      console.error('API error:', err);
      throw err;
    }
  },

  async fetchData() {
    return this.request('/api/sheets?action=fetch');
  },

  async fetchAudit() {
    return this.request('/api/sheets?action=audit');
  },

  async fetchQuotes(force = false) {
    return this.request(`/api/quotes${force ? '?force=1' : ''}`);
  },

  async appendFin(values) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'append_fin', values }),
    });
  },

  async updateFin(id, values) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'update_fin', id, values }),
    });
  },

  async deleteFin(ids) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'delete_fin', ids }),
    });
  },

  async appendObra(values) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'append_obra', values }),
    });
  },

  async updateObra(id, values) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'update_obra', id, values }),
    });
  },

  async renameObra(oldName, newName) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'rename_obra', oldName, newName }),
    });
  },

  async logAudit(entry) {
    return this.request('/api/sheets', {
      method: 'POST',
      body: JSON.stringify({ action: 'log_audit', entry }),
    });
  },
};
