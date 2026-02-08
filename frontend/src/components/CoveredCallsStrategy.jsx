import { useState, useEffect, useCallback } from 'react';
import { getCcIdeas, getCcFilters } from '../services/api';
import { Tooltip } from './ui/Tooltip';

const CC_HEADER_TOOLTIPS = {
  ticker: 'Stock symbol. Click to open more details on Finviz.',
  current_stock_price: 'Current stock price.',
  market_cap_b: "Company's total market value in billions.",
  call_strike: "Call strike price (price at which you'd sell the stock if assigned).",
  expiration: 'Option expiration date.',
  bid: 'Highest price a buyer will pay for the option.',
  ask: 'Lowest price a seller will accept for the option.',
  mid: 'Average of bid and ask (often used as fair value).',
  premium_per_contract: 'Premium you receive for selling one call contract (100 shares).',
  covered_shares_required: 'Number of shares needed to cover one call (always 100).',
  upside_if_called_pct: 'Percent gain if the stock is called away at the strike price.',
  return_pct: 'Premium as a percentage of stock value (not annualized).',
  annualized_return_pct: 'Annualized premium return based on days until expiration.',
  breakeven_price: 'Stock price where premium offsets a drop (stock price minus premium).',
  pct_to_strike: 'How far the strike is above the current stock price (upside if called).',
  forward_pe: 'Forward price-to-earnings ratio.',
  analyst_target_price: 'Analyst average price target.',
};

const SECTOR_OPTIONS = [
  { value: '', label: 'All sectors' },
  { value: 'Technology', label: 'Technology' },
  { value: 'Healthcare', label: 'Healthcare' },
  { value: 'Financial Services', label: 'Financial Services' },
  { value: 'Consumer Cyclical', label: 'Consumer Cyclical' },
  { value: 'Consumer Defensive', label: 'Consumer Defensive' },
  { value: 'Industrials', label: 'Industrials' },
  { value: 'Energy', label: 'Energy' },
  { value: 'Utilities', label: 'Utilities' },
  { value: 'Real Estate', label: 'Real Estate' },
  { value: 'Basic Materials', label: 'Basic Materials' },
  { value: 'Communication Services', label: 'Communication Services' },
];

const DEFAULT_FILTER_STATE = {
  sector: '',
  max_dte: 30,
  strike_pct_min: 1.05,
  strike_pct_max: 1.20,
  max_bid_ask_pct: 0.10,
  min_annualized_return_pct: 0.10,
  min_market_cap_b: 20,
  max_symbols: 10,
  max_results: 50,
};

function CoveredCallsStrategy() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [asOf, setAsOf] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: 'annualized_return_pct', direction: 'desc' });
  const [filters, setFilters] = useState(DEFAULT_FILTER_STATE);
  const [customSymbols, setCustomSymbols] = useState('');
  const [useCommunityStocks, setUseCommunityStocks] = useState(false);
  const [filtersLoaded, setFiltersLoaded] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(true);

  const CC_STORAGE_KEY = 'mai_cc_results';

  useEffect(() => {
    getCcFilters()
      .then((data) => {
        if (data && typeof data === 'object') {
          setFilters((prev) => ({ ...prev, ...data }));
        }
        setFiltersLoaded(true);
      })
      .catch(() => setFiltersLoaded(true));
  }, []);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(CC_STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        if (Array.isArray(data.opportunities)) {
          setOpportunities(data.opportunities);
          if (data.as_of != null) setAsOf(data.as_of);
        }
      }
    } catch (_) {}
  }, []);

  const loadCcIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = {};
    Object.keys(filters).forEach((k) => {
      const v = filters[k];
      if (k === 'sector') {
        if (v !== '' && v != null) params[k] = String(v);
      } else if (v !== '' && v != null) {
        params[k] = Number(v);
      }
    });
    if (useCommunityStocks && !customSymbols.trim()) {
      params.use_community_universe = true;
    } else if (customSymbols.trim()) {
      params.symbols = customSymbols.trim();
    }
    if (params.max_symbols != null) params.max_symbols = Math.min(10, Math.max(1, Number(params.max_symbols)));
    if (params.max_results != null) params.max_results = Math.min(100, Math.max(1, Number(params.max_results)));
    try {
      const data = await getCcIdeas(params);
      const opps = data.opportunities ?? [];
      const asOfVal = data.as_of ?? null;
      setOpportunities(opps);
      setAsOf(asOfVal);
      try {
        sessionStorage.setItem(CC_STORAGE_KEY, JSON.stringify({ opportunities: opps, as_of: asOfVal }));
      } catch (_) {}
    } catch (err) {
      setOpportunities([]);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load covered call ideas. Screener may take 1–2 minutes.');
    } finally {
      setLoading(false);
    }
  }, [filters, customSymbols, useCommunityStocks]);

  const runScreener = () => {
    loadCcIdeas();
  };

  const updateFilter = (key, value) => {
    if (key === 'sector') {
      setFilters((prev) => ({ ...prev, [key]: value }));
      return;
    }
    let v = value === '' ? '' : Number(value);
    if (key === 'max_symbols' && v !== '' && (v > 10 || v < 1)) v = Math.min(10, Math.max(1, v));
    if (key === 'max_results' && v !== '' && (v > 100 || v < 1)) v = Math.min(100, Math.max(1, v));
    setFilters((prev) => ({ ...prev, [key]: v === '' ? '' : v }));
  };

  const resetFilters = () => {
    getCcFilters().then((data) => {
      if (data && typeof data === 'object') setFilters((prev) => ({ ...prev, ...data }));
    });
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
    setSortConfig({ key, direction });
  };

  const sortedOpportunities = [...opportunities].sort((a, b) => {
    const aVal = a[sortConfig.key];
    const bVal = b[sortConfig.key];
    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;
    const cmp = typeof aVal === 'string' && typeof bVal === 'string'
      ? aVal.localeCompare(bVal)
      : (aVal < bVal ? -1 : aVal > bVal ? 1 : 0);
    return sortConfig.direction === 'asc' ? cmp : -cmp;
  });

  const formatNumber = (num) => (num == null ? '–' : Number(num).toLocaleString(undefined, { maximumFractionDigits: 2 }));
  const formatPercent = (num) => (num == null ? '–' : `${Number(num).toFixed(2)}%`);
  const formatCurrency = (num) => (num == null ? '–' : `$${Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
  const getSortIcon = (key) => (sortConfig.key !== key ? '↕' : sortConfig.direction === 'asc' ? '↑' : '↓');

  if (loading && opportunities.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-3xl font-bold">Covered Calls Strategy</h2>
        <p className="text-dark-muted text-sm">
          Adjust filters below and click Run screener to scan covered call opportunities.
        </p>
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
          <p className="text-dark-muted">Running covered calls screener…</p>
          <p className="text-sm text-dark-muted max-w-md text-center">
            Screening stocks and call options (1–2 minutes). Results will appear when ready.
          </p>
        </div>
      </div>
    );
  }

  const filterInput = (label, key, hint, type = 'number', step = 0.01) => (
    <div key={key} className="flex flex-col gap-0.5">
      <label className="text-xs text-dark-muted">{label}</label>
      <input
        type={type}
        step={step}
        value={filters[key] ?? ''}
        onChange={(e) => updateFilter(key, e.target.value)}
        className="w-full px-2 py-1.5 bg-dark-surface border border-dark-border rounded text-white text-sm focus:border-blue-500 focus:outline-none"
      />
      {hint && <span className="text-xs text-dark-muted">{hint}</span>}
    </div>
  );

  return (
    <div className={`space-y-4 ${loading ? 'cursor-wait' : ''}`}>
      <h2 className="text-3xl font-bold">Covered Calls Strategy</h2>
      <p className="text-dark-muted text-sm">
        Adjust filters below and click Run screener to scan covered call opportunities.
      </p>

      <div className="flex flex-col gap-2">
        <div className="flex items-start gap-8">
          <div className="flex flex-col gap-1 min-w-0 max-w-2xl flex-1">
            <label className="text-sm font-medium">Stocks / ETFs (comma-separated)</label>
            <input
              type="text"
              value={customSymbols}
              onChange={(e) => setCustomSymbols(e.target.value)}
              placeholder="e.g. AAPL, MSFT, SPY — leave empty to scan default MAI universe"
              className="w-full px-3 py-2 bg-dark-surface border border-dark-border rounded-lg text-white placeholder-dark-muted focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2 shrink-0 pt-6">
            <span className="text-sm font-medium whitespace-nowrap">Use MAI stocks</span>
            <button
              type="button"
              role="switch"
              aria-checked={useCommunityStocks}
              onClick={() => setUseCommunityStocks((v) => !v)}
              className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border border-dark-border transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-dark-bg ${useCommunityStocks ? 'bg-blue-600' : 'bg-dark-border'}`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition translate-x-0.5 mt-0.5 ${useCommunityStocks ? 'translate-x-5' : 'translate-x-0'}`}
              />
            </button>
          </div>
        </div>
      </div>

      <div className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => setFiltersOpen((o) => !o)}
          className="w-full px-4 py-3 flex justify-between items-center text-left font-medium hover:bg-dark-border transition-colors"
        >
          <span>Screener filters</span>
          <span className="text-dark-muted">{filtersOpen ? '▼' : '▶'}</span>
        </button>
        {filtersOpen && (
          <div className="px-4 pb-4 pt-0 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <div className="flex flex-col gap-0.5">
              <label className="text-xs text-dark-muted">Sector</label>
              <select
                value={filters.sector ?? ''}
                onChange={(e) => updateFilter('sector', e.target.value)}
                className="w-full px-2 py-1.5 bg-dark-surface border border-dark-border rounded text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                {SECTOR_OPTIONS.map((opt) => (
                  <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            {filterInput('Max DTE', 'max_dte', 'Calendar days to expiration')}
            {filterInput('Strike % min', 'strike_pct_min', 'e.g. 1.05 = 5% above spot', 'number', 0.01)}
            {filterInput('Strike % max', 'strike_pct_max', 'e.g. 1.15 = 15% above spot', 'number', 0.01)}
            {filterInput('Min annualized return', 'min_annualized_return_pct', 'Decimal e.g. 0.10 = 10%', 'number', 0.01)}
            {filterInput('Min market cap (B)', 'min_market_cap_b', '$B')}
            {filterInput('Max bid-ask spread %', 'max_bid_ask_pct', 'Of premium e.g. 0.10 = 10%', 'number', 0.01)}
            {filterInput('Max symbols', 'max_symbols', 'Universe size to scan. Max 10.', 'number', 1)}
            {filterInput('Max results', 'max_results', 'Max 100.', 'number', 1)}
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={runScreener}
                disabled={loading}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
              >
                {loading ? 'Running…' : 'Run screener'}
              </button>
              <button
                type="button"
                onClick={resetFilters}
                className="px-3 py-1.5 rounded bg-dark-border text-dark-muted hover:text-white text-sm"
              >
                Reset to defaults
              </button>
            </div>
          </div>
        )}
      </div>
      {asOf && (
        <p className="text-dark-muted text-xs">
          As of: {new Date(asOf).toLocaleString('en-US', { timeZone: 'America/Chicago' })} CST
        </p>
      )}

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg">
          <p className="font-semibold">Screener Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-dark-surface border-b border-dark-border sticky top-0">
              <th className="px-3 py-2 text-left cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('ticker')}>
                Ticker {getSortIcon('ticker')} <Tooltip content={CC_HEADER_TOOLTIPS.ticker}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('current_stock_price')}>
                Stock Price {getSortIcon('current_stock_price')} <Tooltip content={CC_HEADER_TOOLTIPS.current_stock_price}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('market_cap_b')}>
                Market cap {getSortIcon('market_cap_b')} <Tooltip content={CC_HEADER_TOOLTIPS.market_cap_b}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('call_strike')}>
                Call Strike {getSortIcon('call_strike')} <Tooltip content={CC_HEADER_TOOLTIPS.call_strike}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors min-w-[7.5rem]" onClick={() => handleSort('expiration')}>
                Expiry {getSortIcon('expiration')} <Tooltip content={CC_HEADER_TOOLTIPS.expiration}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Bid <Tooltip content={CC_HEADER_TOOLTIPS.bid}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Ask <Tooltip content={CC_HEADER_TOOLTIPS.ask}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Mid <Tooltip content={CC_HEADER_TOOLTIPS.mid}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('premium_per_contract')}>
                Premium ($/contract) {getSortIcon('premium_per_contract')} <Tooltip content={CC_HEADER_TOOLTIPS.premium_per_contract}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Covered Shares <Tooltip content={CC_HEADER_TOOLTIPS.covered_shares_required}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('upside_if_called_pct')}>
                Upside if Called % {getSortIcon('upside_if_called_pct')} <Tooltip content={CC_HEADER_TOOLTIPS.upside_if_called_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('return_pct')}>
                Return % {getSortIcon('return_pct')} <Tooltip content={CC_HEADER_TOOLTIPS.return_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('annualized_return_pct')}>
                Ann. Return % {getSortIcon('annualized_return_pct')} <Tooltip content={CC_HEADER_TOOLTIPS.annualized_return_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('breakeven_price')}>
                Breakeven Price {getSortIcon('breakeven_price')} <Tooltip content={CC_HEADER_TOOLTIPS.breakeven_price}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('pct_to_strike')}>
                % to Strike {getSortIcon('pct_to_strike')} <Tooltip content={CC_HEADER_TOOLTIPS.pct_to_strike}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('forward_pe')}>
                Fwd P/E {getSortIcon('forward_pe')} <Tooltip content={CC_HEADER_TOOLTIPS.forward_pe}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('analyst_target_price')}>
                Target {getSortIcon('analyst_target_price')} <Tooltip content={CC_HEADER_TOOLTIPS.analyst_target_price}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedOpportunities.map((opp, idx) => (
              <tr key={`${opp.ticker}-${opp.call_strike}-${opp.expiration}-${idx}`} className="border-b border-dark-border hover:bg-dark-surface transition-colors">
                <td className="px-3 py-2 font-semibold">
                  <a
                    href={`https://finviz.com/quote.ashx?t=${encodeURIComponent(opp.ticker)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 underline"
                  >
                    {opp.ticker}
                  </a>
                </td>
                <td className="px-3 py-2 text-right">{formatCurrency(opp.current_stock_price)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{opp.market_cap_b != null ? `$${Number(opp.market_cap_b).toFixed(1)}B` : '–'}</td>
                <td className="px-3 py-2 text-right">{formatCurrency(opp.call_strike)}</td>
                <td className="px-3 py-2 text-right text-dark-muted text-sm whitespace-nowrap">{opp.expiration || '–'}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.bid)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.ask)}</td>
                <td className="px-3 py-2 text-right">{formatCurrency(opp.mid)}</td>
                <td className="px-3 py-2 text-right font-semibold text-green-400">{formatCurrency(opp.premium_per_contract)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{opp.covered_shares_required ?? 100}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.upside_if_called_pct)}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.return_pct)}</td>
                <td className="px-3 py-2 text-right font-semibold text-green-400">{formatPercent(opp.annualized_return_pct)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.breakeven_price)}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.pct_to_strike)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatNumber(opp.forward_pe)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.analyst_target_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && opportunities.length === 0 && !error && (
          <div className="text-center py-8 text-dark-muted">No opportunities match the filters. Try again later or adjust filters.</div>
        )}
      </div>
    </div>
  );
}

export default CoveredCallsStrategy;
