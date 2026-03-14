# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.core.memory import session_manager, memory_manager
from app.core.streaming import streaming_service
from app.core.registry import register_all_agents
from app.core.artifacts import artifact_store
from app.core.shared_context import shared_context
from app.core.rate_limiter import rate_limiter
from app.core.checkpoints import workflow_checkpoint
from app.core.reasoning_trace import reasoning_trace_store
from app.core.experiments import experiment_logger
from app.core.tool_registry import tool_registry, register_default_tools
from app.core.decision_memory import decision_memory
from app.api.routes import orchestrator, data, analytics, health, sse, reports
from app.api.routes import experiments as experiments_routes
from app.api.routes import decisions as decisions_routes
from app.api.routes import visualization as visualization_routes

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    try:
        await session_manager.initialize()
        await memory_manager.initialize()
        await streaming_service.initialize()
        await artifact_store.initialize()
        await shared_context.initialize()
        await rate_limiter.initialize()
        await workflow_checkpoint.initialize()
        await reasoning_trace_store.initialize()
        await experiment_logger.initialize()
        await tool_registry.initialize()
        await decision_memory.initialize()
        register_all_agents()
        register_default_tools()
        print("✓ All systems initialized")
    except Exception as e:
        print(f"Warning: Initialization failed: {e}")
    
    yield
    
    # Shutdown
    try:
        await session_manager.close()
        await memory_manager.close()
        await streaming_service.close()
        await artifact_store.close()
        await shared_context.close()
        await rate_limiter.close()
        await workflow_checkpoint.close()
        await reasoning_trace_store.close()
        await experiment_logger.close()
        await tool_registry.close()
        await decision_memory.close()
        print("✓ All systems closed")
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orchestrator.router, prefix=settings.API_PREFIX)
app.include_router(data.router, prefix=settings.API_PREFIX)
app.include_router(analytics.router, prefix=settings.API_PREFIX)
app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(sse.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(experiments_routes.router, prefix=settings.API_PREFIX)
app.include_router(decisions_routes.router, prefix=settings.API_PREFIX)
app.include_router(visualization_routes.router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": f"{settings.API_PREFIX}/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )