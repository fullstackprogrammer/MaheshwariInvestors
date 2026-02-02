/**
 * Text + SVG logo for Maheshwari Investors (no image asset).
 * Compact “MAI” mark with upward bars suggesting growth.
 */
function SiteLogo({ className = '' }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        viewBox="0 0 48 32"
        className="h-8 w-auto flex-shrink-0 text-amber-400"
        aria-hidden
      >
        {/* Upward bars (growth) */}
        <rect x="2" y="18" width="6" height="12" rx="1" fill="currentColor" opacity="0.9" />
        <rect x="10" y="14" width="6" height="16" rx="1" fill="currentColor" />
        <rect x="18" y="10" width="6" height="20" rx="1" fill="currentColor" />
        <rect x="26" y="6" width="6" height="24" rx="1" fill="currentColor" />
        <rect x="34" y="2" width="6" height="28" rx="1" fill="currentColor" />
      </svg>
      <span className="font-bold text-white text-lg tracking-tight">
        Mahesh<span className="text-amber-400">AI</span>
      </span>
    </div>
  );
}

export default SiteLogo;
