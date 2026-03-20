/**
 * Utilitários globais
 */

const CATS = ['Material', 'Mão de Obra', 'Serviços', 'Administrativo', 'Impostos', 'Emolumentos Cartorários', 'Outros'];
const PAGAMENTOS = ['PIX', 'Cartão de Crédito', 'Cartão de Débito', 'Dinheiro', 'Transferência', 'Boleto', 'Cheque', 'Outro'];
const STATUS_OBRA = ['Projeto', 'Fundação', 'Alvenaria', 'Acabamento', 'Concluída', 'Vendida'];

function fmtMoeda(valor) {
  if (valor === null || valor === undefined || valor === '') return 'R$ 0,00';
  const v = parseFloat(String(valor).replace(/[R$\s.]/g, '').replace(',', '.')) || 0;
  const neg = v < 0;
  const abs = Math.abs(v);
  const inteiro = Math.floor(abs);
  const decimal = Math.round((abs - inteiro) * 100);
  const s = inteiro.toLocaleString('pt-BR');
  return `R$ ${neg ? '-' : ''}${s},${String(decimal).padStart(2, '0')}`;
}

function safeFloat(x) {
  if (typeof x === 'number') return x;
  if (!x) return 0;
  const s = String(x).replace(/[R$\s.]/g, '').replace(',', '.');
  return parseFloat(s) || 0;
}

function fmtDate(d) {
  if (!d) return '';
  const dt = new Date(d);
  if (isNaN(dt)) return String(d).substring(0, 10);
  return dt.toLocaleDateString('pt-BR');
}

function toISODate(d) {
  if (!d) return '';
  if (d instanceof Date) {
    return d.toISOString().split('T')[0];
  }
  return String(d).substring(0, 10);
}

function generateId() {
  return Math.floor(Date.now() % 1000000000);
}

function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function showLoading(show = true) {
  const el = document.getElementById('loading-overlay');
  if (show) el.classList.add('active');
  else el.classList.remove('active');
}

function openModal(title, bodyHtml, footerHtml = '') {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  document.getElementById('modal-footer').innerHTML = footerHtml;
  document.getElementById('modal-backdrop').classList.add('active');
  document.getElementById('modal').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-backdrop').classList.remove('active');
  document.getElementById('modal').classList.remove('active');
}

function buildOptions(arr, selected = '') {
  return arr.map(v =>
    `<option value="${v}" ${v === selected ? 'selected' : ''}>${v}</option>`
  ).join('');
}

function saude(perc) {
  if (perc > 100) return { label: 'Estourado', cls: 'status-err', icon: '🔴' };
  if (perc > 80) return { label: 'Atenção', cls: 'status-warn', icon: '🟡' };
  return { label: 'OK', cls: 'status-ok', icon: '🟢' };
}

function roleLevel(role) {
  return { viewer: 0, editor: 1, admin: 2 }[role] || 0;
}

function canEdit() {
  const user = API.getUser();
  return user && roleLevel(user.role) >= 1;
}

function canAdmin() {
  const user = API.getUser();
  return user && roleLevel(user.role) >= 2;
}

function logAction(action, details = '') {
  const user = API.getUser();
  const ts = new Date().toLocaleString('pt-BR');
  API.logAudit([ts, user ? user.name : 'Sistema', action, details.substring(0, 500)]).catch(() => {});
}
