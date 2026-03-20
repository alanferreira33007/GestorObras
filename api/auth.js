/**
 * API de Autenticação — Vercel Serverless Function
 * POST /api/auth { username, password } → { token, user }
 */
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'gestor-pro-secret-2026';
const TOKEN_EXPIRY = '24h';

function getUsers() {
  try {
    return JSON.parse(process.env.APP_USERS || '{}');
  } catch {
    return {};
  }
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const { username, password } = req.body || {};
    if (!password) return res.status(400).json({ error: 'Senha obrigatória' });

    const users = getUsers();
    let matched = null;

    if (username) {
      const u = users[username];
      if (u && u.password === password) {
        matched = { id: username, name: u.name || username, role: u.role || 'admin' };
      }
    } else {
      for (const [uid, udata] of Object.entries(users)) {
        const pwd = typeof udata === 'object' ? udata.password : String(udata);
        if (pwd === password) {
          matched = {
            id: uid,
            name: (typeof udata === 'object' ? udata.name : uid) || uid,
            role: (typeof udata === 'object' ? udata.role : 'admin') || 'admin'
          };
          break;
        }
      }
    }

    if (!matched) return res.status(401).json({ error: 'Credenciais incorretas' });

    const token = jwt.sign(
      { id: matched.id, name: matched.name, role: matched.role },
      JWT_SECRET,
      { expiresIn: TOKEN_EXPIRY }
    );

    return res.status(200).json({ token, user: matched });
  } catch (err) {
    console.error('Auth error:', err);
    return res.status(500).json({ error: 'Erro interno' });
  }
};

module.exports.verifyToken = (token) => {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
};
