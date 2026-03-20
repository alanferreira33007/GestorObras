/**
 * API CRUD Google Sheets — Vercel Serverless Function
 *
 * GET  /api/sheets?action=fetch          → { obras: [], financeiro: [] }
 * GET  /api/sheets?action=audit          → { audit: [] }
 * POST /api/sheets { action: 'append_fin', values: [...] }
 * POST /api/sheets { action: 'update_fin', id, values: [...] }
 * POST /api/sheets { action: 'delete_fin', ids: [...] }
 * POST /api/sheets { action: 'append_obra', values: [...] }
 * POST /api/sheets { action: 'update_obra', id, values: [...] }
 * POST /api/sheets { action: 'rename_obra', oldName, newName }
 * POST /api/sheets { action: 'log_audit', entry: [...] }
 */
const { google } = require('googleapis');

const SPREADSHEET_NAME = 'GestorObras_DB';
let sheetsClient = null;
let spreadsheetId = null;

async function getClient() {
  if (sheetsClient) return sheetsClient;

  const creds = JSON.parse(process.env.GCP_CREDENTIALS || '{}');
  const auth = new google.auth.GoogleAuth({
    credentials: creds,
    scopes: ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'],
  });
  sheetsClient = google.sheets({ version: 'v4', auth });

  // Find spreadsheet by name
  const drive = google.drive({ version: 'v3', auth });
  const res = await drive.files.list({
    q: `name='${SPREADSHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`,
    fields: 'files(id)',
  });
  if (res.data.files.length === 0) throw new Error('Spreadsheet não encontrada');
  spreadsheetId = res.data.files[0].id;

  return sheetsClient;
}

function verifyAuth(req) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) return null;
  const token = authHeader.split(' ')[1];
  try {
    const jwt = require('jsonwebtoken');
    const JWT_SECRET = process.env.JWT_SECRET || 'gestor-pro-secret-2026';
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

async function getSheetData(sheetName) {
  const client = await getClient();
  const res = await client.spreadsheets.values.get({
    spreadsheetId,
    range: `${sheetName}!A:Z`,
  });
  const rows = res.data.values || [];
  if (rows.length < 2) return { headers: rows[0] || [], data: [] };
  const headers = rows[0];
  const data = rows.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = row[i] || ''; });
    return obj;
  });
  return { headers, data };
}

async function appendRow(sheetName, values) {
  const client = await getClient();
  await client.spreadsheets.values.append({
    spreadsheetId,
    range: `${sheetName}!A:Z`,
    valueInputOption: 'USER_ENTERED',
    requestBody: { values: [values] },
  });
}

async function findRowById(sheetName, id, idColIndex = 0) {
  const client = await getClient();
  const res = await client.spreadsheets.values.get({
    spreadsheetId,
    range: `${sheetName}!A:Z`,
  });
  const rows = res.data.values || [];
  for (let i = 1; i < rows.length; i++) {
    if (String(rows[i][idColIndex]) === String(id)) return i + 1; // 1-based
  }
  return null;
}

async function updateRow(sheetName, rowNum, values, numCols) {
  const client = await getClient();
  const endCol = String.fromCharCode(64 + numCols);
  await client.spreadsheets.values.update({
    spreadsheetId,
    range: `${sheetName}!A${rowNum}:${endCol}${rowNum}`,
    valueInputOption: 'USER_ENTERED',
    requestBody: { values: [values] },
  });
}

async function deleteRows(sheetName, rowNums) {
  const client = await getClient();
  // Get sheetId
  const meta = await client.spreadsheets.get({ spreadsheetId });
  const sheet = meta.data.sheets.find(s => s.properties.title === sheetName);
  if (!sheet) return;
  const sheetId = sheet.properties.sheetId;

  // Delete from bottom to top
  const sorted = [...rowNums].sort((a, b) => b - a);
  const requests = sorted.map(r => ({
    deleteDimension: {
      range: { sheetId, dimension: 'ROWS', startIndex: r - 1, endIndex: r }
    }
  }));
  await client.spreadsheets.batchUpdate({
    spreadsheetId,
    requestBody: { requests },
  });
}

async function renameInColumn(sheetName, colIndex, oldVal, newVal) {
  const client = await getClient();
  const res = await client.spreadsheets.values.get({
    spreadsheetId,
    range: `${sheetName}!A:Z`,
  });
  const rows = res.data.values || [];
  let count = 0;
  const updates = [];
  for (let i = 1; i < rows.length; i++) {
    if (rows[i][colIndex] === oldVal) {
      const col = String.fromCharCode(65 + colIndex);
      updates.push({
        range: `${sheetName}!${col}${i + 1}`,
        values: [[newVal]],
      });
      count++;
    }
  }
  if (updates.length > 0) {
    await client.spreadsheets.values.batchUpdate({
      spreadsheetId,
      requestBody: { valueInputOption: 'USER_ENTERED', data: updates },
    });
  }
  return count;
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();

  const user = verifyAuth(req);
  if (!user) return res.status(401).json({ error: 'Não autorizado' });

  try {
    // GET requests
    if (req.method === 'GET') {
      const action = req.query.action || 'fetch';

      if (action === 'fetch') {
        const [obras, fin] = await Promise.all([
          getSheetData('Obras'),
          getSheetData('Financeiro'),
        ]);
        return res.status(200).json({
          obras: obras.data,
          obrasHeaders: obras.headers,
          financeiro: fin.data,
          finHeaders: fin.headers,
        });
      }

      if (action === 'audit') {
        const audit = await getSheetData('Auditoria');
        return res.status(200).json({ audit: audit.data });
      }

      return res.status(400).json({ error: 'Ação inválida' });
    }

    // POST requests
    if (req.method === 'POST') {
      const { action } = req.body;
      const roleHierarchy = { viewer: 0, editor: 1, admin: 2 };
      const userLevel = roleHierarchy[user.role] || 0;

      if (action === 'append_fin') {
        if (userLevel < 1) return res.status(403).json({ error: 'Sem permissão' });
        await appendRow('Financeiro', req.body.values);
        return res.status(200).json({ ok: true });
      }

      if (action === 'update_fin') {
        if (userLevel < 1) return res.status(403).json({ error: 'Sem permissão' });
        const rowNum = await findRowById('Financeiro', req.body.id);
        if (!rowNum) return res.status(404).json({ error: 'Registro não encontrado' });
        await updateRow('Financeiro', rowNum, req.body.values, req.body.values.length);
        return res.status(200).json({ ok: true });
      }

      if (action === 'delete_fin') {
        if (userLevel < 2) return res.status(403).json({ error: 'Sem permissão' });
        const rowNums = [];
        for (const id of req.body.ids) {
          const r = await findRowById('Financeiro', id);
          if (r) rowNums.push(r);
        }
        if (rowNums.length > 0) await deleteRows('Financeiro', rowNums);
        return res.status(200).json({ ok: true, deleted: rowNums.length });
      }

      if (action === 'append_obra') {
        if (userLevel < 1) return res.status(403).json({ error: 'Sem permissão' });
        await appendRow('Obras', req.body.values);
        return res.status(200).json({ ok: true });
      }

      if (action === 'update_obra') {
        if (userLevel < 1) return res.status(403).json({ error: 'Sem permissão' });
        const rowNum = await findRowById('Obras', req.body.id);
        if (!rowNum) return res.status(404).json({ error: 'Registro não encontrado' });
        await updateRow('Obras', rowNum, req.body.values, req.body.values.length);
        return res.status(200).json({ ok: true });
      }

      if (action === 'rename_obra') {
        if (userLevel < 1) return res.status(403).json({ error: 'Sem permissão' });
        const { headers } = await getSheetData('Financeiro');
        const colIdx = headers.indexOf('Obra Vinculada');
        if (colIdx >= 0) {
          const count = await renameInColumn('Financeiro', colIdx, req.body.oldName, req.body.newName);
          return res.status(200).json({ ok: true, updated: count });
        }
        return res.status(200).json({ ok: true, updated: 0 });
      }

      if (action === 'log_audit') {
        await appendRow('Auditoria', req.body.entry);
        return res.status(200).json({ ok: true });
      }

      return res.status(400).json({ error: 'Ação inválida' });
    }

    return res.status(405).json({ error: 'Method not allowed' });
  } catch (err) {
    console.error('Sheets API error:', err);
    return res.status(500).json({ error: 'Erro ao acessar planilha', details: err.message });
  }
};
