/**
 * Financeiro Module
 */

function renderFinanceiro() {
  const container = document.getElementById('view-financeiro');
  const fin = window.APP_DATA.financeiro || [];
  const obras = window.APP_DATA.obras || [];
  const obraNames = [...new Set(obras.map(o => (o.Cliente || '').trim()))].filter(Boolean).sort();

  container.innerHTML = `
    <div class="tabs">
      <button class="tab-btn active" onclick="switchFinTab('novo',this)">➕ Novo Lançamento</button>
      <button class="tab-btn" onclick="switchFinTab('consulta',this)">🔍 Consultar</button>
    </div>

    <div class="tab-content active" id="fin-novo">
      ${canEdit() ? renderFinForm(obraNames) : '<div class="alert alert-info">🔒 Sem permissão para criar lançamentos.</div>'}
    </div>

    <div class="tab-content" id="fin-consulta">
      ${renderFinConsulta(fin, obraNames)}
    </div>
  `;
}

function switchFinTab(tab, btn) {
  document.querySelectorAll('#view-financeiro .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#view-financeiro .tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`fin-${tab}`).classList.add('active');
}

function renderFinForm(obraNames) {
  const today = new Date().toISOString().split('T')[0];
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">Novo Lançamento</span></div>
      <div class="card-body">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Data</label>
            <input type="date" class="form-input" id="fin-data" value="${today}">
          </div>
          <div class="form-group">
            <label class="form-label">Valor R$</label>
            <input type="number" class="form-input" id="fin-valor" min="0" step="0.01" placeholder="0,00">
          </div>
          <div class="form-group full">
            <label class="form-label">Obra Vinculada</label>
            <select class="form-select" id="fin-obra">
              <option value="">Selecione...</option>
              ${obraNames.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Tipo</label>
            <select class="form-select" id="fin-tipo">
              <option value="Saída (Despesa)">Saída (Despesa)</option>
              <option value="Entrada">Entrada</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Categoria</label>
            <select class="form-select" id="fin-cat">
              <option value="">Selecione...</option>
              ${CATS.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Forma de Pagamento</label>
            <select class="form-select" id="fin-pag">
              <option value="">Selecione...</option>
              ${PAGAMENTOS.map(p => `<option value="${p}">${p}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Fornecedor</label>
            <input type="text" class="form-input" id="fin-forn" placeholder="Nome do fornecedor">
          </div>
          <div class="form-group full">
            <label class="form-label">Descrição</label>
            <input type="text" class="form-input" id="fin-desc" placeholder="Descrição do lançamento">
          </div>
          <div class="form-group">
            <label class="form-label">Parcelas</label>
            <input type="number" class="form-input" id="fin-parcelas" min="1" max="48" value="1">
          </div>
          <div class="form-group" style="display:flex;align-items:flex-end;">
            <span id="fin-parcela-info" class="text-sm text-muted"></span>
          </div>
        </div>
        <div style="margin-top:20px;">
          <button class="btn btn-primary btn-full" onclick="salvarLancamento()">Salvar Lançamento</button>
        </div>
      </div>
    </div>
  `;
}

async function salvarLancamento() {
  const data = document.getElementById('fin-data').value;
  const valor = parseFloat(document.getElementById('fin-valor').value) || 0;
  const obra = document.getElementById('fin-obra').value.trim();
  const tipo = document.getElementById('fin-tipo').value;
  const cat = document.getElementById('fin-cat').value.trim();
  const pag = document.getElementById('fin-pag').value.trim();
  const forn = document.getElementById('fin-forn').value.trim();
  const desc = document.getElementById('fin-desc').value.trim();
  const parcelas = parseInt(document.getElementById('fin-parcelas').value) || 1;

  // Validate
  const erros = [];
  if (!obra) erros.push('Selecione a Obra Vinculada.');
  if (!cat) erros.push('Selecione a Categoria.');
  if (!desc) erros.push('A Descrição é obrigatória.');
  if (valor <= 0) erros.push('O Valor deve ser maior que zero.');
  if (!pag) erros.push('Selecione a Forma de Pagamento.');
  if (cat === 'Material' && !forn) erros.push('Para Material, Fornecedor é obrigatório.');

  if (erros.length > 0) {
    showToast(erros[0], 'error');
    return;
  }

  showLoading(true);
  try {
    const vp = Math.round(valor / parcelas * 100) / 100;
    for (let p = 0; p < parcelas; p++) {
      const id = generateId() + p;
      let dtP = new Date(data + 'T12:00:00');
      if (p > 0) {
        dtP.setMonth(dtP.getMonth() + p);
      }
      const descP = parcelas > 1 ? `${desc} (${p + 1}/${parcelas})` : desc;
      await API.appendFin([id, toISODate(dtP), tipo, cat, descP, vp, obra, forn, pag]);
    }

    logAction('CRIAR_LANCAMENTO', `${parcelas}x | ${obra} | ${cat} | ${fmtMoeda(valor)}`);
    showToast(`Lançamento salvo! ${parcelas > 1 ? `(${parcelas} parcelas)` : ''}`);
    await refreshData();
    renderFinanceiro();
  } catch (err) {
    showToast('Erro ao salvar: ' + err.message, 'error');
  }
  showLoading(false);
}

function renderFinConsulta(fin, obraNames) {
  if (fin.length === 0) {
    return '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">Nenhum lançamento registrado</div></div>';
  }

  const total = fin.reduce((s, f) => s + safeFloat(f.Valor), 0);

  return `
    <div class="card mb-16">
      <div class="card-header">
        <span class="card-title">Filtros</span>
        <button class="btn btn-secondary" onclick="resetFinFilters()">Limpar</button>
      </div>
      <div class="card-body">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Obra</label>
            <select class="form-select" id="filt-obra" onchange="applyFinFilters()">
              <option value="">Todas</option>
              ${obraNames.map(n => `<option value="${n}">${n}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Categoria</label>
            <select class="form-select" id="filt-cat" onchange="applyFinFilters()">
              <option value="">Todas</option>
              ${CATS.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Tipo</label>
            <select class="form-select" id="filt-tipo" onchange="applyFinFilters()">
              <option value="">Todos</option>
              <option value="Saída (Despesa)">Saída (Despesa)</option>
              <option value="Entrada">Entrada</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Buscar</label>
            <input type="text" class="form-input" id="filt-texto" placeholder="Descrição ou fornecedor..." oninput="applyFinFilters()">
          </div>
        </div>
      </div>
    </div>

    <p class="text-sm text-muted mb-16" id="fin-summary"><strong>${fin.length}</strong> lançamentos | Total: <strong>${fmtMoeda(total)}</strong></p>

    <div class="card">
      <div class="card-body-flush">
        <div class="table-container">
          <table id="fin-table">
            <thead><tr>
              <th>Data</th><th>Tipo</th><th>Obra</th><th>Categoria</th><th>Fornecedor</th><th>Descrição</th><th class="td-right">Valor</th>
              ${canAdmin() ? '<th class="td-center">Ações</th>' : ''}
            </tr></thead>
            <tbody id="fin-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function applyFinFilters() {
  const fin = window.APP_DATA.financeiro || [];
  const obra = (document.getElementById('filt-obra') || {}).value || '';
  const cat = (document.getElementById('filt-cat') || {}).value || '';
  const tipo = (document.getElementById('filt-tipo') || {}).value || '';
  const texto = ((document.getElementById('filt-texto') || {}).value || '').toLowerCase();

  let filtered = fin;
  if (obra) filtered = filtered.filter(f => (f['Obra Vinculada'] || '').trim() === obra);
  if (cat) filtered = filtered.filter(f => (f.Categoria || '').trim() === cat);
  if (tipo) filtered = filtered.filter(f => (f.Tipo || '').trim() === tipo);
  if (texto) filtered = filtered.filter(f =>
    (f['Descrição'] || '').toLowerCase().includes(texto) ||
    (f.Fornecedor || '').toLowerCase().includes(texto)
  );

  const total = filtered.reduce((s, f) => s + safeFloat(f.Valor), 0);
  const summary = document.getElementById('fin-summary');
  if (summary) summary.innerHTML = `<strong>${filtered.length}</strong> lançamentos | Total: <strong>${fmtMoeda(total)}</strong>`;

  renderFinTable(filtered);
}

function renderFinTable(data) {
  const tbody = document.getElementById('fin-tbody');
  if (!tbody) return;

  const sorted = [...data].sort((a, b) => new Date(b.Data) - new Date(a.Data));

  tbody.innerHTML = sorted.map(r => `
    <tr>
      <td>${fmtDate(r.Data)}</td>
      <td><span class="status-badge ${String(r.Tipo || '').match(/Saída|Despesa/i) ? 'status-err' : 'status-ok'}">${r.Tipo || ''}</span></td>
      <td>${r['Obra Vinculada'] || ''}</td>
      <td>${r.Categoria || ''}</td>
      <td>${r.Fornecedor || ''}</td>
      <td>${r['Descrição'] || ''}</td>
      <td class="td-right td-mono">${fmtMoeda(r.Valor)}</td>
      ${canAdmin() ? `<td class="td-center"><button class="btn-icon" onclick="deletarLancamento('${r.ID}')" title="Excluir" style="color:var(--status-danger);">🗑️</button></td>` : ''}
    </tr>
  `).join('');
}

function resetFinFilters() {
  ['filt-obra', 'filt-cat', 'filt-tipo'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const txt = document.getElementById('filt-texto');
  if (txt) txt.value = '';
  applyFinFilters();
}

async function deletarLancamento(id) {
  openModal('Confirmar Exclusão',
    `<p>Deseja excluir o lançamento <strong>#${id}</strong>?</p><p class="text-sm text-muted mt-16">Esta ação não pode ser desfeita.</p>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
     <button class="btn btn-danger" onclick="confirmarDeleteFin('${id}')">Excluir</button>`
  );
}

async function confirmarDeleteFin(id) {
  closeModal();
  showLoading(true);
  try {
    await API.deleteFin([id]);
    logAction('EXCLUIR_LANCAMENTO', `ID=${id}`);
    showToast('Lançamento excluído');
    await refreshData();
    renderFinanceiro();
    // Switch to consulta tab
    setTimeout(() => {
      const btn = document.querySelectorAll('#view-financeiro .tab-btn')[1];
      if (btn) switchFinTab('consulta', btn);
      applyFinFilters();
    }, 100);
  } catch (err) {
    showToast('Erro: ' + err.message, 'error');
  }
  showLoading(false);
}
