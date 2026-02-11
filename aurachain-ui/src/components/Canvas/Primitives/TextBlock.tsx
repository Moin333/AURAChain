// src/components/Canvas/Primitives/TextBlock.tsx
import React from 'react';
import { clsx } from 'clsx';

interface TextBlockProps {
  title?: string;
  content?: string;
  items?: string[];
  variant?: 'default' | 'info' | 'success' | 'warning';
}

const TextBlock: React.FC<TextBlockProps> = ({ 
  title, 
  content, 
  items,
  variant = 'default' 
}) => {
  const variantStyles = {
    default: 'bg-slate-50 dark:bg-zinc-900 border-slate-200 dark:border-zinc-800',
    info: 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800',
    success: 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800',
    warning: 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800'
  };

  const textStyles = {
    default: 'text-slate-700 dark:text-zinc-300',
    info: 'text-blue-700 dark:text-blue-300',
    success: 'text-green-700 dark:text-green-300',
    warning: 'text-amber-700 dark:text-amber-300'
  };

  return (
    <div className={clsx(
      'p-4 rounded-xl border',
      variantStyles[variant]
    )}>
      {title && (
        <h4 className={clsx(
          'text-sm font-semibold mb-2',
          textStyles[variant]
        )}>
          {title}
        </h4>
      )}
      
      {content && (
        <p className={clsx(
          'text-sm leading-relaxed',
          textStyles[variant]
        )}>
          {content}
        </p>
      )}
      
      {items && items.length > 0 && (
        <ul className="space-y-2 mt-2">
          {items.map((item, idx) => (
            <li 
              key={idx} 
              className={clsx(
                'text-sm flex items-start',
                textStyles[variant]
              )}
            >
              <span className="mr-2 mt-0.5">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default TextBlock;