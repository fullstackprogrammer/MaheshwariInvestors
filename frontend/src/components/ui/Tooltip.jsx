import { useState, useRef, useEffect } from 'react';

const HIDE_DELAY_MS = 120;

/**
 * Hover tooltip (shadcn-style). Wrap a trigger element; show content on hover.
 * Use for table header info icons. Delay before hide prevents flicker when moving to tooltip.
 */
export function Tooltip({ content, children, side = 'bottom' }) {
  const [open, setOpen] = useState(false);
  const hideTimeoutRef = useRef(null);

  const clearHideTimeout = () => {
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };

  useEffect(() => () => clearHideTimeout(), []);

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => {
        clearHideTimeout();
        setOpen(true);
      }}
      onMouseLeave={() => {
        hideTimeoutRef.current = setTimeout(() => setOpen(false), HIDE_DELAY_MS);
      }}
    >
      {children}
      {open && content && (
        <span
          className={`absolute z-50 px-2 py-1.5 text-xs font-normal text-white bg-gray-900 rounded shadow-lg whitespace-normal max-w-[220px] border border-gray-700 pointer-events-none ${side === 'top' ? 'bottom-full left-1/2 -translate-x-1/2 mb-0.5' : 'top-full left-1/2 -translate-x-1/2 mt-0.5'}`}
          role="tooltip"
        >
          {content}
        </span>
      )}
    </span>
  );
}

export function TooltipProvider({ children }) {
  return children;
}
