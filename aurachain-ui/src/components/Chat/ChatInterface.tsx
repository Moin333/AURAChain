// src/components/Chat/ChatInterface.tsx
import React, { useEffect, useRef, useMemo } from 'react';
import { clsx } from 'clsx';
import { Infinity as InfinityIcon, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import MessageBubble, { type Message } from './MessageBubble';
import InputPanel from './InputPanel';
import ThinkingIndicator from './ThinkingIndicator';
import { useUIStore } from '../../store/uiStore';
import { useAgentStream } from '../../hooks/useAgentStream';

const ChatInterface: React.FC = () => {
  const {
    messages,
    isThinking,
    processingStep,
    setRightPanelOpen,
    isSidebarOpen,
    isRightPanelOpen,
    rightPanelWidth,
    sessionId,
  } = useUIStore();

  const { isConnected, error: streamError, reconnect } = useAgentStream(sessionId);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const analysisMessages = messages.filter(msg => msg.type === 'analysis');

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking, processingStep]);

  const getAnalysisTitle = (msg: Message, idx: number): string => {
    if (msg.text) return msg.text;
    if (msg.metadata?.title) return msg.metadata.title;

    const content = msg.metadata?.summary?.toLowerCase() || msg.text?.toLowerCase() || '';
    if (content.includes('forecast')) return 'Demand Forecast Analysis';
    if (content.includes('inventory')) return 'Inventory Analysis';
    if (content.includes('supplier')) return 'Supplier Analysis';
    if (content.includes('shipment')) return 'Shipment Analysis';
    if (content.includes('sales')) return 'Sales Analysis';
    if (content.includes('cost')) return 'Cost Analysis';
    if (content.includes('trend')) return 'Trend Analysis';
    if (msg.metadata?.agents) return 'Orchestration Plan';

    return `Analysis ${idx + 1}`;
  };

  const handleNodeClick = (msgId: string) => {
    const element = messageRefs.current.get(msgId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });

      element.style.transition = 'box-shadow 0.3s ease';
      element.style.boxShadow = '0 0 0 2px var(--primary-500, #3b82f6)';

      setTimeout(() => {
        element.style.boxShadow = '';
      }, 2000);
    }
    setRightPanelOpen(true);
  };

  const dynamicPaddingLeft = useMemo(() => {
    const sidebarWidth = isSidebarOpen ? 280 : 72;
    return sidebarWidth + 10;
  }, [isSidebarOpen]);

  const dynamicPaddingRight = useMemo(() => {
    return isRightPanelOpen ? Math.min(rightPanelWidth * 0.08, 80) : 32;
  }, [isRightPanelOpen, rightPanelWidth]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col h-full relative bg-light-bg dark:bg-dark-bg transition-colors duration-500">
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="mb-8 text-center animate-fade-in">
            <h1 className="text-4xl md:text-5xl font-heading font-medium text-slate-800 dark:text-zinc-100 mb-3 flex items-center justify-center gap-4">
              <InfinityIcon size={48} className="text-primary-500" strokeWidth={2.5} />
              Good Afternoon
            </h1>
            <p className="text-lg text-slate-500 dark:text-zinc-400 max-w-md mx-auto">
              Ready to orchestrate your supply chain agents?
            </p>
          </div>
          <div className="w-full max-w-2xl">
            <InputPanel isZeroState={true} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full relative bg-light-bg dark:bg-dark-bg">

      {/* Connection Status */}
      {sessionId && (
        <div className="absolute top-4 right-4 z-50">
          <div className={clsx(
            "flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-medium transition-all",
            isConnected 
              ? "bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400"
              : streamError?.includes('multiple attempts')
                ? "bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400"
                : "bg-yellow-500/10 border-yellow-500/20 text-yellow-600 dark:text-yellow-400"
          )}>
            {isConnected ? (
              <>
                <Wifi size={12} />
                <span>Live</span>
                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              </>
            ) : streamError?.includes('multiple attempts') ? (
              <>
                <WifiOff size={12} />
                <span>Disconnected</span>
                <button 
                  onClick={reconnect}
                  className="ml-1 p-1 hover:bg-red-500/20 rounded transition-colors"
                  title="Retry connection"
                >
                  <RefreshCw size={12} />
                </button>
              </>
            ) : (
              <>
                <WifiOff size={12} />
                <span>Connecting...</span>
              </>
            )}
          </div>
          
          <div className="mt-1 text-[9px] text-slate-400 dark:text-zinc-600 font-mono text-right">
            {sessionId.substring(0, 8)}...
          </div>
          
          {streamError && !streamError.includes('Reconnecting') && (
            <div className="mt-2 text-[10px] text-red-500 dark:text-red-400 max-w-[200px] text-right">
              {streamError}
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {analysisMessages.length > 0 && (
        <div
          className="fixed top-24 z-40 flex flex-col items-center pointer-events-none transition-all duration-300"
          style={{
            left: `${dynamicPaddingLeft}px`,
            height: '70vh',
            maxHeight: '700px'
          }}
        >
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-primary-200 dark:bg-primary-800" />

          <div className={clsx(
            "relative flex flex-col h-full py-2 pointer-events-auto",
            analysisMessages.length > 1 ? "justify-between" : "justify-start"
          )}>
            {analysisMessages.map((msg, idx) => (
              <button
                key={msg.id}
                onClick={() => handleNodeClick(msg.id)}
                className="relative group/node focus:outline-none"
                aria-label={`Jump to analysis at ${msg.timestamp || 'unknown time'}`}
                type="button"
              >
                <div className={clsx(
                  "w-3 h-3 rounded-full transition-all duration-200 relative z-10",
                  "ring-4 ring-light-bg dark:ring-dark-bg",
                  "hover:scale-150 hover:ring-2 cursor-pointer",
                  msg.status === 'processing'
                    ? "bg-primary-500 animate-pulse"
                    : msg.status === 'failed'
                      ? "bg-red-500"
                      : "bg-primary-500"
                )}>
                  {msg.status === 'processing' && (
                    <div className="absolute inset-0 bg-primary-500/40 rounded-full animate-ping" />
                  )}
                </div>

                <div className="absolute left-full ml-3 px-3 py-1.5 bg-slate-900 dark:bg-zinc-800 text-white text-xs font-medium rounded-lg opacity-0 group-hover/node:opacity-100 transition-opacity duration-200 whitespace-nowrap pointer-events-none shadow-lg z-50 min-w-max border border-zinc-700">
                  <div className="font-semibold">
                    {getAnalysisTitle(msg, idx)}
                  </div>
                  {msg.timestamp && (
                    <div className="text-slate-300 dark:text-zinc-400 text-[10px] mt-0.5">
                      {msg.timestamp}
                    </div>
                  )}
                  <div className="absolute top-1/2 -left-1 -mt-1 border-4 border-transparent border-r-slate-900 dark:border-r-zinc-800" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages Container */}
      <div 
        className="flex-1 overflow-y-auto custom-scrollbar"
        style={{
          paddingTop: '2rem',
          paddingBottom: '2rem',
          paddingLeft: `${dynamicPaddingLeft - 160}px`,
          paddingRight: `${dynamicPaddingRight}px`,
          transition: 'padding 300ms ease-out'
        }}
      >
        <div className="max-w-3xl mx-auto relative">

          {messages.map((msg, index) => (
            <div
              key={msg.id}
              ref={(el) => {
                if (el) {
                  messageRefs.current.set(msg.id, el);
                } else {
                  messageRefs.current.delete(msg.id);
                }
              }}
              className="relative mb-6 transition-all duration-300 rounded-lg"
            >
              <MessageBubble
                message={msg}
                isLast={index === messages.length - 1}
              />
            </div>
          ))}

          {isThinking && (
            <ThinkingIndicator />
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      <InputPanel isZeroState={false} />
    </div>
  );
};

export default ChatInterface;