import logoSrc from '../../logo.png';

/**
 * MAI - Maheshwari Ansh Index logo (used on login and in header).
 */
function SiteLogo({ className = '' }) {
  return (
    <div className={`flex items-center ${className}`}>
      <img
        src={logoSrc}
        alt="MAI - Maheshwari Ansh Index"
        className="block h-full w-auto object-contain"
      />
    </div>
  );
}

export default SiteLogo;
