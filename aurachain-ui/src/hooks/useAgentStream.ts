// aurachain-ui/src/hooks/useAgentStream.ts
import { useEffect, useRef, useState } from 'react';
import { useUIStore } from '../store/uiStore';

interface StreamEvent {
  type: 
    | 'connected' 
    | 'workflow_started'
    | 'agent_started' 
    | 'agent_progress' 
    | 'agent_completed' 
    | 'agent_failed'
    | 'workflow_completed'
    | 'workflow_failed'
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
    setRightPanelOpen,
    handleWorkflowStarted,
    handleWorkflowCompleted
  } = useUIStore();
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      console.log('⏸ No session ID, skipping SSE connection');
      return;
    }

    // 🔥 FIX: Detect if this is a new connection or reconnection
    const isNewSession = sessionIdRef.current !== sessionId;
    sessionIdRef.current = sessionId;

    console.log(`🔌 useAgentStream: ${isNewSession ? 'New' : 'Reconnecting to'} session ${sessionId}`);

    // FIXED: Proper cleanup function
    const cleanup = () => {
      if (eventSourceRef.current) {
        // Remove listeners BEFORE closing
        console.log(`🔌 Closing SSE connection for session ${sessionId}`);
        eventSourceRef.current.onopen = null;
        eventSourceRef.current.onmessage = null;
        eventSourceRef.current.onerror = null;
        
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        console.log('🔌 SSE connection closed');
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    cleanup(); // Clean up any existing connection

    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
    const url = `${API_URL}/sse/stream/${sessionId}`;
    
    console.log(`🔌 Connecting to SSE: ${url}`);
    
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('✅ SSE Connected');
      setIsConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0; // Reset on successful connection
    };

    eventSource.onmessage = (event) => {
      try {
        const update: StreamEvent = JSON.parse(event.data);
        
        console.log('📡 SSE Event:', update.type, update.agent || '');
        
        switch (update.type) {
          case 'connected':
            console.log('✓ SSE stream initialized');
            break;
          
          // 🔥 NEW: Workflow started
          case 'workflow_started':
            if (update.data?.agents) {
              handleWorkflowStarted(update.data.agents);
              setRightPanelOpen(true);
            }
            break;
            
          case 'agent_started':
            if (update.agent) {
              updateAgentStatus(update.agent, 'processing');
              updateAgentProgress(update.agent, 0, update.data?.task || 'Starting...');
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
          
          // NEW: Workflow completed
          case 'workflow_completed':
            console.log('✅ Workflow completed - keeping connection alive');
            handleWorkflowCompleted();
            // DON'T call cleanup() - connection stays open!
            break;
          
          // NEW: Workflow failed
          case 'workflow_failed':
            console.error('❌ Workflow failed:', update.data?.error);
            setError(update.data?.error || 'Workflow failed');
            handleWorkflowCompleted();
            // DON'T call cleanup() - connection stays open!
            break;
            
          case 'stream_ended':
            console.log('🏁 Stream ended by server - will reconnect if needed');
            // Backend explicitly closed the stream
            setIsConnected(false);
            // Don't cleanup yet - let onerror handle reconnection
            break;
            
          case 'heartbeat':
            // Keep-alive ping - no action needed
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

    // 🔥 FIX: Better error handling - reconnect when connection drops
    eventSource.onerror = (err) => {
      console.error('❌ SSE Error:', err);
      setIsConnected(false);
      
      // Check if EventSource is closed
      if (eventSourceRef.current?.readyState === EventSource.CLOSED) {
        console.log('🔌 Connection closed, will reconnect...');
        
        // Attempt reconnection with exponential backoff
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectAttemptsRef.current++;
          
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          setError(`Reconnecting... (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            cleanup();
            // Force re-render by toggling state
            setIsConnected(false);
            // The useEffect will run again because we'll trigger it manually
            
            // Recreate connection immediately
            const newEventSource = new EventSource(url);
            eventSourceRef.current = newEventSource;
            
            newEventSource.onopen = () => {
              console.log(`✅ SSE Reconnected to session ${sessionId}`);
              setIsConnected(true);
              setError(null);
              reconnectAttemptsRef.current = 0;
            };
            
            newEventSource.onmessage = eventSource.onmessage;
            newEventSource.onerror = eventSource.onerror;
          }, delay);
        } else {
          console.error('❌ Max reconnection attempts reached');
          setError('Connection failed after multiple attempts. Please refresh the page.');
        }
      }
    };

    // Cleanup on unmount or sessionId change
    return cleanup;
  }, [sessionId, updateAgentStatus, updateAgentProgress, updateAgentData, setRightPanelOpen, handleWorkflowStarted, handleWorkflowCompleted]);

  // Manual reconnect function
  const reconnect = () => {
    console.log('🔄 Manual reconnect requested');
    reconnectAttemptsRef.current = 0;
    setIsConnected(false);
    setError(null);

    // Force reconnection by closing and nulling current connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    // Trigger useEffect to run again
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
  };

  return { 
    isConnected, 
    error,
    reconnect 
  };
};