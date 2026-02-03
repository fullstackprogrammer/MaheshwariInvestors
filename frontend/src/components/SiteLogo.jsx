/**
 * Title text for MAI - Maheshwari Ansh Index (no logo).
 */
function SiteLogo({ className = '' }) {
  return (
    <div className={`flex items-center ${className}`}>
      <span className="font-bold text-white text-lg tracking-tight">
        MAI - Maheshwari Ansh Index
      </span>
    </div>
  );
}

export default SiteLogo;
