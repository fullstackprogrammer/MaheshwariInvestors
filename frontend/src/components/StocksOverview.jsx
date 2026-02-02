import { useState, useMemo } from 'react';

function StocksOverview({ stocks: stocksProp = null, dataRetrying = false }) {
  const [sortConfig, setSortConfig] = useState({ key: 'ytd', direction: 'desc' });
  const [searchTerm, setSearchTerm] = useState('');
  const [sectorFilter, setSectorFilter] = useState('');
  const stocks = stocksProp ?? [];

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sectors = useMemo(() => {
    const uniqueSectors = [...new Set(stocks.map(s => s.sector))].filter(Boolean).sort();
    return uniqueSectors;
  }, [stocks]);

  const filteredAndSortedStocks = useMemo(() => {
    let filtered = stocks.filter((stock) => {
      const matchesSearch =
        stock.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        stock.company_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesSector = !sectorFilter || stock.sector === sectorFilter;
      return matchesSearch && matchesSector;
    });

    filtered.sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [stocks, searchTerm, sectorFilter, sortConfig]);

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-';
    const sign = num >= 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return '↕️';
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };

  if (stocksProp === null) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="text-dark-muted">
          {dataRetrying ? 'Backend is preparing data. Retrying in 15s…' : 'Loading stocks…'}
        </p>
        <p className="text-sm text-dark-muted max-w-md text-center">
          {dataRetrying
            ? 'Data is loaded once from cache; retrying until ready.'
            : 'First load can take 2–3 minutes if the backend is warming its cache. Stocks will appear when ready.'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-3xl font-bold">Stocks Overview</h2>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search by symbol or company name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 bg-dark-surface border border-dark-border rounded-lg text-white placeholder-dark-muted focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="sm:w-64">
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            className="w-full px-4 py-2 bg-dark-surface border border-dark-border rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">All Sectors</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-dark-surface border-b border-dark-border sticky top-0">
              <th
                className="px-4 py-3 text-left cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('symbol')}
              >
                Symbol {getSortIcon('symbol')}
              </th>
              <th className="px-4 py-3 text-left">Company Name</th>
              <th
                className="px-4 py-3 text-left cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('sector')}
              >
                Sector {getSortIcon('sector')}
              </th>
              <th className="px-4 py-3 text-left">Industry</th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('current_price')}
              >
                Current Price {getSortIcon('current_price')}
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
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('pe_ratio')}
              >
                PE Ratio {getSortIcon('pe_ratio')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('forward_pe')}
              >
                Forward PE {getSortIcon('forward_pe')}
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:bg-dark-border transition-colors"
                onClick={() => handleSort('investors_holding')}
              >
                Investors {getSortIcon('investors_holding')}
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedStocks.map((stock) => (
              <tr
                key={stock.symbol}
                className="border-b border-dark-border hover:bg-dark-surface transition-colors"
              >
                <td className="px-4 py-3 font-semibold">{stock.symbol}</td>
                <td className="px-4 py-3">{stock.company_name}</td>
                <td className="px-4 py-3 text-dark-muted">{stock.sector}</td>
                <td className="px-4 py-3 text-dark-muted text-sm">{stock.industry}</td>
                <td className="px-4 py-3 text-right font-semibold">
                  ${formatNumber(stock.current_price)}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    stock.daily >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(stock.daily)}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    stock['1m'] >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(stock['1m'])}
                </td>
                <td
                  className={`px-4 py-3 text-right ${
                    stock['3m'] >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(stock['3m'])}
                </td>
                <td
                  className={`px-4 py-3 text-right font-semibold ${
                    stock.ytd >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {formatPercent(stock.ytd)}
                </td>
                <td className="px-4 py-3 text-right text-dark-muted">
                  {formatNumber(stock.pe_ratio)}
                </td>
                <td className="px-4 py-3 text-right text-dark-muted">
                  {formatNumber(stock.forward_pe)}
                </td>
                <td className="px-4 py-3 text-right">{stock.investors_holding}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredAndSortedStocks.length === 0 && (
          <div className="text-center py-8 text-dark-muted">
            No stocks found matching your filters.
          </div>
        )}
      </div>
    </div>
  );
}

export default StocksOverview;
