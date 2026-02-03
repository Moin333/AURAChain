import React from 'react';
import { clsx } from 'clsx';
import { 
  Infinity as InfinityIcon, 
  Database, 
  PanelLeft,
  PanelLeftClose,
  Plus 
} from 'lucide-react';
import SessionList from './SessionList';
import UserProfile from './UserProfile';
import { useUIStore } from '../../store/uiStore';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onToggle }) => {
  const { resetSession } = useUIStore();

  return (
    <aside 
      className={clsx(
        "flex-shrink-0 flex flex-col border-r border-light-border dark:border-dark-border bg-light-surface dark:bg-dark-surface transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] relative z-20",
        isOpen ? "w-[280px]" : "w-[72px]"
      )}
    >
      {/* Top Section */}
      <div className={clsx(
        "h-16 flex items-center transition-all duration-300",
        isOpen ? "justify-between px-3" : "justify-center px-2"
      )}>
        
        {isOpen && (
          <div className="flex items-center gap-3 overflow-hidden fade-in duration-300">
             <div className="relative w-8 h-8 flex items-center justify-center flex-shrink-0">
               <InfinityIcon size={32} strokeWidth={2.5} className="text-primary-500" />
             </div>
             <h1 className="font-heading font-bold text-2xl tracking-tight text-primary-500">
               AURAChain
             </h1>
          </div>
        )}

        <button
          onClick={onToggle}
          className={clsx(
            "rounded-lg transition-colors flex-shrink-0 flex items-center justify-center",
            "hover:bg-slate-100 dark:hover:bg-zinc-800 hover:text-slate-600 dark:hover:text-zinc-200",
            isOpen ? "p-2 text-slate-400 dark:text-zinc-500" : "w-12 h-12 text-slate-500 dark:text-zinc-400"
          )}
          title={isOpen ? "Collapse Sidebar" : "Expand Sidebar"}
        >
          {isOpen ? <PanelLeftClose size={20} /> : <PanelLeft size={24} />}
        </button>

      </div>

      {/* Data Connectivity Status */}
      <div className={clsx(
        "flex items-center transition-all duration-300 py-3",
        isOpen ? "px-3 gap-3" : "justify-center px-3"
      )}>
        <div className="flex-shrink-0 flex items-center justify-center w-12 h-12 text-slate-500 dark:text-zinc-400">
           <Database size={24} strokeWidth={1.5} />
        </div>

        <div className={clsx(
          "flex-1 flex items-center justify-between overflow-hidden transition-all duration-300",
          isOpen ? "w-auto opacity-100" : "w-0 opacity-0"
        )}>
           <span className="text-sm font-medium text-slate-700 dark:text-zinc-300 whitespace-nowrap">
             Data Sources
           </span>
           <span className="flex items-center text-[10px] font-bold text-accent-teal bg-accent-teal/10 dark:bg-accent-teal/20 px-2 py-0.5 rounded-full">
             <span className="w-1.5 h-1.5 rounded-full bg-accent-teal mr-1.5 animate-pulse"></span>
             3 Active
           </span>
        </div>
      </div>

      {/* NEW SESSION BUTTON */}
      <div className={clsx(
        "py-2 transition-all duration-300",
        isOpen ? "px-3" : "px-2 flex justify-center"
      )}>
        <button
          onClick={resetSession}
          className={clsx(
            "flex items-center justify-center transition-all duration-200 rounded-xl border border-dashed border-slate-300 dark:border-zinc-700 hover:border-primary-400 dark:hover:border-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/20 group",
            isOpen ? "w-full py-2.5" : "w-12 h-12" 
          )}
          title="Start New Session"
        >
          <Plus size={20} className="text-slate-500 dark:text-zinc-400 group-hover:text-primary-500 transition-colors" />
          {isOpen && (
            <span className="ml-2 text-sm font-medium text-slate-600 dark:text-zinc-300 group-hover:text-primary-600 dark:group-hover:text-primary-400 whitespace-nowrap transition-colors">
              New Session
            </span>
          )}
        </button>
      </div>

      {/* Scrollable Session List */}
      <SessionList isOpen={isOpen} />

      {/* Bottom: User Profile */}
      <UserProfile isOpen={isOpen} />
    </aside>
  );
};

export default Sidebar;