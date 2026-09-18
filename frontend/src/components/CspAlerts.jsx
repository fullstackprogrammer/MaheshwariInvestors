import { useCallback, useEffect, useState } from 'react';
import {
  getCspAlertSettings,
  updateCspAlertSettings,
  getCspAlertIdeas,
  runCspAlertScan,
} from '../services/api';

const CRITERIA_FIELDS = [
  { key: 'min_dte', label: 'Min DTE', type: 'number', step: 1 },
  { key: 'max_dte', label: 'Max DTE', type: 'number', step: 1 },
  { key: 'put_delta_min', label: 'Put delta min', type: 'number', step: 0.01 },
  { key: 'put_delta_max', label: 'Put delta max', type: 'number', step: 0.01 },
  { key: 'max_bid_ask_pct', label: 'Max bid/ask %', type: 'number', step: 0.01 },
  { key: 'min_annualized_return_pct', label: 'Min ann. return', type: 'number', step: 0.01 },
  { key: 'min_open_interest', label: 'Min open interest', type: 'number', step: 1 },
  { key: 'min_option_volume', label: 'Min option volume', type: 'number', step: 1 },
  { key: 'max_price_vs_ma200_pct', label: 'Max price vs MA200', type: 'number', step: 0.01 },
  { key: 'min_iv_rank', label: 'Min IV rank', type: 'number', step: 1 },
  { key: 'top_n', label: 'Top N to keep / text', type: 'number', step: 1 },
];

function fmtMoney(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  const sign = n > 0 ? '+' : '';
  return `${sign}$${n.toFixed(2)}`;
}

function fmtNum(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toFixed(digits);
}

function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function cashInvested(row) {
  const strike = Number(row?.put_strike);
  if (!strike || Number.isNaN(strike)) return null;
  return strike * 100; // 1 short put contract
}

function pnlDollars(row) {
  if (row.status === 'settled') return row.settled_pnl;
  if (row.status === 'open') return row.last_unrealized_pnl;
  return null;
}

function pnlPctOfInvested(row) {
  const invested = cashInvested(row);
  const pnl = pnlDollars(row);
  if (invested == null || invested === 0 || pnl === null || pnl === undefined) return null;
  return (Number(pnl) / invested) * 100;
}

function fmtSuggestedAt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/Chicago',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' CT';
}

function pnlClass(v) {
  if (v === null || v === undefined) return 'text-dark-muted';
  if (v > 0) return 'text-emerald-400';
  if (v < 0) return 'text-red-400';
  return 'text-dark-muted';
}

/**
 * CSP Alerts — settings + paper P&L ledger.
 * Gated in App.jsx; APIs also enforce FEATURE_USERS on the backend.
 */
function CspAlerts({ userId }) {
  const [settings, setSettings] = useState(null);
  const [email, setEmail] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [watchlistText, setWatchlistText] = useState('');
  const [criteria, setCriteria] = useState({});
  const [ideas, setIdeas] = useState([]);
  const [summary, setSummary] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async (opts = {}) => {
    const { refreshMarks = false } = opts;
    setError(null);
    try {
      const [s, ledger] = await Promise.all([
        getCspAlertSettings(userId),
        getCspAlertIdeas(userId, {
          // Always load all ideas so summary tiles stay accurate; filter in the UI.
          refresh: refreshMarks,
        }),
      ]);
      setSettings(s);
      setEmail(s.email || '');
      setEmailEnabled(!!s.email_enabled);
      setWatchlistText((s.watchlist || []).join(', '));
      setCriteria(s.criteria || {});
      setIdeas(ledger.ideas || []);
      setSummary(ledger.summary || null);
      setLatestRun(ledger.latest_run || null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load CSP Alerts');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    setLoading(true);
    loadAll();
  }, [loadAll]);

  const visibleIdeas = statusFilter === 'all'
    ? ideas
    : ideas.filter((row) => row.status === statusFilter);

  const totalInvested = ideas.reduce((sum, row) => sum + (cashInvested(row) || 0), 0);
  const totalPnl =
    (summary?.open_unrealized_pnl || 0) + (summary?.settled_realized_pnl || 0);
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : null;
  const persistSettings = async () => {
    const watchlist = watchlistText.split(/[\s,;]+/).map((t) => t.trim()).filter(Boolean);
    const saved = await updateCspAlertSettings(userId, {
      email,
      email_enabled: emailEnabled,
      watchlist,
      criteria: {
        ...criteria,
        skip_earnings: !!criteria.skip_earnings,
      },
    });
    setSettings(saved);
    setEmail(saved.email || '');
    setEmailEnabled(!!saved.email_enabled);
    setWatchlistText((saved.watchlist || []).join(', '));
    setCriteria(saved.criteria || {});
    return saved;
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await persistSettings();
      setMessage('Settings saved.');
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async (withEmail) => {
    setRunning(true);
    setMessage(null);
    setError(null);
    try {
      await persistSettings();
      const result = await runCspAlertScan(userId, { send_email: withEmail });
      setMessage(
        result.error
          ? `Run finished with error: ${result.error}`
          : `Scan done — found ${result.opportunities_found}, new ideas ${result.ideas_inserted}, email ${result.email_sent ? 'sent' : 'not sent'}.`
      );
      await loadAll({ refreshMarks: true });
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Scan failed');
    } finally {
      setRunning(false);
    }
  };

  const handleRefreshMarks = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await loadAll({ refreshMarks: true });
      setMessage('Marks refreshed.');
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const updateCriterion = (key, value) => {
    setCriteria((prev) => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="text-dark-muted py-12 text-center">Loading CSP Alerts…</div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold text-white mb-1">CSP Alerts</h2>
        <p className="text-dark-muted text-sm max-w-3xl">
          Weekday 12:30 PM CT scan of your watchlist. Top ideas are saved as paper trades with live P/L until expiry,
          then settled from the stock close. Email includes zero-result days when enabled.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}
      {message && (
        <div className="bg-blue-900/30 border border-blue-700 text-blue-100 px-4 py-3 rounded-lg text-sm">{message}</div>
      )}

      {/* Settings */}
      <section className="bg-dark-surface border border-dark-border rounded-lg p-5 space-y-4">
        <h3 className="text-lg font-medium text-white">Settings</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-dark-muted mb-1">Alert email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-3 py-2 rounded-lg bg-dark-bg border border-dark-border text-white"
            />
          </div>
          <div className="flex items-end pb-2">
            <label className="inline-flex items-center gap-2 text-sm text-white cursor-pointer">
              <input
                type="checkbox"
                checked={emailEnabled}
                onChange={(e) => setEmailEnabled(e.target.checked)}
                className="rounded border-dark-border"
              />
              Send email at 12:30 CT (weekdays)
            </label>
          </div>
        </div>

        <div>
          <label className="block text-sm text-dark-muted mb-1">Watchlist tickers (comma-separated)</label>
          <textarea
            value={watchlistText}
            onChange={(e) => setWatchlistText(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 rounded-lg bg-dark-bg border border-dark-border text-white font-mono text-sm"
          />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {CRITERIA_FIELDS.map((f) => (
            <div key={f.key}>
              <label className="block text-xs text-dark-muted mb-1">{f.label}</label>
              <input
                type="number"
                step={f.step}
                value={criteria[f.key] ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  updateCriterion(f.key, raw === '' ? '' : Number(raw));
                }}
                className="w-full px-3 py-2 rounded-lg bg-dark-bg border border-dark-border text-white text-sm"
              />
            </div>
          ))}
          <div className="flex items-end pb-2">
            <label className="inline-flex items-center gap-2 text-sm text-white cursor-pointer">
              <input
                type="checkbox"
                checked={!!criteria.skip_earnings}
                onChange={(e) => updateCriterion('skip_earnings', e.target.checked)}
                className="rounded border-dark-border"
              />
              Skip earnings window
            </label>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 pt-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || running}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save settings'}
          </button>
          <button
            type="button"
            onClick={() => handleRun(true)}
            disabled={running || saving}
            className="px-4 py-2 rounded-lg bg-emerald-700 text-white text-sm hover:bg-emerald-600 disabled:opacity-50"
          >
            {running ? 'Scanning… (1–3 min)' : 'Run scan now + email'}
          </button>
          <button
            type="button"
            onClick={() => handleRun(false)}
            disabled={running || saving}
            className="px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-white text-sm hover:bg-dark-border disabled:opacity-50"
          >
            Run scan (no email)
          </button>
          <button
            type="button"
            onClick={handleRefreshMarks}
            disabled={refreshing || running}
            className="px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-white text-sm hover:bg-dark-border disabled:opacity-50"
          >
            {refreshing ? 'Refreshing…' : 'Refresh P/L marks'}
          </button>
        </div>

        {settings?.updated_at && (
          <p className="text-xs text-dark-muted">Settings updated: {new Date(settings.updated_at).toLocaleString()}</p>
        )}
        {latestRun && (
          <p className="text-xs text-dark-muted">
            Last run: {new Date(latestRun.ran_at).toLocaleString()} · found {latestRun.opportunities_found} ·
            inserted {latestRun.ideas_inserted} · email {latestRun.sms_sent ? 'yes' : 'no'}
            {latestRun.error ? ` · error: ${latestRun.error}` : ''}
          </p>
        )}
      </section>

      {/* Summary */}
      {summary && (
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <p className="text-xs text-dark-muted">Open ideas</p>
            <p className="text-xl text-white">{summary.open_count}</p>
          </div>
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <p className="text-xs text-dark-muted">Open unrealized</p>
            <p className={`text-xl ${pnlClass(summary.open_unrealized_pnl)}`}>{fmtMoney(summary.open_unrealized_pnl)}</p>
          </div>
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <p className="text-xs text-dark-muted">Settled realized</p>
            <p className={`text-xl ${pnlClass(summary.settled_realized_pnl)}`}>{fmtMoney(summary.settled_realized_pnl)}</p>
          </div>
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <p className="text-xs text-dark-muted">Total P/L %</p>
            <p className={`text-xl ${pnlClass(totalPnlPct)}`}>{fmtPct(totalPnlPct)}</p>
            <p className="text-xs text-dark-muted mt-1">
              {fmtMoney(totalPnl)} on ${totalInvested.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </p>
          </div>
          <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
            <p className="text-xs text-dark-muted">Settled win rate</p>
            <p className="text-xl text-white">
              {summary.settled_win_rate == null ? '—' : `${(summary.settled_win_rate * 100).toFixed(0)}%`}
              <span className="text-sm text-dark-muted ml-1">({summary.settled_count})</span>
            </p>
          </div>
        </section>
      )}

      {/* Ledger */}
      <section className="bg-dark-surface border border-dark-border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-dark-border flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-medium text-white">Tracked ideas (paper)</h3>
          <div className="flex gap-2 text-sm">
            {['all', 'open', 'settled'].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-lg capitalize ${
                  statusFilter === s ? 'bg-blue-600 text-white' : 'bg-dark-bg text-dark-muted'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-dark-muted border-b border-dark-border">
              <tr>
                <th className="px-3 py-2">Suggested (CT)</th>
                <th className="px-3 py-2">Ticker</th>
                <th className="px-3 py-2">Strike</th>
                <th className="px-3 py-2">Expiry</th>
                <th className="px-3 py-2">$ Invested</th>
                <th className="px-3 py-2">Entry prem</th>
                <th className="px-3 py-2">Entry spot</th>
                <th className="px-3 py-2">Last spot</th>
                <th className="px-3 py-2">Put mid</th>
                <th className="px-3 py-2">Unrealized $</th>
                <th className="px-3 py-2">Settled $</th>
                <th className="px-3 py-2">P/L %</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleIdeas.length === 0 && (
                <tr>
                  <td colSpan={13} className="px-3 py-8 text-center text-dark-muted">
                    No tracked ideas yet. Save settings and run a scan.
                  </td>
                </tr>
              )}
              {visibleIdeas.map((row) => {
                const invested = cashInvested(row);
                const pct = pnlPctOfInvested(row);
                return (
                  <tr key={row.id} className="border-b border-dark-border/60 text-white">
                    <td className="px-3 py-2 whitespace-nowrap text-dark-muted text-xs">
                      {fmtSuggestedAt(row.suggested_at)}
                    </td>
                    <td className="px-3 py-2 font-medium">{row.ticker}</td>
                    <td className="px-3 py-2">{fmtNum(row.put_strike, 2)}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{row.expiration}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {invested == null ? '—' : `$${invested.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
                    </td>
                    <td className="px-3 py-2">{fmtNum(row.entry_premium, 2)}</td>
                    <td className="px-3 py-2">{fmtNum(row.entry_spot, 2)}</td>
                    <td className="px-3 py-2">{fmtNum(row.last_spot, 2)}</td>
                    <td className="px-3 py-2">{fmtNum(row.last_put_mid, 2)}</td>
                    <td className={`px-3 py-2 ${pnlClass(row.status === 'open' ? row.last_unrealized_pnl : null)}`}>
                      {row.status === 'open' ? fmtMoney(row.last_unrealized_pnl) : '—'}
                    </td>
                    <td className={`px-3 py-2 ${pnlClass(row.settled_pnl)}`}>
                      {row.status === 'settled' ? (
                        <span title={row.settled_status || ''}>
                          {fmtMoney(row.settled_pnl)}
                          {row.settled_stock_close != null && (
                            <span className="text-dark-muted text-xs ml-1">@ {fmtNum(row.settled_stock_close, 2)}</span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className={`px-3 py-2 whitespace-nowrap ${pnlClass(pct)}`}>
                      {fmtPct(pct)}
                    </td>
                    <td className="px-3 py-2 capitalize text-dark-muted">
                      {row.status}
                      {row.settled_status ? ` (${row.settled_status.replace('expired_', '')})` : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="px-4 py-3 text-xs text-dark-muted border-t border-dark-border">
          Paper booking: 1 short put contract. <strong className="text-dark-muted">$ Invested</strong> = strike × 100 (cash secured).
          Unrealized = (entry premium − put mid) × 100. <strong className="text-dark-muted">P/L %</strong> = P/L $ ÷ $ Invested.
          Settled uses underlying close on expiry vs strike. Suggested times are America/Chicago.
        </p>
      </section>
    </div>
  );
}

export default CspAlerts;
