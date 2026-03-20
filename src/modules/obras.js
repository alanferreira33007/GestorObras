/**
 * Obras Module
 */

function renderObras() {
  const container = document.getElementById('view-obras');
  const obras = window.APP_DATA.obras || [];

  container.innerHTML = `
    <div class="tabs">
      <button class="tab-btn active" onclick="switchObrasTab('nova',this)">➕ Nova Obra</button>
      <button class="tab-btn" onclick="switchObrasTab('carteira',this)">📋 Carteira</button>
      <button class="tab-btn" onclick="switchObrasTab('cronograma',this)">📊 Cronograma</button>
    </div>

    <div class="tab-content active" id="obras-nova">
      ${canEdit() ? renderObraForm() : '<div class="alert alert-info">🔒 Sem permissão.</div>'}
    </div>

    <div class="tab-content" id="obras-carteira">
      ${renderCarteira(obras)}
    </div>

    <div class="tab-content" id="obras-cronograma">
      ${renderCronograma(obras)}
    </div>
  `;
}

function switchObrasTab(tab, btn) {
  document.querySelectorAll('#view-obras .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#view-obras .tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`obras-${tab}`).classList.add('active');
}

function renderObraForm() {
  const today = new Date().toISOString().split('T')[0];
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">Cadastrar Nova Obra</span></div>
      <div class="card-body">
        <div class="form-grid">
          <div class="form-section-title">Identificação</div>
          <div class="form-group full">
            <label class="form-label">Nome do Empreendimento</label>
            <input type="text" class="form-input" id="obra-nome" placeholder="Ex: Res. Vila Verde">
          </div>
          <div class="form-group full">
            <label class="form-label">Endereço</label>
            <input type="text" class="form-input" id="obra-end" placeholder="Rua, Bairro...">
          </div>

          <div class="form-section-title">Características</div>
          <div class="form-group">
            <label class="form-label">Área Construída m²</label>
            <input type="number" class="form-input" id="obra-area-c" min="0" step="0.01" value="0">
          </div>
          <div class="form-group">
            <label class="form-label">Área Terreno m²</label>
            <input type="number" class="form-input" id="obra-area-t" min="0" step="0.01" value="0">
          </div>
          <div class="form-group">
            <label class="form-label">Quartos</label>
            <input type="number" class="form-input" id="obra-quartos" min="0" step="1" value="0">
          </div>
          <div class="form-group">
            <label class="form-label">Fase</label>
            <select class="form-select" id="obra-status">
              ${STATUS_OBRA.map(s => `<option value="${s}">${s}</option>`).join('')}
            </select>
          </div>

          <div class="form-section-title">Financeiro e Prazos</div>
          <div class="form-group">
            <label class="form-label">Orçamento (Custo)</label>
            <input type="number" class="form-input" id="obra-custo" min="0" step="1000" value="0">
          </div>
          <div class="form-group">
            <label class="form-label">VGV (Venda)</label>
            <input type="number" class="form-input" id="obra-vgv" min="0" step="1000" value="0">
          </div>
          <div class="form-group">
            <label class="form-label">Data Início</label>
            <input type="date" class="form-input" id="obra-data" value="${today}">
          </div>
          <div class="form-group">
            <label class="form-label">Prazo / Entrega</label>
            <input type="text" class="form-input" id="obra-prazo" placeholder="Ex: 12/2026">
          </div>
        </div>
        <div style="margin-top:20px;">
          <button class="btn btn-primary btn-full" onclick="salvarObra()">Salvar Obra</button>
        </div>
      </div>
    </div>
  `;
}

async function salvarObra() {
  const nome = (document.getElementById('obra-nome').value || '').trim();
  const end = (document.getElementById('obra-end').value || '').trim();
  const areaC = parseFloat(document.getElementById('obra-area-c').value) || 0;
  const areaT = parseFloat(document.getElementById('obra-area-t').value) || 0;
  const quartos = parseInt(document.getElementById('obra-quartos').value) || 0;
  const status = document.getElementById('obra-status').value;
  const custo = parseFloat(document.getElementById('obra-custo').value) || 0;
  const vgv = parseFloat(document.getElementById('obra-vgv').value) || 0;
  const dataInicio = document.getElementById('obra-data').value;
  const prazo = (document.getElementById('obra-prazo').value || '').trim();

  // Validate
  const erros = [];
  if (!nome || nome.length < 3) erros.push('Nome deve ter pelo menos 3 caracteres.');
  if (!end) erros.push('Endereço é obrigatório.');
  if (!prazo) erros.push('Prazo é obrigatório.');
  if (vgv <= 0) erros.push('VGV deve ser maior que zero.');
  if (custo <= 0) erros.push('Orçamento deve ser maior que zero.');
  if (areaC <= 0 && areaT <= 0) erros.push('Preencha ao menos uma área.');

  if (erros.length > 0) {
    showToast(erros[0], 'error');
    return;
  }

  showLoading(true);
  try {
    const id = generateId();
    await API.appendObra([id, nome, end, status, vgv, dataInicio, prazo, areaC, areaT, quartos, custo]);
    logAction('CRIAR_OBRA', `ID=${id} | ${nome}`);
    showToast('Obra cadastrada com sucesso!');
    await refreshData();
    renderObras();
  } catch (err) {
    showToast('Erro: ' + err.message, 'error');
  }
  showLoading(false);
}

function renderCarteira(obras) {
  if (obras.length === 0) {
    return '<div class="empty-state"><div class="empty-state-icon">🏢</div><div class="empty-state-text">Nenhuma obra cadastrada</div></div>';
  }

  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title">Carteira de Obras</span>
        <span class="text-sm text-muted">${obras.length} empreendimento(s)</span>
      </div>
      <div class="card-body-flush">
        <div class="table-container">
          <table>
            <thead><tr>
              <th>Empreendimento</th><th>Fase</th><th>Prazo</th>
              <th class="td-right">VGV</th><th class="td-right">Custo</th>
              <th>Área m²</th><th>Qts</th>
              ${canEdit() ? '<th class="td-center">Ações</th>' : ''}
            </tr></thead>
            <tbody>
              ${obras.map(o => {
                const nome = (o.Cliente || '').trim();
                const st = (o.Status || '').trim();
                const stCls = st.toLowerCase() === 'vendida' ? 'status-ok' : st.toLowerCase() === 'concluída' ? 'status-info' : 'status-neutral';
                return `
                <tr>
                  <td class="fw-600">${nome}</td>
                  <td><span class="status-badge ${stCls}">${st}</span></td>
                  <td>${o.Prazo || '—'}</td>
                  <td class="td-right td-mono">${fmtMoeda(o['Valor Total'])}</td>
                  <td class="td-right td-mono">${fmtMoeda(o['Custo Previsto'])}</td>
                  <td>${o['Area Construida'] || 0} / ${o['Area Terreno'] || 0}</td>
                  <td class="td-center">${o.Quartos || 0}</td>
                  ${canEdit() ? `<td class="td-center"><button class="btn-icon" onclick="editarObra('${o.ID}')" title="Editar">✏️</button></td>` : ''}
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function editarObra(id) {
  const obras = window.APP_DATA.obras || [];
  const obra = obras.find(o => String(o.ID) === String(id));
  if (!obra) return;

  openModal('Editar Obra', `
    <div class="form-grid">
      <div class="form-group full">
        <label class="form-label">Nome</label>
        <input type="text" class="form-input" id="edit-obra-nome" value="${obra.Cliente || ''}">
      </div>
      <div class="form-group">
        <label class="form-label">Fase</label>
        <select class="form-select" id="edit-obra-status">
          ${STATUS_OBRA.map(s => `<option value="${s}" ${s === (obra.Status || '') ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Prazo</label>
        <input type="text" class="form-input" id="edit-obra-prazo" value="${obra.Prazo || ''}">
      </div>
      <div class="form-group">
        <label class="form-label">VGV</label>
        <input type="number" class="form-input" id="edit-obra-vgv" value="${safeFloat(obra['Valor Total'])}">
      </div>
      <div class="form-group">
        <label class="form-label">Custo</label>
        <input type="number" class="form-input" id="edit-obra-custo" value="${safeFloat(obra['Custo Previsto'])}">
      </div>
    </div>
  `, `
    <button class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
    <button class="btn btn-primary" onclick="salvarEdicaoObra('${id}')">Salvar</button>
  `);
}

async function salvarEdicaoObra(id) {
  const obras = window.APP_DATA.obras || [];
  const obra = obras.find(o => String(o.ID) === String(id));
  if (!obra) return;

  const novoNome = (document.getElementById('edit-obra-nome').value || '').trim();
  const novoStatus = document.getElementById('edit-obra-status').value;
  const novoPrazo = (document.getElementById('edit-obra-prazo').value || '').trim();
  const novoVgv = parseFloat(document.getElementById('edit-obra-vgv').value) || 0;
  const novoCusto = parseFloat(document.getElementById('edit-obra-custo').value) || 0;

  closeModal();
  showLoading(true);

  try {
    const oldName = (obra.Cliente || '').trim();

    // Rename in financeiro if name changed
    if (novoNome && novoNome !== oldName) {
      await API.renameObra(oldName, novoNome);
      logAction('RENOMEAR_OBRA', `'${oldName}' -> '${novoNome}'`);
    }

    const values = [
      obra.ID, novoNome, obra['Endereço'] || '', novoStatus, novoVgv,
      obra['Data Início'] || '', novoPrazo, obra['Area Construida'] || 0,
      obra['Area Terreno'] || 0, obra.Quartos || 0, novoCusto
    ];
    await API.updateObra(id, values);
    logAction('EDITAR_OBRA', `ID=${id} | ${novoNome}`);

    showToast('Obra atualizada!');
    await refreshData();
    renderObras();
    setTimeout(() => {
      const btn = document.querySelectorAll('#view-obras .tab-btn')[1];
      if (btn) switchObrasTab('carteira', btn);
    }, 100);
  } catch (err) {
    showToast('Erro: ' + err.message, 'error');
  }
  showLoading(false);
}

function renderCronograma(obras) {
  if (obras.length === 0) {
    return '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">Nenhuma obra cadastrada</div></div>';
  }

  return obras.map(o => {
    const nome = (o.Cliente || '').trim();
    const st = (o.Status || 'Projeto').trim();
    const prazo = (o.Prazo || '').trim();
    const idx = STATUS_OBRA.indexOf(st);
    const prog = idx >= 0 ? Math.round((idx / (STATUS_OBRA.length - 1)) * 100) : 0;

    let sColor, sIcon;
    if (st.toLowerCase() === 'concluída' || st.toLowerCase() === 'vendida') {
      sColor = '#168821'; sIcon = '✅';
    } else if (prog >= 50) {
      sColor = '#1351B4'; sIcon = '🔨';
    } else {
      sColor = '#C05E10'; sIcon = '📐';
    }

    const progressCls = prog >= 100 ? 'green' : prog >= 50 ? '' : 'yellow';

    return `
      <div class="card mb-16">
        <div class="card-body">
          <div class="flex-between" style="margin-bottom:12px;">
            <div style="font-size:15px;font-weight:600;">${sIcon} ${nome}</div>
            <span class="status-badge" style="background:${sColor}18;color:${sColor};">${st}</span>
          </div>
          <div class="text-sm text-muted" style="margin-bottom:10px;">Prazo: ${prazo || '—'}</div>
          <div class="progress-bar" style="height:8px;">
            <div class="progress-fill ${progressCls}" style="width:${prog}%;"></div>
          </div>
          <div class="text-sm text-muted" style="margin-top:6px;">
            Etapas: ${STATUS_OBRA.slice(0, (idx >= 0 ? idx : 0) + 1).join(' → ')}
          </div>
        </div>
      </div>
    `;
  }).join('');
}
