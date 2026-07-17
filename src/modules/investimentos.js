/**
 * Investimentos Module — Monitoramento de ETFs
 */

const INVEST_GRUPOS = [
  { id: 'rv-br', titulo: '🇧🇷 Renda Variável — Brasil' },
  { id: 'rv-ext', titulo: '🌎 Renda Variável — Exterior' },
  { id: 'rf', titulo: '🪙 Renda Fixa, Moeda e Commodities' },
];

const INVEST_ATIVOS = [
  { ticker: 'BOVA11', nome: 'Ibovespa', grupo: 'rv-br' },
  { ticker: 'BRAX11', nome: 'IBrX-100', grupo: 'rv-br' },
  { ticker: 'DIVO11', nome: 'Dividendos (IDIV)', grupo: 'rv-br' },
  { ticker: 'NASD11', nome: 'Nasdaq-100', grupo: 'rv-ext' },
  { ticker: 'WRLD11', nome: 'MSCI World', grupo: 'rv-ext' },
  { ticker: 'BIVE39', nome: 'S&P 500 Value (BDR)', grupo: 'rv-ext' },
  { ticker: 'LFTB11', nome: 'Tesouro Selic', grupo: 'rf' },
  { ticker: 'DEBB11', nome: 'Debêntures', grupo: 'rf' },
  { ticker: 'CPTI11', nome: 'Infraestrutura', grupo: 'rf' },
  { ticker: 'USDB11', nome: 'Renda Fixa Americana (USD)', grupo: 'rf' },
  { ticker: 'BNDX11', nome: 'Renda Fixa Americana', grupo: 'rf' },
  { ticker: 'GOLD11', nome: 'Ouro', grupo: 'rf' },
];

const INVEST_REFRESH_MS = 5 * 60 * 1000;

let investQuotes = {};        // ticker → quote
let investUpdatedAt = null;
let investTimer = null;
let investLoading = false;
let investSparks = {};        // ticker → Chart

function fmtPreco(v) {
  if (v == null || isNaN(v)) return '—';
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function fmtPct(v) {
  if (v == null || isNaN(v)) return '—';
  const s = Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${s}%`;
}

function pctChip(v) {
  if (v == null || isNaN(v)) return '<span class="quote-chip flat">—</span>';
  const cls = v > 0.005 ? 'up' : v < -0.005 ? 'down' : 'flat';
  const arrow = cls === 'up' ? '▲' : cls === 'down' ? '▼' : '•';
  return `<span class="quote-chip ${cls}">${arrow} ${fmtPct(v)}</span>`;
}

function renderInvestimentos() {
  const container = document.getElementById('view-investimentos');
  if (!container) return;

  const quotes = INVEST_ATIVOS.map(a => ({ ...a, q: investQuotes[a.ticker] || null }));
  const valid = quotes.filter(x => x.q && !x.q.error);

  // KPIs do dia
  const emAlta = valid.filter(x => x.q.changePct > 0.005).length;
  const emBaixa = valid.filter(x => x.q.changePct < -0.005).length;
  const sorted = [...valid].sort((a, b) => b.q.changePct - a.q.changePct);
  const maiorAlta = sorted.length ? sorted[0] : null;
  const maiorBaixa = sorted.length ? sorted[sorted.length - 1] : null;

  const updatedStr = investUpdatedAt
    ? new Date(investUpdatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : '—';

  container.innerHTML = `
    <div class="flex-between mb-16" style="flex-wrap:wrap;gap:8px;">
      <span class="invest-updated">📡 Cotações com atraso · Atualizado às <strong>${updatedStr}</strong></span>
      <button class="btn btn-secondary" onclick="loadInvestimentos(true)" ${investLoading ? 'disabled' : ''}>
        ${investLoading ? '⏳ Atualizando...' : '🔄 Atualizar cotações'}
      </button>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#E4F7E8;color:#168821;">📈</div>
        <div class="kpi-info">
          <div class="kpi-label">EM ALTA HOJE</div>
          <div class="kpi-value">${valid.length ? emAlta : '—'}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#FDE8EA;color:#CC2936;">📉</div>
        <div class="kpi-info">
          <div class="kpi-label">EM BAIXA HOJE</div>
          <div class="kpi-value">${valid.length ? emBaixa : '—'}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#D4E5FF;color:#1351B4;">🏆</div>
        <div class="kpi-info">
          <div class="kpi-label">MAIOR ALTA${maiorAlta ? ` — ${maiorAlta.ticker}` : ''}</div>
          <div class="kpi-value">${maiorAlta ? fmtPct(maiorAlta.q.changePct) : '—'}</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:#FFF0E0;color:#C05E10;">⚠️</div>
        <div class="kpi-info">
          <div class="kpi-label">MAIOR BAIXA${maiorBaixa ? ` — ${maiorBaixa.ticker}` : ''}</div>
          <div class="kpi-value">${maiorBaixa ? fmtPct(maiorBaixa.q.changePct) : '—'}</div>
        </div>
      </div>
    </div>

    ${INVEST_GRUPOS.map(g => {
      const ativos = quotes.filter(x => x.grupo === g.id);
      return `
      <div class="card mb-16">
        <div class="card-header"><span class="card-title">${g.titulo}</span></div>
        <div class="card-body-flush">
          <div class="table-container">
            <table>
              <thead><tr>
                <th>Ativo</th>
                <th class="td-right">Cotação</th>
                <th class="td-right">Dia</th>
                <th class="td-right">30 dias</th>
                <th style="width:130px;">Tendência 30d</th>
              </tr></thead>
              <tbody>
                ${ativos.map(x => investRowHtml(x)).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>`;
    }).join('')}

    <p class="text-sm text-muted">
      Fonte: Yahoo Finance (B3, atraso de até 15 min). Atualização automática a cada 5 minutos enquanto esta tela estiver aberta.
    </p>
  `;

  buildInvestSparks(valid);
}

function investRowHtml(x) {
  const q = x.q;
  if (!q) {
    return `
      <tr>
        <td><span class="fw-600">${x.ticker}</span><br><span class="text-sm text-muted">${x.nome}</span></td>
        <td class="td-right td-mono text-muted" colspan="4">${investLoading ? 'Carregando...' : 'Sem dados'}</td>
      </tr>`;
  }
  if (q.error) {
    return `
      <tr>
        <td><span class="fw-600">${x.ticker}</span><br><span class="text-sm text-muted">${x.nome}</span></td>
        <td class="td-right td-mono text-muted" colspan="4">⚠️ Indisponível</td>
      </tr>`;
  }
  return `
    <tr>
      <td><span class="fw-600">${x.ticker}</span><br><span class="text-sm text-muted">${x.nome}</span></td>
      <td class="td-right td-mono fw-600">${fmtPreco(q.price)}</td>
      <td class="td-right">${pctChip(q.changePct)}</td>
      <td class="td-right">${pctChip(q.monthChangePct)}</td>
      <td><canvas id="spark-${x.ticker}" width="120" height="36"></canvas></td>
    </tr>`;
}

function buildInvestSparks(valid) {
  if (typeof Chart === 'undefined') return;
  Object.values(investSparks).forEach(c => { try { c.destroy(); } catch {} });
  investSparks = {};

  valid.forEach(x => {
    const canvas = document.getElementById(`spark-${x.ticker}`);
    const hist = (x.q.history || []).filter(v => v != null);
    if (!canvas || hist.length < 2) return;

    const up = hist[hist.length - 1] >= hist[0];
    investSparks[x.ticker] = new Chart(canvas, {
      type: 'line',
      data: {
        labels: hist.map((_, i) => i),
        datasets: [{
          data: hist,
          borderColor: up ? '#168821' : '#CC2936',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
          fill: false,
        }],
      },
      options: {
        responsive: false,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
      },
    });
  });
}

async function loadInvestimentos(force = false) {
  if (investLoading) return;

  const fresh = investUpdatedAt && Date.now() - investUpdatedAt < INVEST_REFRESH_MS;
  if (fresh && !force) {
    renderInvestimentos();
    scheduleInvestRefresh();
    return;
  }

  investLoading = true;
  renderInvestimentos();

  try {
    const data = await API.fetchQuotes(force);
    if (data && data.quotes) {
      investQuotes = {};
      data.quotes.forEach(q => { investQuotes[q.ticker] = q; });
      investUpdatedAt = data.updatedAt || Date.now();
      if (data.okCount === 0) showToast('Não foi possível obter cotações agora', 'error');
    } else if (data && data.error) {
      showToast(data.error, 'error');
    }
  } catch (err) {
    console.error('Quotes error:', err);
    showToast('Erro ao buscar cotações', 'error');
  }

  investLoading = false;
  renderInvestimentos();
  scheduleInvestRefresh();
}

function scheduleInvestRefresh() {
  if (investTimer) clearInterval(investTimer);
  investTimer = setInterval(() => {
    const view = document.getElementById('view-investimentos');
    if (!view || !view.classList.contains('active')) {
      clearInterval(investTimer);
      investTimer = null;
      return;
    }
    loadInvestimentos(true);
  }, INVEST_REFRESH_MS);
}
