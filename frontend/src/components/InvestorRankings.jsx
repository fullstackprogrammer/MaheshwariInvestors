import { useState, useEffect, useMemo } from 'react';
import { getInvestorRankings } from '../services/api';

function InvestorRankings() {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: 'rank', direction: 'asc' });

  useEffect(() => {
    loadRankings();
  }, []);

  const loadRankings = async () => {
    try {
      setLoading(true);
      const data = await getInvestorRankings();
      setRankings(data);
      setLoading(false);
    } catch (error) {
      console.error('Error loading investor rankings:', error);
      setLoading(false);
    }
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortedRankings = useMemo(() => {
    const sorted = [...rankings];
    const dir = sortConfig.direction === 'asc' ? 1 : -1;
    sorted.sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];
      // Handle undefined/null so sort is stable
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      // Ensure numbers for numeric columns
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return (aVal - bVal) * dir;
      }
      const aStr = String(aVal);
      const bStr = String(bVal);
      if (aStr < bStr) return -dir;
      if (aStr > bStr) return dir;
      return 0;
    });
    return sorted;
  }, [rankings, sortConfig]);

  const formatNumber = (num) => {
    if (typeof num !== 'number') return '-';
    return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  const formatPercent = (num) => {
    if (typeof num !== 'number') return '-';
    const sign = num >= 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return '↕️';
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Investor Rankings</h2>
        <button
          onClick={loadRankings}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-dark-surface border-b border-dark-border sticky top-0">
              <th
                className="px-4 py-3 text-left cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('rank')}
              >
                Rank {getSortIcon('rank')}
              </th>
              <th className="px-4 py-3 text-left">Investor Alias</th>
              <th className="px-4 py-3 text-left">Stock 1</th>
              <th className="px-4 py-3 text-left">Stock 2</th>
              <th className="px-4 py-3 text-left">Stock 3</th>
              <th className="px-4 py-3 text-left">Stock 4</th>
              <th className="px-4 py-3 text-left">Stock 5</th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('portfolio_value')}
              >
                Portfolio Value {getSortIcon('portfolio_value')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('daily')}
              >
                Daily % {getSortIcon('daily')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('1m')}
              >
                1M % {getSortIcon('1m')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('3m')}
              >
                3M % {getSortIcon('3m')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('ytd')}
              >
                YTD % {getSortIcon('ytd')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedRankings.map((investor, index) => (
              <tr
                key={investor.stocks ? `${investor.alias}-${investor.stocks.join('-')}-${index}` : `row-${index}`}
                className="border-b border-dark-border hover:bg-dark-surface transition-colors"
              >
                <td className="px-4 py-3 font-semibold">{investor.rank}</td>
                <td className="px-4 py-3 font-medium">{investor.alias}</td>
                {[0, 1, 2, 3, 4].map((idx) => (
                  <td key={idx} className="px-4 py-3 text-dark-muted">
                    {investor.stocks[idx] || '-'}
                  </td>
                ))}
                <td className="px-4 py-3 text-right font-semibold">
                  ${formatNumber(investor.portfolio_value)}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    investor.daily >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(investor.daily)}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    investor['1m'] >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(investor['1m'])}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    investor['3m'] >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(investor['3m'])}
                </td>
                <td
                  className={`px-4 py-3 text-right font-semibold ${
                    investor.ytd >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(investor.ytd)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default InvestorRankings;
