# app/core/memory.py
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import redis.asyncio as redis
import json
from app.config import get_settings
from loguru import logger

settings = get_settings()

# ==================== MODELS ====================

class Message(BaseModel):
    """Single message in conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class Session(BaseModel):
    """Container for immediate conversation history"""
    session_id: str
    user_id: str
    messages: List[Message] = []
    created_at: datetime
    last_activity: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to session"""
        self.messages.append(Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata
        ))
        self.last_activity = datetime.utcnow()
    
    def get_context_window(self, max_messages: int = 20) -> List[Dict[str, str]]:
        """Get recent messages formatted for LLM context"""
        recent = self.messages[-max_messages:]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent
        ]

class Memory(BaseModel):
    """Long-term persistence across sessions"""
    user_id: str
    facts: Dict[str, Any] = {}  # Extracted facts about user
    preferences: Dict[str, Any] = {}  # User preferences
    history_summary: List[str] = []  # Summarized past interactions
    entities: Dict[str, Any] = {}  # Named entities (companies, products, etc.)
    last_updated: datetime
    
    def update_fact(self, key: str, value: Any):
        """Update or add a fact"""
        self.facts[key] = value
        self.last_updated = datetime.utcnow()
    
    def update_preference(self, key: str, value: Any):
        """Update user preference"""
        self.preferences[key] = value
        self.last_updated = datetime.utcnow()
    
    def add_entity(self, entity_type: str, entity_name: str, data: Dict[str, Any]):
        """Add or update entity"""
        if entity_type not in self.entities:
            self.entities[entity_type] = {}
        self.entities[entity_type][entity_name] = data
        self.last_updated = datetime.utcnow()


# ==================== SESSION MANAGER ====================

class SessionManager:
    """Manages working memory within sessions"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"session:{session_id}"
    
    async def create_session(self, user_id: str, session_id: str) -> Session:
        """Create new session"""
        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        await self.redis_client.setex(
            self._session_key(session_id),
            settings.REDIS_TTL,
            session.model_dump_json()
        )
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session"""
        data = await self.redis_client.get(self._session_key(session_id))
        if data:
            return Session.model_validate_json(data)
        return None
    
    async def update_session(self, session: Session):
        """Update session in Redis"""
        await self.redis_client.setex(
            self._session_key(session.session_id),
            settings.REDIS_TTL,
            session.model_dump_json()
        )
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """Add message to session"""
        session = await self.get_session(session_id)
        if session:
            session.add_message(role, content, metadata)
            await self.update_session(session)
        else:
            logger.warning(f"Session {session_id} not found")
    
    async def get_conversation_history(
        self,
        session_id: str,
        max_messages: int = 20
    ) -> List[Dict[str, str]]:
        """Get conversation history for LLM context"""
        session = await self.get_session(session_id)
        if session:
            return session.get_context_window(max_messages)
        return []
    
    async def delete_session(self, session_id: str):
        """Delete session"""
        await self.redis_client.delete(self._session_key(session_id))
        logger.info(f"Deleted session {session_id}")


# ==================== MEMORY MANAGER ====================

class MemoryManager:
    """Manages long-term memory across sessions"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _memory_key(self, user_id: str) -> str:
        """Generate Redis key for memory"""
        return f"memory:{user_id}"
    
    async def get_memory(self, user_id: str) -> Memory:
        """Retrieve or create user memory"""
        data = await self.redis_client.get(self._memory_key(user_id))
        if data:
            return Memory.model_validate_json(data)
        
        # Create new memory
        memory = Memory(
            user_id=user_id,
            last_updated=datetime.utcnow()
        )
        await self.save_memory(memory)
        return memory
    
    async def save_memory(self, memory: Memory):
        """Persist memory to Redis"""
        await self.redis_client.set(
            self._memory_key(memory.user_id),
            memory.model_dump_json()
        )
    
    async def update_from_conversation(
        self,
        user_id: str,
        messages: List[Message],
        extracted_info: Dict[str, Any]
    ):
        """Update memory based on conversation"""
        memory = await self.get_memory(user_id)
        
        # Update facts
        if "facts" in extracted_info:
            for key, value in extracted_info["facts"].items():
                memory.update_fact(key, value)
        
        # Update preferences
        if "preferences" in extracted_info:
            for key, value in extracted_info["preferences"].items():
                memory.update_preference(key, value)
        
        # Add entities
        if "entities" in extracted_info:
            for entity_type, entities in extracted_info["entities"].items():
                for entity_name, entity_data in entities.items():
                    memory.add_entity(entity_type, entity_name, entity_data)
        
        await self.save_memory(memory)
        logger.info(f"Updated memory for user {user_id}")
    
    async def get_relevant_context(
        self,
        user_id: str,
        query: str
    ) -> Dict[str, Any]:
        """Get relevant memory context via semantic search."""
        memory = await self.get_memory(user_id)
        
        # Try embedding-based search
        try:
            model = self._get_embedding_model()
            if model and memory.facts:
                relevant_facts = await self._semantic_search(
                    user_id, query, memory.facts, model, top_k=5
                )
                return {
                    "facts": relevant_facts,
                    "preferences": memory.preferences,
                    "entities": memory.entities
                }
        except Exception as e:
            logger.warning(f"Semantic search fallback: {e}")
        
        # Fallback: return all
        return {
            "facts": memory.facts,
            "preferences": memory.preferences,
            "entities": memory.entities
        }
    
    def _get_embedding_model(self):
        """Lazy-load sentence-transformers model."""
        if not hasattr(self, '_embed_model'):
            try:
                from sentence_transformers import SentenceTransformer
                self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("✓ Embedding model loaded (all-MiniLM-L6-v2)")
            except ImportError:
                logger.warning("sentence-transformers not installed — using fallback")
                self._embed_model = None
        return self._embed_model
    
    async def _semantic_search(
        self, user_id: str, query: str, facts: Dict, model, top_k: int = 5
    ) -> Dict[str, Any]:
        """Embed query and return top-k most relevant facts by cosine similarity."""
        import numpy as np
        
        # Embed query
        query_emb = model.encode(query, normalize_embeddings=True)
        
        # Embed all facts (text representation)
        fact_items = list(facts.items())
        if not fact_items:
            return facts
        
        fact_texts = [f"{k}: {v}" for k, v in fact_items]
        fact_embs = model.encode(fact_texts, normalize_embeddings=True)
        
        # Cosine similarity (embeddings are normalized, so dot product = cosine)
        similarities = np.dot(fact_embs, query_emb)
        
        # Top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Return only relevant facts
        relevant = {}
        for idx in top_indices:
            if similarities[idx] > 0.2:  # Minimum relevance threshold
                key, value = fact_items[idx]
                relevant[key] = value
        
        return relevant if relevant else facts  # Fallback if nothing relevant
    
    async def summarize_session(
        self,
        user_id: str,
        session: Session
    ) -> str:
        """Create summary of session for long-term storage"""
        # This would use an LLM to create summary
        # For now, simple extraction
        message_count = len(session.messages)
        topics = []  # Extract topics from messages
        
        summary = f"Session on {session.created_at.date()}: {message_count} messages exchanged"
        
        memory = await self.get_memory(user_id)
        memory.history_summary.append(summary)
        await self.save_memory(memory)
        
        return summary


# ==================== CONTEXT ENGINEERING ====================

class ContextEngineer:
    """Dynamically assemble context window for agents"""
    
    def __init__(
        self,
        session_manager: SessionManager,
        memory_manager: MemoryManager
    ):
        self.session_manager = session_manager
        self.memory_manager = memory_manager
    
    async def build_context(
        self,
        session_id: str,
        user_id: str,
        current_query: str,
        max_history: int = 10
    ) -> Dict[str, Any]:
        """Build complete context for agent"""
        
        # Get session history
        history = await self.session_manager.get_conversation_history(
            session_id,
            max_history
        )
        
        # Get relevant long-term memory
        memory_context = await self.memory_manager.get_relevant_context(
            user_id,
            current_query
        )
        
        # Assemble context
        context = {
            "conversation_history": history,
            "user_facts": memory_context.get("facts", {}),
            "user_preferences": memory_context.get("preferences", {}),
            "known_entities": memory_context.get("entities", {}),
            "current_query": current_query
        }
        
        return context
    
    def format_system_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into system prompt"""
        prompt_parts = []
        
        if context.get("user_facts"):
            facts_str = "\n".join([
                f"- {k}: {v}" for k, v in context["user_facts"].items()
            ])
            prompt_parts.append(f"Known facts about user:\n{facts_str}")
        
        if context.get("user_preferences"):
            prefs_str = "\n".join([
                f"- {k}: {v}" for k, v in context["user_preferences"].items()
            ])
            prompt_parts.append(f"User preferences:\n{prefs_str}")
        
        if context.get("known_entities"):
            prompt_parts.append(
                f"Known entities: {json.dumps(context['known_entities'], indent=2)}"
            )
        
        return "\n\n".join(prompt_parts)


# Global instances
session_manager = SessionManager()
memory_manager = MemoryManager()
context_engineer = ContextEngineer(session_manager, memory_manager)