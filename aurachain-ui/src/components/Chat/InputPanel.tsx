// aurachain-ui/src/components/Chat/InputPanel.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Paperclip, Send, Loader2, X, FileText, Maximize2, Minimize2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useUIStore } from '../../store/uiStore';

interface InputPanelProps {
  isZeroState?: boolean;
}

const InputPanel: React.FC<InputPanelProps> = ({ isZeroState = false }) => {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showExpandIcon, setShowExpandIcon] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { sendMessage, uploadDataset, isThinking } = useUIStore();

  const MAX_HEIGHT = 200;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      
      setShowExpandIcon(scrollHeight > MAX_HEIGHT);
      
      const newHeight = isExpanded ? 400 : Math.min(scrollHeight, MAX_HEIGHT);
      textarea.style.height = `${newHeight}px`;
    }
  }, [text, isExpanded]);

  const handleSubmit = async () => {
    if ((!text.trim() && !file) || isThinking) return;

    if (file) {
      await uploadDataset(file);
      setFile(null);
    }

    if (text.trim()) {
      await sendMessage(text);
      setText('');
      setIsExpanded(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className={clsx(
      "transition-all duration-300 ease-in-out z-20",
      isZeroState ? "p-0" : "w-full max-w-3xl mx-auto px-4 pb-6"
    )}>
      <div className="mx-auto relative w-full">
        {/* File Preview Chip - DARK MODE POLISHED */}
        {file && (
          <div className="absolute -top-12 left-0 right-0 mx-2 p-2 bg-primary-50 dark:bg-primary-900/20 border border-primary-100 dark:border-primary-800 rounded-lg flex items-center justify-between animate-slide-in">
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="p-1.5 bg-white dark:bg-primary-800/50 rounded-md text-primary-600 dark:text-primary-300">
                <FileText size={16} />
              </div>
              <span className="text-xs font-medium text-primary-700 dark:text-primary-200 truncate max-w-[200px]">
                {file.name}
              </span>
              <span className="text-[10px] text-primary-500 dark:text-primary-400">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            </div>
            <button 
              onClick={() => setFile(null)} 
              className="p-1 hover:bg-primary-100 dark:hover:bg-primary-800 rounded-full text-primary-500 dark:text-primary-400 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Main Input Container - DARK MODE POLISHED */}
        <div className={clsx(
          "flex flex-col bg-light-elevated dark:bg-dark-elevated border border-slate-200 dark:border-zinc-700 focus-within:ring-2 focus-within:ring-primary-100 dark:focus-within:ring-primary-900/30 transition-all rounded-2xl overflow-hidden shadow-xl-light dark:shadow-none dark:ring-1 dark:ring-zinc-800",
          isThinking && "opacity-80 pointer-events-none"
        )}>
          {/* Textarea - DARK MODE POLISHED */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isThinking ? "Agent is working..." : "Ask AURAChain..."}
            className={clsx(
              "w-full py-4 px-4 bg-transparent border-none focus:ring-0 outline-none resize-none text-slate-800 dark:text-zinc-100 placeholder:text-slate-400 dark:placeholder:text-zinc-500 custom-scrollbar overflow-y-auto",
              isZeroState ? "text-lg" : "text-sm"
            )}
            style={{ minHeight: isZeroState ? '80px' : '60px' }}
          />

          {/* Action Bar - DARK MODE POLISHED */}
          <div className="flex items-center justify-between px-2 pb-2 mt-auto border-t border-slate-100 dark:border-zinc-800 pt-2">
            <div className="flex items-center gap-1">
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={(e) => setFile(e.target.files?.[0] || null)} 
                className="hidden" 
                accept=".csv,.xlsx,.json" 
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2 text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                title="Attach data file"
              >
                <Paperclip size={20} />
              </button>

              {showExpandIcon && (
                <button 
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="p-2 text-slate-400 dark:text-zinc-500 hover:text-primary-500 dark:hover:text-primary-400 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                  title={isExpanded ? "Collapse" : "Expand"}
                >
                  {isExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </button>
              )}
            </div>

            <button
              onClick={handleSubmit}
              disabled={(!text.trim() && !file) || isThinking}
              className={clsx(
                "p-2 rounded-lg shadow-sm transition-all",
                (text.trim() || file) && !isThinking
                  ? "bg-primary-600 hover:bg-primary-700 text-white shadow-primary-500/20"
                  : "bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-600 cursor-not-allowed"
              )}
            >
              {isThinking ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InputPanel;