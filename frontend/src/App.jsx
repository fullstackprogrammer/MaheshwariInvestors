import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import InvestorRankings from './components/InvestorRankings';
import StocksOverview from './components/StocksOverview';
import CashSecuredPutsStrategy from './components/CashSecuredPutsStrategy';
import CoveredCallsStrategy from './components/CoveredCallsStrategy';
import Login from './components/Login';
import { checkHealth, getMetrics, getInvestorRankings, getStocks, getApiBaseUrl } from './services/api';

const API_BASE_URL = getApiBaseUrl();

const DATA_RETRY_MS = 15000;
const DEBUG = true;

const AUTH_STORAGE_KEY = 'mai_auth';
const VIEW_STORAGE_KEY = 'mai_view';
const CSP_STORAGE_KEY = 'mai_csp_results';
const CC_STORAGE_KEY = 'mai_cc_results';
const VALID_VIEWS = ['dashboard', 'investors', 'stocks', 'csp', 'cc'];

function readStoredAuth() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw);
      if (data.authenticated && data.userId) return data;
    }
  } catch (_) {}
  return null;
}

function readStoredView(uid) {
  try {
    const saved = sessionStorage.getItem(VIEW_STORAGE_KEY);
    if (!saved || !VALID_VIEWS.includes(saved)) return null;
    if ((saved === 'csp' || saved === 'cc') && uid !== 'nileshrb') return null;
    return saved;
  } catch (_) {}
  return null;
}

function App() {
  const [authenticated, setAuthenticated] = useState(() => {
    const auth = readStoredAuth();
    return !!auth;
  });
  const [userId, setUserId] = useState(() => readStoredAuth()?.userId ?? null);
  const [activeView, setActiveView] = useState(() => {
    const auth = readStoredAuth();
    return readStoredView(auth?.userId) ?? 'dashboard';
  });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  // Rankings, stocks, and metrics loaded once after login; Dashboard/Rankings/Stocks use this (cache-backed)
  const [rankingsData, setRankingsData] = useState(null);
  const [stocksData, setStocksData] = useState(null);
  const [metricsData, setMetricsData] = useState(null);
  const [dataRetrying, setDataRetrying] = useState(false);

  const handleLogin = (uid) => {
    setUserId(uid ?? null);
    setAuthenticated(true);
    try {
      sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ authenticated: true, userId: uid }));
    } catch (_) {}
  };

  const handleSignOut = () => {
    setAuthenticated(false);
    setUserId(null);
    setActiveView('dashboard');
    try {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      sessionStorage.removeItem(VIEW_STORAGE_KEY);
      sessionStorage.removeItem(CSP_STORAGE_KEY);
      sessionStorage.removeItem(CC_STORAGE_KEY);
    } catch (_) {}
  };


  useEffect(() => {
    if (authenticated && activeView) {
      try {
        sessionStorage.setItem(VIEW_STORAGE_KEY, activeView);
      } catch (_) {}
    }
  }, [authenticated, activeView]);

  useEffect(() => {
    if (!authenticated) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    let dataRetryTimeoutId = null;

    async function loadRankingsStocksAndMetrics() {
      try {
        setDataRetrying(false);
        if (DEBUG) console.log('[App] loadRankingsStocksAndMetrics: starting');
        const [rankings, stocks, metrics] = await Promise.all([
          getInvestorRankings(),
          getStocks(),
          getMetrics(),
        ]);
        if (cancelled) return;
        if (DEBUG) console.log('[App] loadRankingsStocksAndMetrics: OK', rankings?.length, 'rankings', stocks?.length, 'stocks');
        setRankingsData(rankings);
        setStocksData(stocks);
        setMetricsData(metrics);
        if (metrics?.last_updated) setLastUpdated(metrics.last_updated);
        setApiError(null);
      } catch (err) {
        if (cancelled) return;
        if (err.response?.status === 503) {
          if (DEBUG) console.log('[App] loadRankingsStocksAndMetrics: 503 cache warming, retry in 15s');
          setDataRetrying(true);
          dataRetryTimeoutId = setTimeout(loadRankingsStocksAndMetrics, DATA_RETRY_MS);
          return;
        }
        console.error('[App] loadRankingsStocksAndMetrics failed:', err?.message || err, err.response?.status);
        setRankingsData([]);
        setStocksData([]);
        setMetricsData(null);
      }
    }

    async function init() {
      try {
        if (DEBUG) console.log('[App] init: checkHealth');
        await checkHealth();
        if (cancelled) return;
        if (DEBUG) console.log('[App] init: health OK, loading rankings+stocks and metrics');
        setLoading(false);
        setApiError(null);
        loadRankingsStocksAndMetrics();
      } catch (error) {
        if (!cancelled) {
          setLoading(false);
          const url = API_BASE_URL;
          if (DEBUG) console.log('[App] init failed:', error?.message || error, error?.code);
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            setApiError(
              `Backend did not respond in time at ${url}. From the backend folder run: uvicorn main:app --reload --port 8080 --host 0.0.0.0 (or .\\run.bat). If you still use port 8000, set VITE_API_BASE_URL=http://127.0.0.1:8000 in frontend/.env.development.local and restart npm run dev.`
            );
          } else if (error.request) {
            setApiError(`Cannot connect to backend at ${url}. Start the server (e.g. cd backend && uvicorn main:app --reload --port 8080).`);
          } else {
            setApiError(`Backend error. Ensure the server is running on ${url}`);
          }
        }
      }
    }

    init();
    return () => {
      cancelled = true;
      if (dataRetryTimeoutId) clearTimeout(dataRetryTimeoutId);
    };
  }, [authenticated]);

  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // Wait for backend health check before showing main content
  if (loading) {
    return (
      <div className="min-h-screen bg-dark-bg flex flex-col items-center justify-center gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="text-dark-muted">Connecting to backend at {API_BASE_URL}…</p>
        <p className="text-sm text-dark-muted">If this hangs, check that the backend is running (uvicorn on port 8080 for local dev).</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col">
      {/* Header */}
      <header className="bg-dark-surface border-b border-dark-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-3">
              <span className="font-bold text-white text-lg tracking-tight">
                MAI - Maheshwari Ansh Index
              </span>
            </div>
            <nav className="flex gap-2 items-center">
              <button
                onClick={() => setActiveView('dashboard')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeView === 'dashboard'
                    ? 'bg-blue-600 text-white'
                    : 'bg-dark-surface text-dark-muted hover:bg-dark-border'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setActiveView('investors')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeView === 'investors'
                    ? 'bg-blue-600 text-white'
                    : 'bg-dark-surface text-dark-muted hover:bg-dark-border'
                }`}
              >
                Investor Rankings
              </button>
              <button
                onClick={() => setActiveView('stocks')}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  activeView === 'stocks'
                    ? 'bg-blue-600 text-white'
                    : 'bg-dark-surface text-dark-muted hover:bg-dark-border'
                }`}
              >
                Stocks Overview
              </button>
              {userId === 'nileshrb' && (
                <>
                  <button
                    onClick={() => setActiveView('csp')}
                    className={`px-4 py-2 rounded-lg transition-colors ${
                      activeView === 'csp'
                        ? 'bg-blue-600 text-white'
                        : 'bg-dark-surface text-dark-muted hover:bg-dark-border'
                    }`}
                  >
                    Cash Secured Puts Strategy
                  </button>
                  <button
                    onClick={() => setActiveView('cc')}
                    className={`px-4 py-2 rounded-lg transition-colors ${
                      activeView === 'cc'
                        ? 'bg-blue-600 text-white'
                        : 'bg-dark-surface text-dark-muted hover:bg-dark-border'
                    }`}
                  >
                    Covered Calls Strategy
                  </button>
                </>
              )}
              <button
                onClick={handleSignOut}
                className="px-4 py-2 rounded-lg bg-dark-surface text-dark-muted hover:bg-dark-border transition-colors"
              >
                Sign out
              </button>
            </nav>
          </div>
          {lastUpdated && (
            <p className="text-sm text-dark-muted mt-2">
              Last updated: {new Date(lastUpdated).toLocaleString('en-US', { timeZone: 'America/Chicago', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })} CST
            </p>
          )}
        </div>
      </header>

      {/* API Error Banner */}
      {apiError && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 mx-4 mt-4 rounded-lg">
          <div className="flex justify-between items-center">
            <div>
              <p className="font-semibold">API Connection Error</p>
              <p className="text-sm">{apiError}</p>
            </div>
            <button
              onClick={() => setApiError(null)}
              className="text-red-200 hover:text-white"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Main Content - rankings/stocks loaded once from cache; tabs display from props */}
      <main className="container mx-auto px-4 py-8 flex-1">
        {activeView === 'dashboard' && (
          <Dashboard metrics={metricsData} dataRetrying={dataRetrying} />
        )}
        {activeView === 'investors' && (
          <InvestorRankings rankings={rankingsData} dataRetrying={dataRetrying} />
        )}
        {activeView === 'stocks' && (
          <StocksOverview stocks={stocksData} dataRetrying={dataRetrying} />
        )}
        {activeView === 'csp' && userId === 'nileshrb' && <CashSecuredPutsStrategy />}
        {activeView === 'cc' && userId === 'nileshrb' && <CoveredCallsStrategy />}
      </main>

      {/* Footer with footnotes */}
      <footer className="bg-dark-surface border-t border-dark-border mt-auto">
        <div className="container mx-auto px-4 py-4">
          <p className="text-dark-muted text-sm">
            <strong className="text-dark-muted">Notes:</strong> Each investor starts with $10,000 allocated equally across their selected stocks. Market data is refreshed every 15 minutes. Investor names are anonymized and displayed only as aliases.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
