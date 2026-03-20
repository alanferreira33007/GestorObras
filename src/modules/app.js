/**
 * App — Inicialização e navegação
 */

window.APP_DATA = { obras: [], financeiro: [] };
window.dashScope = 'all';

// ─── Auth check ───
(function checkAuth() {
  const token = API.getToken();
  if (!token) {
    window.location.href = '/login.html';
    return;
  }
  initApp();
})();

async function initApp() {
  const user = API.getUser();
  if (!user) {
    window.location.href = '/login.html';
    return;
  }

  // Set user info in sidebar
  const nameEl = document.getElementById('user-name');
  const roleEl = document.getElementById('user-role');
  const avatarEl = document.getElementById('user-avatar');

  if (nameEl) nameEl.textContent = user.name || user.id;
  if (roleEl) {
    const roleMap = { admin: 'Administrador', editor: 'Editor', viewer: 'Visualizador' };
    roleEl.textContent = roleMap[user.role] || user.role;
  }
  if (avatarEl) {
    const initials = (user.name || user.id || '--').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
    avatarEl.textContent = initials;
  }

  // Show admin items
  if (canAdmin()) {
    document.querySelectorAll('.admin-section, .admin-btn').forEach(el => {
      el.style.display = '';
    });
  }

  // Load data
  await refreshData();

  // Render dashboard
  renderDashboard();
}

async function refreshData() {
  showLoading(true);
  try {
    const data = await API.fetchData();
    if (data) {
      window.APP_DATA.obras = data.obras || [];
      window.APP_DATA.financeiro = data.financeiro || [];

      // Update badges
      const bdgFin = document.getElementById('bdg-fin');
      if (bdgFin && data.financeiro.length > 0) {
        bdgFin.textContent = data.financeiro.length;
        bdgFin.style.display = '';
      }
      const bdgObras = document.getElementById('bdg-obras');
      if (bdgObras && data.obras.length > 0) {
        bdgObras.textContent = data.obras.length;
        bdgObras.style.display = '';
      }

      // Update sync status
      const syncEl = document.getElementById('sync-status');
      if (syncEl) syncEl.textContent = '🟢 Sincronizado';
    }
  } catch (err) {
    console.error('Refresh error:', err);
    const syncEl = document.getElementById('sync-status');
    if (syncEl) syncEl.textContent = '🔴 Erro de conexão';
    showToast('Erro ao carregar dados', 'error');
  }
  showLoading(false);
}

// ─── Navigation ───
function goView(view, btn) {
  // Update sidebar buttons
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  // Update views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(`view-${view}`);
  if (target) target.classList.add('active');

  // Update title
  const titles = { dashboard: 'Dashboard', financeiro: 'Financeiro', obras: 'Obras', auditoria: 'Auditoria' };
  document.getElementById('page-title').textContent = titles[view] || view;

  // Render content
  if (view === 'dashboard') renderDashboard();
  else if (view === 'financeiro') { renderFinanceiro(); setTimeout(() => applyFinFilters(), 100); }
  else if (view === 'obras') renderObras();
  else if (view === 'auditoria') renderAuditoria();

  // Close mobile sidebar
  closeSidebar();
}

function goViewMobile(view, btn) {
  document.querySelectorAll('.bottom-nav-item').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  // Also update sidebar buttons
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.remove('active');
    if (b.textContent.trim().toLowerCase().includes(view)) b.classList.add('active');
  });

  goView(view, null);
}

// ─── Sidebar toggle ───
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  sidebar.classList.toggle('open');
  backdrop.classList.toggle('open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-backdrop').classList.remove('open');
}

// ─── Logout ───
function logout() {
  localStorage.removeItem('gp_token');
  localStorage.removeItem('gp_user');
  window.location.href = '/login.html';
}

// ─── Parcela info update ───
document.addEventListener('input', (e) => {
  if (e.target.id === 'fin-parcelas' || e.target.id === 'fin-valor') {
    const parcelas = parseInt((document.getElementById('fin-parcelas') || {}).value) || 1;
    const valor = parseFloat((document.getElementById('fin-valor') || {}).value) || 0;
    const info = document.getElementById('fin-parcela-info');
    if (info && parcelas > 1 && valor > 0) {
      info.innerHTML = `💳 ${parcelas}x de <strong>${fmtMoeda(valor / parcelas)}</strong>`;
    } else if (info) {
      info.innerHTML = '';
    }
  }
});
