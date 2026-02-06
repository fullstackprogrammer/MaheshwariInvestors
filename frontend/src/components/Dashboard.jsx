import { useState, useEffect } from 'react';
import { getMetrics, getIndexPerformance } from '../services/api';
import KPICard from './KPICard';

const RETRY_AFTER_MS = 15000; // 15s when backend returns 503 (cache warming)
const INDEX_POLL_MS = 15 * 60 * 1000; // 15 min, matches backend refresh

function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [indexPerformance, setIndexPerformance] = useState(null);
  const [viewMode, setViewMode] = useState('investors'); // 'investors' or 'stocks'
  const [loading, setLoading] = useState(true);
  const [cacheWarming, setCacheWarming] = useState(false); // true when we got 503 and are retrying

  useEffect(() => {
    let cancelled = false;
    let retryTimeoutId = null;
    let indexRetryTimeoutId = null;

    const loadMetrics = async () => {
      try {
        setLoading(true);
        setCacheWarming(false);
        const data = await getMetrics();
        if (cancelled) return;
        console.info('Dashboard: data loaded');
        setMetrics(data);
        setLoading(false);
      } catch (error) {
        if (cancelled) return;
        const is503 = error.response?.status === 503;
        if (is503) {
          console.info('Dashboard: cache warming, retrying in 15s');
          setCacheWarming(true);
          setLoading(true);
          retryTimeoutId = setTimeout(loadMetrics, RETRY_AFTER_MS);
          return;
        }
        console.error('Error loading dashboard metrics:', error);
        setLoading(false);
      }
    };

    const loadIndex = () => {
      getIndexPerformance()
        .then((data) => {
          if (!cancelled) setIndexPerformance(data);
        })
        .catch((err) => {
          if (cancelled) return;
          if (err.response?.status === 503) {
            indexRetryTimeoutId = setTimeout(loadIndex, RETRY_AFTER_MS);
            return;
          }
          console.error('Index performance load failed:', err);
        });
    };

    loadMetrics();
    loadIndex();
    const interval = setInterval(loadIndex, INDEX_POLL_MS);
    return () => {
      cancelled = true;
      if (retryTimeoutId) clearTimeout(retryTimeoutId);
      if (indexRetryTimeoutId) clearTimeout(indexRetryTimeoutId);
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="text-dark-muted">
          {cacheWarming ? 'Backend is preparing data after restart. Retrying in 15s…' : 'Loading dashboard…'}
        </p>
        <p className="text-sm text-dark-muted">
          {cacheWarming
            ? 'Once the cache is warm, data will load from cache and future loads will be fast.'
            : 'First load can take 2–3 minutes while the backend fetches stock data.'}
        </p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400">Failed to load dashboard data</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Dashboard</h2>
        <div className="flex gap-2 bg-dark-surface p-1 rounded-lg">
          <button
            onClick={() => setViewMode('investors')}
            className={`px-4 py-2 rounded-md transition-colors ${
              viewMode === 'investors'
                ? 'bg-blue-600 text-white'
                : 'text-dark-muted hover:text-white'
            }`}
          >
            Top Investors
          </button>
          <button
            onClick={() => setViewMode('stocks')}
            className={`px-4 py-2 rounded-md transition-colors ${
              viewMode === 'stocks'
                ? 'bg-blue-600 text-white'
                : 'text-dark-muted hover:text-white'
            }`}
          >
            Top Stocks
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-dark-surface border border-dark-border rounded-lg p-6">
          <p className="text-dark-muted text-sm mb-1">Total Investors</p>
          <p className="text-3xl font-bold">{metrics.total_investors}</p>
        </div>
        <div className="bg-dark-surface border border-dark-border rounded-lg p-6">
          <p className="text-dark-muted text-sm mb-1">Total Stocks</p>
          <p className="text-3xl font-bold">{metrics.total_stocks}</p>
        </div>
        <div className="bg-dark-surface border border-dark-border rounded-lg p-6">
          <p className="text-dark-muted text-sm mb-1">Avg Portfolio Value</p>
          <p className="text-3xl font-bold">
            ${((metrics.top_investors.reduce((sum, inv) => sum + inv.portfolio_value, 0) / metrics.top_investors.length) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="bg-dark-surface border border-dark-border rounded-lg p-6">
          <p className="text-dark-muted text-sm mb-1">Best YTD Return</p>
          <p className={`text-3xl font-bold ${metrics.top_investors[0]?.ytd >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {metrics.top_investors[0]?.ytd?.toFixed(2) ?? 0}%
          </p>
        </div>
        <div className="bg-dark-surface border border-dark-border rounded-lg p-6">
          <p className="text-dark-muted text-sm mb-1">Aggregated YTD Return</p>
          <p className={`text-3xl font-bold ${(metrics.aggregate_ytd_return ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(metrics.aggregate_ytd_return ?? 0) >= 0 ? '+' : ''}{(metrics.aggregate_ytd_return ?? 0).toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Top 5 Cards */}
      <div>
        <h3 className="text-xl font-semibold mb-4">
          Top 5 {viewMode === 'investors' ? 'Investors' : 'Stocks'} (YTD %)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {viewMode === 'investors'
            ? metrics.top_investors.map((investor, idx) => (
                <KPICard
                  key={investor.alias}
                  rank={idx + 1}
                  title={investor.alias}
                  value={investor.ytd}
                  subtitle={`Portfolio: $${investor.portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  type="investor"
                />
              ))
            : metrics.top_stocks.map((stock, idx) => (
                <KPICard
                  key={stock.symbol}
                  rank={idx + 1}
                  title={stock.symbol}
                  value={stock.ytd}
                  subtitle={stock.company_name}
                  type="stock"
                />
              ))}
        </div>
      </div>

      {/* Index performance: MAI vs Benchmarks (refreshes every 15 min with backend) */}
      <div>
        <div className="overflow-x-auto rounded-lg border border-dark-border">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-sky-700 text-white">
                <th className="px-4 py-3 font-semibold">Index</th>
                <th className="px-4 py-3 font-semibold">Price on 1/1/2026</th>
                <th className="px-4 py-3 font-semibold">Current Price</th>
                <th className="px-4 py-3 font-semibold">Gain/Loss $</th>
                <th className="px-4 py-3 font-semibold">Gain/Loss %</th>
                <th className="px-4 py-3 font-semibold">MAI compared to other indices</th>
              </tr>
            </thead>
            <tbody>
              {indexPerformance?.rows?.length ? (
                indexPerformance.rows.map((row) => (
                  <tr
                    key={row.index}
                    className={`border-b border-dark-border last:border-b-0 ${
                      row.index === 'MAI'
                        ? 'bg-sky-600/25 border-l-4 border-l-sky-400 font-medium'
                        : 'bg-sky-500/10'
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">{row.index}</td>
                    <td className="px-4 py-3">{row.price_start?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="px-4 py-3">{row.price_current?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className={`px-4 py-3 ${(row.gain_loss_dollars ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(row.gain_loss_dollars ?? 0) >= 0 ? '+' : ''}{row.gain_loss_dollars?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className={`px-4 py-3 ${(row.gain_loss_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(row.gain_loss_pct ?? 0) >= 0 ? '+' : ''}{row.gain_loss_pct?.toFixed(2)}%
                    </td>
                    <td className={`px-4 py-3 ${row.mai_vs_other_pct != null ? (row.mai_vs_other_pct >= 0 ? 'text-green-400' : 'text-red-400') : ''}`}>
                      {row.mai_vs_other_pct != null ? `${(row.mai_vs_other_pct >= 0 ? '+' : '')}${row.mai_vs_other_pct.toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="bg-dark-surface">
                  <td colSpan={6} className="px-4 py-6 text-center text-dark-muted">
                    Loading index performance…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
