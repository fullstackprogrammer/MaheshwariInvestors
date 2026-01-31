import axios from 'axios';

// Backend URL from .env (Vite exposes only vars prefixed with VITE_)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second default timeout
});

// Health check uses short timeout (backend either responds in 5s or isn't there)
export const checkHealth = async () => {
  const response = await axios.get(`${API_BASE_URL}/health`, { timeout: 5000 });
  return response.data;
};

// Add request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`Making API request to: ${config.url}`);
    return config;
  },
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

export const getInvestorRankings = async () => {
  const response = await api.get('/investors/rankings');
  return response.data;
};

export const getStocks = async () => {
  const response = await api.get('/stocks');
  return response.data;
};

export const getMetrics = async () => {
  // Metrics fetches all stock data - can take 2+ minutes on first load
  const response = await axios.get(`${API_BASE_URL}/metrics`, {
    timeout: 180000, // 3 minutes for first load
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
};

export const refreshData = async () => {
  const response = await api.post('/refresh-data');
  return response.data;
};
