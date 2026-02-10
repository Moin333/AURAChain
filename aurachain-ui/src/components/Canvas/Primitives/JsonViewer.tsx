// src/components/Canvas/Primitives/JsonViewer.tsx
import React, { useState } from 'react';
import { clsx } from 'clsx';
import { Copy, Check } from 'lucide-react';

interface JsonViewerProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  title?: string;
  maxHeight?: string;
}

const JsonViewer: React.FC<JsonViewerProps> = ({ 
  data, 
  title,
  maxHeight = '500px' 
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-3">
      {title && (
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
            {title}
          </h3>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2 py-1 text-xs bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded transition-colors"
          >
            {copied ? (
              <>
                <Check size={12} className="text-green-500" />
                <span>Copied!</span>
              </>
            ) : (
              <>
                <Copy size={12} />
                <span>Copy JSON</span>
              </>
            )}
          </button>
        </div>
      )}
      
      <div 
        className={clsx(
          'bg-slate-900 dark:bg-zinc-950 text-slate-300 dark:text-zinc-400',
          'p-4 rounded-xl text-xs font-mono overflow-auto',
          'border border-slate-700 dark:border-zinc-800'
        )}
        style={{ maxHeight }}
      >
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
};

export default JsonViewer;