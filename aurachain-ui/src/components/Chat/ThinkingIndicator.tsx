// aurachain-ui/src/components/Chat/ThinkingIndicator.tsx
import React from 'react';
import { InfinityIcon } from 'lucide-react';


const ThinkingIndicator: React.FC = () => {
  return (
    <div className="flex items-center gap-3 mb-6 animate-fade-in">
      {/* Infinity Icon with Continuous Alternating Rotation */}
      <div className="flex-shrink-0">
        <InfinityIcon 
          size={32} 
          className="text-primary animate-rotate-alternate" 
          strokeWidth={2.5} 
        />
      </div>
    </div>
  );
};

export default ThinkingIndicator;