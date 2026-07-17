/**
 * API Cotações de ETFs — Vercel Serverless Function
 *
 * GET /api/quotes → { updatedAt, quotes: [ { ticker, price, changePct, monthChangePct, history, ... } ] }
 *
 * Fonte primária: Yahoo Finance (sufixo .SA, sem chave).
 * Fallback: brapi.dev (se BRAPI_TOKEN estiver configurado).
 * Cache em memória de 5 min + cache de CDN (s-maxage).
 */

const TICKERS = [
  'BOVA11', 'BRAX11', 'DIVO11',          // Renda variável Brasil
  'NASD11', 'WRLD11', 'BIVE39',          // Renda variável exterior
  'LFTB11', 'DEBB11', 'CPTI11',          // Renda fixa
  'USDB11', 'BNDX11', 'GOLD11',          // Renda fixa americana / ouro
];

const CACHE_TTL_MS = 5 * 60 * 1000;
let cache = { at: 0, payload: null };

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

async function fetchYahoo(ticker) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}.SA?range=1mo&interval=1d`;
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; GestorPro/1.0)' },
  });
  if (!res.ok) throw new Error(`Yahoo HTTP ${res.status}`);
  const json = await res.json();
  const r = json.chart && json.chart.result && json.chart.result[0];
  if (!r) throw new Error('Yahoo: sem dados');

  const meta = r.meta || {};
  const ts = r.timestamp || [];
  const closes = (((r.indicators || {}).quote || [])[0] || {}).close || [];
  const points = [];
  for (let i = 0; i < ts.length; i++) {
    if (closes[i] != null) points.push({ t: ts[i] * 1000, c: closes[i] });
  }

  const price = meta.regularMarketPrice != null
    ? meta.regularMarketPrice
    : (points.length ? points[points.length - 1].c : null);
  if (price == null) throw new Error('Yahoo: sem preço');

  // Fechamento anterior: última barra que não é do pregão corrente
  let prevClose = null;
  if (points.length) {
    const lastDay = new Date(points[points.length - 1].t).toDateString();
    const marketDay = meta.regularMarketTime
      ? new Date(meta.regularMarketTime * 1000).toDateString()
      : lastDay;
    if (lastDay === marketDay && points.length >= 2) prevClose = points[points.length - 2].c;
    else if (lastDay !== marketDay) prevClose = points[points.length - 1].c;
  }
  if (prevClose == null) prevClose = meta.chartPreviousClose != null ? meta.chartPreviousClose : price;

  const monthBase = meta.chartPreviousClose != null
    ? meta.chartPreviousClose
    : (points.length ? points[0].c : price);

  return {
    ticker,
    price,
    prevClose,
    changePct: prevClose ? (price / prevClose - 1) * 100 : 0,
    monthChangePct: monthBase ? (price / monthBase - 1) * 100 : 0,
    currency: meta.currency || 'BRL',
    history: points.map(p => Math.round(p.c * 100) / 100),
    marketTime: meta.regularMarketTime ? meta.regularMarketTime * 1000 : null,
  };
}

async function fetchBrapi(ticker) {
  const token = process.env.BRAPI_TOKEN;
  if (!token) throw new Error('BRAPI_TOKEN não configurado');
  const url = `https://brapi.dev/api/quote/${ticker}?range=1mo&interval=1d&token=${token}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`brapi HTTP ${res.status}`);
  const json = await res.json();
  const r = json.results && json.results[0];
  if (!r || r.regularMarketPrice == null) throw new Error('brapi: sem dados');

  const hist = (r.historicalDataPrice || [])
    .filter(h => h.close != null)
    .map(h => Math.round(h.close * 100) / 100);
  const monthBase = hist.length ? hist[0] : r.regularMarketPreviousClose;

  return {
    ticker,
    price: r.regularMarketPrice,
    prevClose: r.regularMarketPreviousClose,
    changePct: r.regularMarketChangePercent != null
      ? r.regularMarketChangePercent
      : (r.regularMarketPreviousClose ? (r.regularMarketPrice / r.regularMarketPreviousClose - 1) * 100 : 0),
    monthChangePct: monthBase ? (r.regularMarketPrice / monthBase - 1) * 100 : 0,
    currency: r.currency || 'BRL',
    history: hist,
    marketTime: r.regularMarketTime ? new Date(r.regularMarketTime).getTime() : null,
  };
}

async function fetchQuote(ticker) {
  try {
    return await fetchYahoo(ticker);
  } catch (err) {
    try {
      return await fetchBrapi(ticker);
    } catch (err2) {
      return { ticker, error: err.message };
    }
  }
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  const user = verifyAuth(req);
  if (!user) return res.status(401).json({ error: 'Não autorizado' });

  try {
    const now = Date.now();
    if (cache.payload && now - cache.at < CACHE_TTL_MS && req.query.force !== '1') {
      res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
      return res.status(200).json(cache.payload);
    }

    const quotes = await Promise.all(TICKERS.map(fetchQuote));
    const okCount = quotes.filter(q => !q.error).length;

    const payload = { updatedAt: now, okCount, total: TICKERS.length, quotes };

    // Só guarda em cache se pelo menos parte dos ativos veio com sucesso
    if (okCount > 0) cache = { at: now, payload };

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.status(200).json(payload);
  } catch (err) {
    console.error('Quotes API error:', err);
    return res.status(500).json({ error: 'Erro ao buscar cotações', details: err.message });
  }
};
