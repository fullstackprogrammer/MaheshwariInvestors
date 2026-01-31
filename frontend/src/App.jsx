import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import InvestorRankings from './components/InvestorRankings';
import StocksOverview from './components/StocksOverview';
import { checkHealth, getMetrics } from './services/api';

function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      // 1. Quick health check (5 sec) - is backend running?
      try {
        await checkHealth();
        if (cancelled) return;
        setLoading(false);
        setApiError(null);
        // 2. Load metrics in background (dashboard will show its own loading)
        getMetrics()
          .then((metrics) => {
            if (!cancelled) {
              setLastUpdated(metrics.last_updated);
              setApiError(null);
            }
          })
          .catch((err) => {
            if (!cancelled) {
              console.error('Metrics load failed:', err);
              setApiError('Dashboard data is still loading. Try refreshing or check the backend. First load can take 2–3 minutes.');
            }
          });
      } catch (error) {
        if (!cancelled) {
          setLoading(false);
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            setApiError('Backend did not respond in time. Is the server running on http://localhost:8000?');
          } else if (error.request) {
            setApiError('Cannot connect to backend. Start the server: cd backend && venv\\Scripts\\activate && uvicorn main:app --reload --port 8000');
          } else {
            setApiError('Backend error. Ensure the server is running on http://localhost:8000');
          }
        }
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="bg-dark-surface border-b border-dark-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <h1 className="text-2xl font-bold text-white">Maheshwari Investor Stock Analysis</h1>
            <nav className="flex gap-2">
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
            </nav>
          </div>
          {lastUpdated && (
            <p className="text-sm text-dark-muted mt-2">
              Last updated: {new Date(lastUpdated).toLocaleString()}
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

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {activeView === 'dashboard' && <Dashboard />}
        {activeView === 'investors' && <InvestorRankings />}
        {activeView === 'stocks' && <StocksOverview />}
      </main>
    </div>
  );
}

export default App;
