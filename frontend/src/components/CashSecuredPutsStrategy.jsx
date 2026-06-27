import { useState, useEffect, useCallback } from 'react';
import { getCspIdeas, getCspFilters } from '../services/api';
import { Tooltip } from './ui/Tooltip';

const CSP_HEADER_TOOLTIPS = {
  ticker: 'Stock symbol. Click to open more details on Finviz.',
  current_stock_price: 'Current stock price.',
  market_cap_b: "Company's total market value in billions.",
  put_strike: "Put strike price (price at which you'd buy the stock if assigned).",
  expiration: 'Option expiration date.',
  bid: 'Highest price a buyer will pay for the option.',
  ask: 'Lowest price a seller will accept for the option.',
  mid: 'Average of bid and ask (often used as fair value).',
  return_dollars: 'Premium at bid (conservative) for selling one put contract (100 shares).',
  cash_required: 'Cash held to secure the put (strike × 100).',
  return_pct: 'Premium as a percentage of cash required (not annualized).',
  annualized_return_pct: 'Annualized premium return based on days until expiration.',
  breakeven_at_expiry: 'Stock price at expiry where you neither gain nor lose (strike minus premium).',
  pct_downside_to_strike: 'How far the current stock price is above the put strike (downside cushion).',
  forward_pe: 'Forward price-to-earnings ratio.',
  analyst_target_price: 'Analyst average price target.',
  composite_score: 'Risk-adjusted score: annualized return × probability of profit × liquidity, plus cushion bonus. Higher is better.',
  delta: 'Put delta (negative for OTM puts). Measures sensitivity to stock price; used for POP. From chain or Black-Scholes.',
  probability_of_profit_pct: 'Estimated chance the put expires worthless (you keep premium). From option delta or Black-Scholes.',
  open_interest: 'Open contracts — higher means more liquid.',
  iv_percentile: 'IV rank proxy: current implied vol vs 1-year range of historical volatility.',
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
  min_dte: 7,
  max_dte: 30,
  put_delta_min: -0.30,
  put_delta_max: -0.10,
  max_bid_ask_pct: 0.10,
  target_upside_min: 0.10,
  min_annualized_return_pct: 0.10,
  min_market_cap_b: 20,
  min_open_interest: 100,
  min_option_volume: 10,
  max_price_vs_ma200_pct: 1.10,
  min_iv_rank: 0,
  skip_earnings: true,
  max_symbols: 10,
  max_results: 50,
};

function CashSecuredPutsStrategy() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [asOf, setAsOf] = useState(null);
  const [marketOpen, setMarketOpen] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: 'composite_score', direction: 'desc' });
  const [filters, setFilters] = useState(DEFAULT_FILTER_STATE);
  const [customSymbols, setCustomSymbols] = useState('');
  const [filtersLoaded, setFiltersLoaded] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(true);

  const CSP_STORAGE_KEY = 'mai_csp_results';

  useEffect(() => {
    getCspFilters()
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
      const raw = sessionStorage.getItem(CSP_STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        if (Array.isArray(data.opportunities)) {
          setOpportunities(data.opportunities);
          if (data.as_of != null) setAsOf(data.as_of);
          if (data.market_open === false) setMarketOpen(false);
        }
      }
    } catch (_) {}
  }, []);

  const loadCspIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = {};
    const skipKeys = new Set(['min_avg_volume_m', 'debt_to_equity_max']);
    Object.keys(filters).forEach((k) => {
      if (skipKeys.has(k)) return;
      const v = filters[k];
      if (k === 'sector') {
        if (v !== '' && v != null) params[k] = String(v);
      } else if (k === 'skip_earnings') {
        params[k] = Boolean(v);
      } else if (v !== '' && v != null) {
        params[k] = Number(v);
      }
    });
    if (customSymbols.trim()) {
      params.symbols = customSymbols.trim();
    }
    if (params.max_symbols != null) params.max_symbols = Math.min(10, Math.max(1, Number(params.max_symbols)));
    if (params.max_results != null) params.max_results = Math.min(100, Math.max(1, Number(params.max_results)));
    try {
      const data = await getCspIdeas(params);
      const opps = data.opportunities ?? [];
      const asOfVal = data.as_of ?? null;
      setOpportunities(opps);
      setAsOf(asOfVal);
      setMarketOpen(data.market_open !== false);
      try {
        sessionStorage.setItem(CSP_STORAGE_KEY, JSON.stringify({ opportunities: opps, as_of: asOfVal, market_open: data.market_open }));
      } catch (_) {}
    } catch (err) {
      setOpportunities([]);
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load CSP ideas. Screener may take 1–2 minutes.';
      const isNetworkError = !err?.response && (err?.message === 'Network Error' || err?.code === 'ERR_NETWORK');
      setError(isNetworkError
        ? 'Cannot reach the API. If you opened the app via an IP (e.g. 172.16.x.x), start the backend with: uvicorn main:app --reload --port 8080 --host 0.0.0.0 — or use http://localhost:5173'
        : msg);
    } finally {
      setLoading(false);
    }
  }, [filters, customSymbols]);

  const runScreener = () => {
    loadCspIdeas();
  };

  const updateFilter = (key, value) => {
    if (key === 'sector') {
      setFilters((prev) => ({ ...prev, [key]: value }));
      return;
    }
    if (key === 'skip_earnings') {
      setFilters((prev) => ({ ...prev, [key]: value }));
      return;
    }
    let v = value === '' ? '' : Number(value);
    if (key === 'max_symbols' && v !== '' && (v > 10 || v < 1)) v = Math.min(10, Math.max(1, v));
    if (key === 'max_results' && v !== '' && (v > 100 || v < 1)) v = Math.min(100, Math.max(1, v));
    setFilters((prev) => ({ ...prev, [key]: v === '' ? '' : v }));
  };

  const resetFilters = () => {
    getCspFilters().then((data) => {
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
  const formatDelta = (num) => (num == null ? '–' : Number(num).toFixed(3));
  const formatPercent = (num) => (num == null ? '–' : `${Number(num).toFixed(2)}%`);
  const formatCurrency = (num) => (num == null ? '–' : `$${Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
  const getSortIcon = (key) => (sortConfig.key !== key ? '↕' : sortConfig.direction === 'asc' ? '↑' : '↓');

  if (loading && opportunities.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-3xl font-bold">Cash Secured Puts Strategy</h2>
        <p className="text-dark-muted text-sm">
          Conservative put-selling ideas. Adjust filters below and run the screener (1–2 min).
        </p>
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
          <p className="text-dark-muted">Running CSP screener…</p>
          <p className="text-sm text-dark-muted max-w-md text-center">
            Screening large-cap stocks and options (1–2 minutes). Results will appear when ready.
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
      <h2 className="text-3xl font-bold">Cash Secured Puts Strategy</h2>
      <p className="text-dark-muted text-sm">
        Adjust filters below and click Run screener. Optionally enter stocks/ETFs (comma-separated) to scan only those; leave empty for the default universe. Takes 1–2 minutes.
      </p>

      <div className="flex flex-col gap-1 min-w-0 max-w-2xl">
        <label className="text-sm font-medium">Stocks / ETFs (comma-separated)</label>
        <input
          type="text"
          value={customSymbols}
          onChange={(e) => setCustomSymbols(e.target.value)}
          placeholder="e.g. AAPL, MSFT, SPY — leave empty for default large-cap universe"
          className="w-full px-3 py-2 bg-dark-surface border border-dark-border rounded-lg text-white placeholder-dark-muted focus:border-blue-500 focus:outline-none"
        />
      </div>

      {/* Filters panel */}
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
            {filterInput('Min DTE', 'min_dte', 'Min calendar days to expiration', 'number', 1)}
            {filterInput('Max DTE', 'max_dte', 'Max calendar days to expiration')}
            {filterInput('Put delta min', 'put_delta_min', 'e.g. -0.30 = up to 30Δ assignment risk', 'number', 0.01)}
            {filterInput('Put delta max', 'put_delta_max', 'e.g. -0.10 = at least 10Δ (more OTM)', 'number', 0.01)}
            {filterInput('Max bid-ask %', 'max_bid_ask_pct', 'Of premium e.g. 0.10 = 10%', 'number', 0.01)}
            {filterInput('Min annualized return', 'min_annualized_return_pct', 'Decimal e.g. 0.10 = 10%', 'number', 0.01)}
            {filterInput('Target upside min', 'target_upside_min', 'e.g. 0.10 = 10%', 'number', 0.01)}
            {filterInput('Min market cap (B)', 'min_market_cap_b', '$B')}
            {filterInput('Min open interest', 'min_open_interest', 'Contracts', 'number', 1)}
            {filterInput('Min option volume', 'min_option_volume', 'Today\'s contracts', 'number', 1)}
            {filterInput('Max price vs MA200', 'max_price_vs_ma200_pct', 'e.g. 1.10 = 10% above 200d MA', 'number', 0.01)}
            {filterInput('Min IV rank', 'min_iv_rank', '0–100 proxy; 0 = off', 'number', 1)}
            {filterInput('Max symbols', 'max_symbols', 'Universe size to scan. Max 10.', 'number', 1)}
            {filterInput('Max results', 'max_results', 'Max 100.', 'number', 1)}
            <div className="flex flex-col gap-0.5 justify-end">
              <label className="text-xs text-dark-muted">Skip earnings window</label>
              <button
                type="button"
                role="switch"
                aria-checked={filters.skip_earnings !== false}
                onClick={() => updateFilter('skip_earnings', !filters.skip_earnings)}
                className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border border-dark-border transition-colors focus:outline-none ${filters.skip_earnings !== false ? 'bg-blue-600' : 'bg-dark-border'}`}
              >
                <span className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition translate-x-0.5 mt-0.5 ${filters.skip_earnings !== false ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
              <span className="text-xs text-dark-muted">Exclude expirations that cross earnings</span>
            </div>
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

      {!marketOpen && opportunities.length > 0 && (
        <div className="bg-amber-900/40 border border-amber-700 text-amber-200 px-4 py-2 rounded-lg text-sm">
          US market is closed. Option bids may be missing; run again during market hours (9:30 AM–4 PM ET) for live quotes.
        </div>
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
                Ticker {getSortIcon('ticker')} <Tooltip content={CSP_HEADER_TOOLTIPS.ticker}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('current_stock_price')}>
                Price {getSortIcon('current_stock_price')} <Tooltip content={CSP_HEADER_TOOLTIPS.current_stock_price}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('market_cap_b')}>
                Market cap {getSortIcon('market_cap_b')} <Tooltip content={CSP_HEADER_TOOLTIPS.market_cap_b}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('put_strike')}>
                Strike {getSortIcon('put_strike')} <Tooltip content={CSP_HEADER_TOOLTIPS.put_strike}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors min-w-[7.5rem]" onClick={() => handleSort('expiration')}>
                Expiry {getSortIcon('expiration')} <Tooltip content={CSP_HEADER_TOOLTIPS.expiration}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Bid <Tooltip content={CSP_HEADER_TOOLTIPS.bid}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Ask <Tooltip content={CSP_HEADER_TOOLTIPS.ask}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Mid <Tooltip content={CSP_HEADER_TOOLTIPS.mid}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('return_dollars')}>
                Return $ (1 contract) {getSortIcon('return_dollars')} <Tooltip content={CSP_HEADER_TOOLTIPS.return_dollars}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('cash_required')}>
                Cash req (1 contract) {getSortIcon('cash_required')} <Tooltip content={CSP_HEADER_TOOLTIPS.cash_required}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('return_pct')}>
                Return % {getSortIcon('return_pct')} <Tooltip content={CSP_HEADER_TOOLTIPS.return_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('annualized_return_pct')}>
                Ann. Return % {getSortIcon('annualized_return_pct')} <Tooltip content={CSP_HEADER_TOOLTIPS.annualized_return_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('composite_score')}>
                Score {getSortIcon('composite_score')} <Tooltip content={CSP_HEADER_TOOLTIPS.composite_score}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('delta')}>
                Delta {getSortIcon('delta')} <Tooltip content={CSP_HEADER_TOOLTIPS.delta}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('probability_of_profit_pct')}>
                POP % {getSortIcon('probability_of_profit_pct')} <Tooltip content={CSP_HEADER_TOOLTIPS.probability_of_profit_pct}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('open_interest')}>
                OI {getSortIcon('open_interest')} <Tooltip content={CSP_HEADER_TOOLTIPS.open_interest}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Breakeven (expiry) <Tooltip content={CSP_HEADER_TOOLTIPS.breakeven_at_expiry}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right cursor-pointer hover:bg-dark-border transition-colors" onClick={() => handleSort('pct_downside_to_strike')}>
                % to Strike {getSortIcon('pct_downside_to_strike')} <Tooltip content={CSP_HEADER_TOOLTIPS.pct_downside_to_strike}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Fwd P/E <Tooltip content={CSP_HEADER_TOOLTIPS.forward_pe}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
              <th className="px-3 py-2 text-right">
                Target <Tooltip content={CSP_HEADER_TOOLTIPS.analyst_target_price}><span className="ml-0.5 cursor-help inline-block" aria-hidden="true">ℹ️</span></Tooltip>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedOpportunities.map((opp, idx) => (
              <tr key={`${opp.ticker}-${opp.put_strike}-${opp.expiration}-${idx}`} className="border-b border-dark-border hover:bg-dark-surface transition-colors">
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
                <td className="px-3 py-2 text-right">{formatCurrency(opp.put_strike)}</td>
                <td className="px-3 py-2 text-right text-dark-muted text-sm whitespace-nowrap">{opp.expiration || '–'}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.bid)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.ask)}</td>
                <td className="px-3 py-2 text-right">{formatCurrency(opp.mid)}</td>
                <td className="px-3 py-2 text-right font-semibold text-green-400">{formatCurrency(opp.return_dollars)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.cash_required)}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.return_pct)}</td>
                <td className="px-3 py-2 text-right font-semibold text-green-400">{formatPercent(opp.annualized_return_pct)}</td>
                <td className="px-3 py-2 text-right font-semibold text-blue-400">{formatNumber(opp.composite_score)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatDelta(opp.delta)}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.probability_of_profit_pct)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatNumber(opp.open_interest)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.breakeven_at_expiry)}</td>
                <td className="px-3 py-2 text-right">{formatPercent(opp.pct_downside_to_strike)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatNumber(opp.forward_pe)}</td>
                <td className="px-3 py-2 text-right text-dark-muted">{formatCurrency(opp.analyst_target_price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && opportunities.length === 0 && !error && (
          <div className="text-center py-8 text-dark-muted">No opportunities match the conservative filters. Try again later or refresh.</div>
        )}
      </div>
    </div>
  );
}

export default CashSecuredPutsStrategy;
