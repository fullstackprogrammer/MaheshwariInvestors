function KPICard({ rank, title, value, subtitle, type }) {
  const isPositive = value >= 0;
  
  return (
    <div className="bg-dark-surface border border-dark-border rounded-lg p-4 hover:border-blue-500 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-semibold text-blue-400">#{rank}</span>
        <span className={`text-lg font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}%
        </span>
      </div>
      <h4 className="font-semibold text-white mb-1">{title}</h4>
      <p className="text-xs text-dark-muted line-clamp-2">{subtitle}</p>
    </div>
  );
}

export default KPICard;
