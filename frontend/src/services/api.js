import axios from 'axios';

// Backend URL: .env wins; else when opened from non-localhost use same host:8000; else localhost:8000
function getApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1')
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  return 'http://localhost:8000';
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
  const response = await axios.get(`${API_BASE_URL}/health`, { timeout: 15000 });
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

/** Conservative cash-secured put ideas (screener can take 1–2 minutes). */
export const getCspIdeas = async (maxResults = 50) => {
  const response = await axios.get(`${API_BASE_URL}/csp-ideas`, {
    params: { max_results: maxResults },
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
