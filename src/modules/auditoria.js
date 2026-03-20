/**
 * Auditoria Module
 */

async function renderAuditoria() {
  const container = document.getElementById('view-auditoria');
  container.innerHTML = '<div class="loading-overlay active" style="position:relative;min-height:200px;"><div class="loading-spinner"></div><p>Carregando logs...</p></div>';

  try {
    const data = await API.fetchAudit();
    const logs = (data.audit || []).reverse().slice(0, 200);

    if (logs.length === 0) {
      container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🛡️</div><div class="empty-state-text">Nenhum registro de auditoria</div></div>';
      return;
    }

    const acoes = [...new Set(logs.map(l => l['Ação'] || ''))].filter(Boolean).sort();
    const usuarios = [...new Set(logs.map(l => l['Usuário'] || ''))].filter(Boolean).sort();

    container.innerHTML = `
      <div class="card mb-16">
        <div class="card-header"><span class="card-title">Filtros</span></div>
        <div class="card-body">
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Ação</label>
              <select class="form-select" id="audit-acao" onchange="filterAudit()">
                <option value="">Todas</option>
                ${acoes.map(a => `<option value="${a}">${a}</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Usuário</label>
              <select class="form-select" id="audit-user" onchange="filterAudit()">
                <option value="">Todos</option>
                ${usuarios.map(u => `<option value="${u}">${u}</option>`).join('')}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Registros</span>
          <span class="text-sm text-muted" id="audit-count">${logs.length} registros</span>
        </div>
        <div class="card-body-flush">
          <div class="table-container">
            <table>
              <thead><tr>
                <th style="width:160px">Data/Hora</th>
                <th style="width:160px">Usuário</th>
                <th style="width:180px">Ação</th>
                <th>Detalhes</th>
              </tr></thead>
              <tbody id="audit-tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    window._auditLogs = logs;
    filterAudit();
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Erro ao carregar auditoria: ${err.message}</div>`;
  }
}

function filterAudit() {
  const logs = window._auditLogs || [];
  const acao = (document.getElementById('audit-acao') || {}).value || '';
  const user = (document.getElementById('audit-user') || {}).value || '';

  let filtered = logs;
  if (acao) filtered = filtered.filter(l => l['Ação'] === acao);
  if (user) filtered = filtered.filter(l => l['Usuário'] === user);

  const tbody = document.getElementById('audit-tbody');
  const count = document.getElementById('audit-count');

  if (count) count.textContent = `${filtered.length} de ${logs.length} registros`;

  if (tbody) {
    tbody.innerHTML = filtered.map(l => `
      <tr>
        <td class="text-sm">${l.Timestamp || ''}</td>
        <td class="fw-600">${l['Usuário'] || ''}</td>
        <td><span class="status-badge status-info">${l['Ação'] || ''}</span></td>
        <td class="text-sm">${l.Detalhes || ''}</td>
      </tr>
    `).join('');
  }
}
