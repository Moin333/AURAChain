// aurachain-ui/src/hooks/useAgentStream.ts
import { useEffect, useRef, useState, useCallback } from 'react';
import { useUIStore } from '../store/uiStore';

interface StreamEvent {
  type: 
    | 'connected' 
    | 'agent_started' 
    | 'agent_progress' 
    | 'agent_completed' 
    | 'agent_failed'
    | 'workflow_completed'
    | 'heartbeat'
    | 'stream_ended'
    | 'error';
  agent?: string;
  data?: any;
  timestamp: string;
}

interface UseAgentStreamReturn {
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
}

export const useAgentStream = (sessionId: string | null): UseAgentStreamReturn => {
  const { 
    updateAgentStatus, 
    updateAgentProgress, 
    updateAgentData,
    setRightPanelOpen 
  } = useUIStore();
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!sessionId) {
      console.log('⏸ No session ID, skipping SSE connection');
      return;
    }

    cleanup();

    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
    const url = `${API_URL}/sse/stream/${sessionId}`;
    
    console.log(`🔌 Connecting to SSE: ${url}`);
    
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('✅ SSE Connected');
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const update: StreamEvent = JSON.parse(event.data);
        
        console.log('📡 SSE Event:', update.type, update.agent);
        
        switch (update.type) {
          case 'connected':
            console.log('✓ SSE stream initialized');
            break;
            
          case 'agent_started':
            if (update.agent) {
              updateAgentStatus(update.agent, 'processing');
              updateAgentProgress(update.agent, 0, update.data?.task || 'Starting...');
              // Auto-open right panel when first agent starts
              setRightPanelOpen(true);
            }
            break;
            
          case 'agent_progress':
            if (update.agent && update.data) {
              updateAgentProgress(
                update.agent,
                update.data.progress || 0,
                update.data.current_activity || 'Processing...',
                update.data.metrics || {}
              );
            }
            break;
            
          case 'agent_completed':
            if (update.agent) {
              updateAgentStatus(update.agent, 'completed');
              updateAgentProgress(update.agent, 100, 'Completed');
              
              // Store agent result data
              if (update.data?.result) {
                updateAgentData(update.agent, update.data.result);
              }
            }
            break;
            
          case 'agent_failed':
            if (update.agent) {
              updateAgentStatus(update.agent, 'failed');
              updateAgentProgress(update.agent, 0, `Failed: ${update.data?.error || 'Unknown error'}`);
            }
            break;
            
          case 'workflow_completed':
            console.log('✅ Workflow completed');
            // Don't close connection yet - let stream_ended handle it
            break;
            
          case 'stream_ended':
            console.log('🏁 Stream ended by server');
            cleanup();
            setIsConnected(false);
            break;
            
          case 'heartbeat':
            // Keep-alive ping, no action needed
            break;
            
          case 'error':
            console.error('❌ Server error:', update.data?.message);
            setError(update.data?.message || 'Unknown error');
            break;
            
          default:
            console.log('Unknown event type:', update.type);
        }
      } catch (err) {
        console.error('Failed to parse SSE message:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('❌ SSE Error:', err);
      setIsConnected(false);
      setError('Connection lost');
      
      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('🔄 Attempting to reconnect...');
        connect();
      }, 3000);
    };
  }, [sessionId, cleanup, updateAgentStatus, updateAgentProgress, updateAgentData, setRightPanelOpen]);

  useEffect(() => {
    connect();
    return cleanup;
  }, [connect, cleanup]);

  return { 
    isConnected, 
    error,
    reconnect: connect 
  };
};