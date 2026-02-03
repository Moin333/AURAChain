// aurachain-ui/src/components/Shared/ThemeToggle.tsx
import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';

const ThemeToggle: React.FC = () => {
  const { isDarkMode, toggleTheme } = useUIStore();

  return (
    <button
      onClick={toggleTheme}
      className="
        group
        relative
        w-14 h-8
        rounded-none
        bg-slate-200 dark:bg-zinc-800
        border border-slate-300 dark:border-zinc-700
        transition-all duration-200
        hover:border-primary-500 dark:hover:border-primary-500
        hover:shadow-[0_0_8px_rgba(74,144,226,0.3)] dark:hover:shadow-[0_0_8px_rgba(74,144,226,0.2)]
        focus:outline-none
        focus-visible:ring-2
        focus-visible:ring-primary-500
        focus-visible:ring-offset-2
        focus-visible:ring-offset-light-bg dark:focus-visible:ring-offset-dark-bg
      "
      aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {/* Slider */}
      <div
        className={`
          absolute top-0 left-0
          w-7 h-full
          bg-white dark:bg-zinc-100
          border-r border-slate-300 dark:border-zinc-600
          flex items-center justify-center
          transition-all duration-200 ease-in-out
          rounded-none
          shadow-sm
          ${isDarkMode ? 'translate-x-full border-l dark:border-l-zinc-600' : 'translate-x-0'}
        `}
      >
        {isDarkMode ? (
          <Moon className="w-4 h-4 text-zinc-900" strokeWidth={2} />
        ) : (
          <Sun className="w-4 h-4 text-amber-500" strokeWidth={2} />
        )}
      </div>

      {/* Edgy Corner Indicators (Optional Industrial Detail) */}
      <div className="absolute top-0 left-0 w-1 h-1 border-t border-l border-current opacity-30 pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-1 h-1 border-b border-r border-current opacity-30 pointer-events-none" />
    </button>
  );
};

export default ThemeToggle;