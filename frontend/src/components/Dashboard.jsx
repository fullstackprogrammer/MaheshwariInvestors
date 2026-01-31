import { useState, useEffect } from 'react';
import { getMetrics } from '../services/api';
import KPICard from './KPICard';

function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [viewMode, setViewMode] = useState('investors'); // 'investors' or 'stocks'
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      const data = await getMetrics();
      setMetrics(data);
      setLoading(false);
    } catch (error) {
      console.error('Error loading dashboard metrics:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
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
    </div>
  );
}

export default Dashboard;
