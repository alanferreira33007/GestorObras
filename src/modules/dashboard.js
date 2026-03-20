/**
 * Dashboard Module
 */

let chartEvolucao = null;
let chartCategoria = null;
let chartMensal = null;

function renderDashboard() {
  const container = document.getElementById('view-dashboard');
  const obras = window.APP_DATA.obras || [];
  const fin = window.APP_DATA.financeiro || [];

  if (obras.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🏗️</div>
        <div class="empty-state-text">Nenhuma obra cadastrada</div>
        <div class="empty-state-sub">Cadastre sua primeira obra para começar</div>
      </div>`;
    return;
  }

  // Scope selector
  const obraNames = [...new Set(obras.map(o => (o.Cliente || '').trim()))].filter(Boolean).sort();
  const scope = window.dashScope || 'all';

  // Filter despesas
  let despesas = fin.filter(f => String(f.Tipo || '').match(/Saída|Despesa/i));
  if (scope !== 'all') {
    despesas = despesas.filter(f => (f['Obra Vinculada'] || '').trim() === scope);
  }

  // Calculate KPIs
  let vgv = 0, custos = 0, lucro = 0, roi = 0;

  if (scope === 'all') {
    vgv = obras.reduce((s, o) => s + safeFloat(o['Valor Total']), 0);
    custos = despesas.reduce((s, f) => s + safeFloat(f.Valor), 0);
  } else {
    const obra = obras.find(o => (o.Cliente || '').trim() === scope);
    vgv = obra ? safeFloat(obra['Valor Total']) : 0;
    custos = despesas.reduce((s, f) => s + safeFloat(f.Valor), 0);
  }

  lucro = vgv - custos;
  roi = custos > 0 ? (lucro / custos * 100) : 0;
  const perc = vgv > 0 ? (custos / vgv * 100) : 0;

  // Prazo alerts
  let alertsHtml = '';
  const hoje = new Date();
  obras.forEach(o => {
    const status = (o.Status || '').trim().toLowerCase();
    if (status === 'concluída' || status === 'vendida') return;
    const prazoStr = (o.Prazo || '').trim();
    if (!prazoStr) return;
    let prazoDate = null;
    // Try MM/YYYY
    const m1 = prazoStr.match(/^(\d{1,2})\/(\d{4})$/);
    if (m1) prazoDate = new Date(parseInt(m1[2]), parseInt(m1[1]) - 1, 28);
    // Try YYYY-MM-DD
    if (!prazoDate) { const d = new Date(prazoStr); if (!isNaN(d)) prazoDate = d; }

    if (prazoDate) {
      const dias = Math.floor((prazoDate - hoje) / 86400000);
      const nome = (o.Cliente || '').trim();
      if (dias < 0) {
        alertsHtml += `<div class="alert alert-danger">🚨 <strong>${nome}</strong> — Prazo vencido há ${Math.abs(dias)} dias!</div>`;
      } else if (dias <= 30) {
        alertsHtml += `<div class="alert alert-warning">⏰ <strong>${nome}</strong> — Vence em ${dias} dias</div>`;
      }
    }
  });

  // Status for single obra
  let kpi3Label = 'LUCRO', kpi3Value = fmtMoeda(lucro), kpi3Icon = '📊', kpi3Bg = '#E4F7E8', kpi3Color = '#168821';
  let kpi4Label = 'ROI', kpi4Value = `${roi.toFixed(1)}%`, kpi4Icon = '🎯', kpi4Bg = '#EDE4F7', kpi4Color = '#6940A5';

  if (scope !== 'all') {
    const obra = obras.find(o => (o.Cliente || '').trim() === scope);
    const st = obra ? (obra.Status || '').trim() : '';
    if (st.toLowerCase() !== 'vendida') {
      kpi3Label = 'FASE'; kpi3Value = st || '—'; kpi3Icon = '🔨'; kpi3Bg = '#F0F2F5'; kpi3Color = '#474A57';
      kpi4Label = 'SALDO'; kpi4Value = fmtMoeda(lucro); kpi4Icon = '💵'; kpi4Bg = '#E4F7E8'; kpi4Color = '#168821';
    }
  }

  container.innerHTML = `
    <!-- Scope selector -->
    <div class="flex-between mb-16">
      <select class="form-select" style="max-width:300px;" onchange="window.dashScope=this.value;renderDashboard()">
        <option value="all" ${scope === 'all' ? 'selected' : ''}>Todas as Obras</option>
        ${obraNames.map(n => `<option value="${n}" ${n === scope ? 'selected' : ''}>${n}</option>`).join('')}
      </select>
    </div>

    ${alertsHtml}

    <!-- KPIs -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#D4E5FF;color:#1351B4;">💰</div>
        <div class="kpi-info">
          <div class="kpi-label">VGV TOTAL</div>
          <div class="kpi-value">${fmtMoeda(vgv)}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#FFF0E0;color:#C05E10;">📉</div>
        <div class="kpi-info">
          <div class="kpi-label">CUSTOS (${perc.toFixed(0)}%)</div>
          <div class="kpi-value">${fmtMoeda(custos)}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:${kpi3Bg};color:${kpi3Color};">${kpi3Icon}</div>
        <div class="kpi-info">
          <div class="kpi-label">${kpi3Label}</div>
          <div class="kpi-value">${kpi3Value}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:${kpi4Bg};color:${kpi4Color};">${kpi4Icon}</div>
        <div class="kpi-info">
          <div class="kpi-label">${kpi4Label}</div>
          <div class="kpi-value">${kpi4Value}</div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button class="tab-btn active" onclick="switchDashTab('charts',this)">📈 Gráficos</button>
      <button class="tab-btn" onclick="switchDashTab('fornec',this)">🏢 Fornecedores</button>
      <button class="tab-btn" onclick="switchDashTab('resumo',this)">📋 Resumo Obras</button>
    </div>

    <div class="tab-content active" id="dash-charts">
      <div class="charts-grid">
        <div class="card">
          <div class="card-header"><span class="card-title">Evolução Acumulada</span></div>
          <div class="card-body"><div class="chart-container"><canvas id="chart-evolucao"></canvas></div></div>
        </div>
        <div class="card">
          <div class="card-header"><span class="card-title">Por Categoria</span></div>
          <div class="card-body"><div class="chart-container"><canvas id="chart-categoria"></canvas></div></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Gastos Mensais</span></div>
        <div class="card-body"><div class="chart-container"><canvas id="chart-mensal"></canvas></div></div>
      </div>
    </div>

    <div class="tab-content" id="dash-fornec">
      <div class="card" id="fornec-card"></div>
    </div>

    <div class="tab-content" id="dash-resumo">
      <div class="card" id="resumo-card"></div>
    </div>

    <!-- Atividade recente -->
    <div class="divider"></div>
    <p class="text-overline mb-16">Atividade Recente</p>
    <div id="atividade-recente"></div>
  `;

  // Build charts
  buildCharts(despesas);
  buildFornecedores(despesas);
  buildResumo(obras, despesas);
  buildAtividade(fin);
}

function switchDashTab(tab, btn) {
  document.querySelectorAll('#view-dashboard .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#view-dashboard .tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`dash-${tab}`).classList.add('active');
}

function buildCharts(despesas) {
  // Destroy existing
  [chartEvolucao, chartCategoria, chartMensal].forEach(c => { if (c) c.destroy(); });

  if (despesas.length === 0) return;

  // Sort by date
  const sorted = [...despesas].sort((a, b) => new Date(a.Data) - new Date(b.Data));

  // Evolução acumulada
  let acc = 0;
  const labels = sorted.map(d => fmtDate(d.Data));
  const values = sorted.map(d => { acc += safeFloat(d.Valor); return acc; });

  const ctx1 = document.getElementById('chart-evolucao');
  if (ctx1) {
    chartEvolucao = new Chart(ctx1, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: '#1351B4',
          backgroundColor: 'rgba(19,81,180,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#F0F2F5' }, ticks: { font: { size: 10 } } },
          y: { grid: { color: '#F0F2F5' }, ticks: { font: { size: 10 } } },
        }
      }
    });
  }

  // Categorias
  const catMap = {};
  despesas.forEach(d => {
    const c = (d.Categoria || 'Outros').trim();
    catMap[c] = (catMap[c] || 0) + safeFloat(d.Valor);
  });
  const catColors = ['#1351B4', '#168821', '#C05E10', '#CC2936', '#6940A5', '#0A6E5C', '#71747E'];

  const ctx2 = document.getElementById('chart-categoria');
  if (ctx2) {
    chartCategoria = new Chart(ctx2, {
      type: 'doughnut',
      data: {
        labels: Object.keys(catMap),
        datasets: [{ data: Object.values(catMap), backgroundColor: catColors, borderWidth: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: { position: 'bottom', labels: { font: { size: 11, family: 'Inter' }, padding: 12, usePointStyle: true } },
        }
      }
    });
  }

  // Mensal
  const mesMap = {};
  despesas.forEach(d => {
    const dt = new Date(d.Data);
    if (isNaN(dt)) return;
    const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`;
    mesMap[key] = (mesMap[key] || 0) + safeFloat(d.Valor);
  });
  const meses = Object.keys(mesMap).sort();

  const ctx3 = document.getElementById('chart-mensal');
  if (ctx3) {
    chartMensal = new Chart(ctx3, {
      type: 'bar',
      data: {
        labels: meses,
        datasets: [{
          data: meses.map(m => mesMap[m]),
          backgroundColor: '#1351B4',
          borderRadius: 4,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
          y: { grid: { color: '#F0F2F5' }, ticks: { font: { size: 10 } } },
        }
      }
    });
  }
}

function buildFornecedores(despesas) {
  const card = document.getElementById('fornec-card');
  if (!card) return;
  const fornMap = {};
  despesas.forEach(d => {
    const f = (d.Fornecedor || '').trim();
    if (!f) return;
    fornMap[f] = (fornMap[f] || 0) + safeFloat(d.Valor);
  });

  const sorted = Object.entries(fornMap).sort((a, b) => b[1] - a[1]).slice(0, 10);

  if (sorted.length === 0) {
    card.innerHTML = '<div class="card-body"><div class="empty-state"><div class="empty-state-icon">🏢</div><div class="empty-state-text">Nenhum fornecedor registrado</div></div></div>';
    return;
  }

  const maxVal = sorted[0][1];
  card.innerHTML = `
    <div class="card-header"><span class="card-title">Top 10 Fornecedores</span></div>
    <div class="card-body">
      ${sorted.map(([name, val]) => `
        <div style="margin-bottom:12px;">
          <div class="flex-between" style="margin-bottom:4px;">
            <span style="font-size:13px;font-weight:500;">${name}</span>
            <span class="td-mono" style="font-size:13px;">${fmtMoeda(val)}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width:${(val/maxVal*100).toFixed(0)}%"></div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function buildResumo(obras, despesas) {
  const card = document.getElementById('resumo-card');
  if (!card) return;

  const rows = obras.map(o => {
    const nome = (o.Cliente || '').trim();
    const cp = safeFloat(o['Custo Previsto']);
    const gasto = despesas.filter(d => (d['Obra Vinculada'] || '').trim() === nome).reduce((s, d) => s + safeFloat(d.Valor), 0);
    const perc = cp > 0 ? (gasto / cp * 100) : 0;
    const s = cp > 0 ? saude(perc) : { label: 'Sem orç.', cls: 'status-neutral', icon: '⚪' };
    const saldo = cp - gasto;

    return { nome, fase: o.Status || '', saude: s, orcado: cp, realizado: gasto, saldo, perc };
  });

  card.innerHTML = `
    <div class="card-header"><span class="card-title">Orçado vs Realizado</span></div>
    <div class="card-body-flush">
      <div class="table-container">
        <table>
          <thead><tr>
            <th>Obra</th><th>Fase</th><th>Saúde</th><th class="td-right">Orçado</th><th class="td-right">Realizado</th><th class="td-right">Saldo</th><th style="width:100px">Exec.</th>
          </tr></thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td class="fw-600">${r.nome}</td>
                <td>${r.fase}</td>
                <td><span class="status-badge ${r.saude.cls}">${r.saude.icon} ${r.saude.label}</span></td>
                <td class="td-right td-mono">${fmtMoeda(r.orcado)}</td>
                <td class="td-right td-mono">${fmtMoeda(r.realizado)}</td>
                <td class="td-right td-mono">${fmtMoeda(r.saldo)}</td>
                <td>
                  <div class="progress-bar">
                    <div class="progress-fill ${r.perc > 100 ? 'red' : r.perc > 80 ? 'yellow' : 'green'}" style="width:${Math.min(r.perc, 100).toFixed(0)}%"></div>
                  </div>
                  <span class="text-sm text-muted">${r.perc.toFixed(0)}%</span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function buildAtividade(fin) {
  const el = document.getElementById('atividade-recente');
  if (!el) return;

  const sorted = [...fin].sort((a, b) => new Date(b.Data) - new Date(a.Data)).slice(0, 5);

  if (sorted.length === 0) {
    el.innerHTML = '<p class="text-sm text-muted">Nenhuma atividade registrada.</p>';
    return;
  }

  el.innerHTML = sorted.map(r => {
    const icon = String(r.Tipo || '').match(/Saída|Despesa/i) ? '🔴' : '🟢';
    return `<p class="text-sm text-muted" style="margin-bottom:6px;">${icon} ${fmtDate(r.Data)} — ${(r['Descrição'] || '').substring(0, 40)} | <strong>${fmtMoeda(r.Valor)}</strong></p>`;
  }).join('');
}
