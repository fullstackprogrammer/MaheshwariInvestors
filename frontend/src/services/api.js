import axios from 'axios';

// Backend URL: .env wins; else local/LAN (localhost or private IP) use same host on port 8080; else production /api
export function getApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  if (typeof window === 'undefined') return 'http://127.0.0.1:8080';
  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1' ||
    /^10\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host) || /^192\.168\./.test(host);
  // Prefer IPv4 loopback: "localhost" can resolve to ::1 first; if only 127.0.0.1 is bound, requests stall.
  if (isLocal && (host === 'localhost' || host === '127.0.0.1')) return 'http://127.0.0.1:8080';
  if (isLocal) return `http://${host}:8080`;
  return `${window.location.origin}/api`;
}
const API_BASE_URL = getApiBaseUrl();
const DEBUG = true; // set to false to reduce console logs

const debug = (msg, ...args) => { if (DEBUG) console.log(`[API] ${msg}`, ...args); };

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second default timeout
});

// Health check: 15s timeout to allow for cold start / slow backend
export const checkHealth = async () => {
  debug('checkHealth →', API_BASE_URL + '/health');
  const response = await axios.get(`${API_BASE_URL}/health`, { timeout: 30000 });
  debug('checkHealth OK', response.data);
  return response.data;
};

api.interceptors.request.use(
  (config) => config,
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      console.error('Request timeout - backend may be slow or unresponsive');
    } else if (error.response) {
      console.error('API Error:', error.response.status, error.response.data);
    } else if (error.request) {
      console.error('No response received - is backend running?', error.request);
    } else {
      console.error('Error setting up request:', error.message);
    }
    return Promise.reject(error);
  }
);

export const getInvestors = async () => {
  const response = await api.get('/investors');
  return response.data;
};

// Rankings/stocks trigger backend to fetch all symbols - can take 2–3+ min on first load
export const getInvestorRankings = async () => {
  debug('getInvestorRankings →', API_BASE_URL + '/investors/rankings');
  const response = await axios.get(`${API_BASE_URL}/investors/rankings`, {
    timeout: 180000,
    headers: { 'Content-Type': 'application/json' },
  });
  debug('getInvestorRankings OK', Array.isArray(response.data) ? response.data.length + ' rows' : response.data);
  return response.data;
};

export const getStocks = async () => {
  debug('getStocks →', API_BASE_URL + '/stocks');
  const response = await axios.get(`${API_BASE_URL}/stocks`, {
    timeout: 180000,
    headers: { 'Content-Type': 'application/json' },
  });
  debug('getStocks OK', Array.isArray(response.data) ? response.data.length + ' symbols' : response.data);
  return response.data;
};

export const getMetrics = async () => {
  debug('getMetrics →', API_BASE_URL + '/metrics');
  const response = await axios.get(`${API_BASE_URL}/metrics`, {
    timeout: 180000, // 3 minutes for first load
    headers: { 'Content-Type': 'application/json' },
  });
  debug('getMetrics OK', response.data?.total_investors != null ? response.data.total_investors + ' investors' : response.data);
  return response.data;
};

export const refreshData = async () => {
  const response = await api.post('/refresh-data');
  return response.data;
};

/** Default CSP screener filters (for UI). */
export const getCspFilters = async () => {
  const response = await axios.get(`${API_BASE_URL}/csp-filters`, {
    timeout: 10000,
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

/** Conservative cash-secured put ideas. Pass filter params to adjust screener (screener can take 1–2 min). */
export const getCspIdeas = async (params = {}) => {
  const requestParams = {
    max_results: params.max_results ?? 50,
    max_dte: params.max_dte,
    sector: params.sector,
    strike_pct_min: params.strike_pct_min,
    strike_pct_max: params.strike_pct_max,
    max_bid_ask_pct: params.max_bid_ask_pct,
    target_upside_min: params.target_upside_min,
    min_annualized_return_pct: params.min_annualized_return_pct,
    min_market_cap_b: params.min_market_cap_b,
    max_symbols: params.max_symbols,
  };
  if (params.symbols && String(params.symbols).trim()) {
    requestParams.symbols = String(params.symbols).trim();
  }
  if (params.use_community_universe) {
    requestParams.use_community_universe = true;
  }
  const response = await axios.get(`${API_BASE_URL}/csp-ideas`, {
    params: requestParams,
    timeout: 120000,
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

/** Covered calls screener default filters. */
export const getCcFilters = async () => {
  const response = await api.get('/covered-calls-filters');
  return response.data;
};

/** Covered call ideas. Pass filter params (screener can take 1–2 min). */
export const getCcIdeas = async (params = {}) => {
  const requestParams = {
    max_results: params.max_results ?? 50,
    max_dte: params.max_dte,
    sector: params.sector,
    strike_pct_min: params.strike_pct_min,
    strike_pct_max: params.strike_pct_max,
    max_bid_ask_pct: params.max_bid_ask_pct,
    min_annualized_return_pct: params.min_annualized_return_pct,
    min_market_cap_b: params.min_market_cap_b,
    max_symbols: params.max_symbols,
  };
  if (params.symbols && String(params.symbols).trim()) {
    requestParams.symbols = String(params.symbols).trim();
  }
  if (params.use_community_universe) {
    requestParams.use_community_universe = true;
  }
  const response = await axios.get(`${API_BASE_URL}/covered-calls-ideas`, {
    params: requestParams,
    timeout: 120000,
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

/** MAI index vs benchmarks (can be slow on first load). */
export const getIndexPerformance = async () => {
  const response = await axios.get(`${API_BASE_URL}/index-performance`, {
    timeout: 180000,
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};
