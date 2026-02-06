# aura_chain/app/api/routes/sse.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
import asyncio
import json
from loguru import logger
from app.config import get_settings
from app.core.streaming import streaming_service

router = APIRouter(prefix="/sse", tags=["sse"])
settings = get_settings()

@router.get("/stream/{session_id}")
async def agent_stream(session_id: str):
    """
    Server-Sent Events endpoint for real-time agent updates
    
    Usage:
        const eventSource = new EventSource('/api/v1/sse/stream/session_123');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data);
        };
    """
    
    async def event_generator():
        """Generate SSE events from Redis pub/sub"""
        redis_client = None
        pubsub = None
        
        try:
            # Connect to Redis
            redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Subscribe to session channel
            channel_name = f"session:{session_id}:stream"
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel_name)
            
            logger.info(f"✓ SSE client connected to session {session_id}")
            
            # Send initial connection event
            connection_event = {
                "type": "connected",
                "session_id": session_id,
                "timestamp": asyncio.get_event_loop().time()
            }
            yield f"data: {json.dumps(connection_event)}\n\n"
            
            # Send heartbeat every 15 seconds to keep connection alive
            last_heartbeat = asyncio.get_event_loop().time()
            
            # Listen for messages
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    # Forward Redis message to SSE client
                    yield f"data: {message['data']}\n\n"
                    
                    # Check if workflow completed
                    try:
                        event_data = json.loads(message['data'])
                        if event_data.get('type') == 'workflow_completed':
                            logger.info(f"✓ Workflow completed for session {session_id}")
                            # Send final event and close
                            yield f"data: {json.dumps({'type': 'stream_ended'})}\n\n"
                            break
                    except:
                        pass
                
                # Send periodic heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > 15:
                    heartbeat = {"type": "heartbeat", "timestamp": current_time}
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                    last_heartbeat = current_time
        
        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected from session {session_id}")
            raise
        
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        
        finally:
            # Cleanup
            if pubsub:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
            if redis_client:
                await redis_client.close()
            logger.info(f"✓ SSE connection closed for session {session_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",  # CORS for SSE
        }
    )

@router.get("/health/{session_id}")
async def check_stream_health(session_id: str):
    """Check if there are active subscribers for a session"""
    try:
        redis_client = await redis.from_url(settings.REDIS_URL)
        channel_name = f"session:{session_id}:stream"
        
        # Check number of subscribers
        pubsub_channels = await redis_client.pubsub_channels(pattern=channel_name)
        await redis_client.close()
        
        return {
            "session_id": session_id,
            "active": len(pubsub_channels) > 0,
            "channel": channel_name
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))