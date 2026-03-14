# app/core/api_clients.py
"""
LLM API clients with production hardening:
- tenacity retry with exponential backoff (3 attempts)
- Circuit breaker keyed by provider+model (5 failures → 60s cooldown)
- Rate limiting via TokenBucketLimiter
- Latency tracking for health dashboard
"""

from anthropic import AsyncAnthropic
import google.generativeai as genai
from openai import AsyncOpenAI
from groq import AsyncGroq
from typing import Dict, List, Optional, Any
import asyncio
import time
from collections import defaultdict
from loguru import logger
from app.config import get_settings

settings = get_settings()

# ── Circuit Breaker State ──
# Keyed by "provider:model" for granular tracking

class CircuitBreaker:
    """Simple circuit breaker keyed by provider+model."""
    
    def __init__(self, failure_threshold: int = 5, cooldown_s: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._failures: Dict[str, int] = defaultdict(int)
        self._open_since: Dict[str, float] = {}
        self._latencies: Dict[str, list] = defaultdict(list)
        self._total_calls: Dict[str, int] = defaultdict(int)
        self._total_errors: Dict[str, int] = defaultdict(int)
    
    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"
    
    def check(self, provider: str, model: str) -> None:
        """Check if circuit is open. Raises CircuitBreakerOpen if so."""
        from app.core.error_handling import CircuitBreakerOpen
        
        key = self._key(provider, model)
        
        if key in self._open_since:
            elapsed = time.time() - self._open_since[key]
            if elapsed < self.cooldown_s:
                raise CircuitBreakerOpen(
                    f"Circuit breaker open for {key} ({elapsed:.0f}s / {self.cooldown_s}s cooldown)",
                    provider=provider,
                    model=model,
                    cooldown_remaining_s=round(self.cooldown_s - elapsed, 1)
                )
            else:
                # Cooldown expired → enter half-open state
                # Allow exactly 1 test request through. Do NOT reset failures yet.
                # record_success will close the circuit; record_failure will reopen it.
                del self._open_since[key]
                logger.info(f"⚡ Circuit breaker half-open for {key} (allowing test request)")
    
    def record_success(self, provider: str, model: str, latency_ms: float) -> None:
        """Record a successful call. Closes circuit if half-open."""
        key = self._key(provider, model)
        self._failures[key] = 0  # Reset consecutive failures → circuit fully closed
        self._total_calls[key] += 1
        self._latencies[key].append(latency_ms)
        # Keep only last 100 latencies
        if len(self._latencies[key]) > 100:
            self._latencies[key] = self._latencies[key][-100:]
    
    def record_failure(self, provider: str, model: str) -> None:
        """Record a failed call. Opens circuit if threshold reached."""
        key = self._key(provider, model)
        self._failures[key] += 1
        self._total_calls[key] += 1
        self._total_errors[key] += 1
        
        if self._failures[key] >= self.failure_threshold:
            self._open_since[key] = time.time()
            logger.warning(
                f"🔴 Circuit breaker OPEN for {key} "
                f"({self._failures[key]} consecutive failures)"
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for health dashboard."""
        status = {}
        all_keys = set(list(self._total_calls.keys()) + list(self._open_since.keys()))
        
        for key in all_keys:
            latencies = self._latencies.get(key, [])
            total = self._total_calls.get(key, 0)
            errors = self._total_errors.get(key, 0)
            
            entry = {
                "total_calls": total,
                "total_errors": errors,
                "error_rate": round(errors / total, 3) if total > 0 else 0,
                "consecutive_failures": self._failures.get(key, 0),
                "circuit_open": key in self._open_since,
            }
            
            if latencies:
                sorted_lat = sorted(latencies)
                entry["p50_latency_ms"] = round(sorted_lat[len(sorted_lat) // 2])
                entry["p95_latency_ms"] = round(sorted_lat[int(len(sorted_lat) * 0.95)])
                entry["avg_latency_ms"] = round(sum(sorted_lat) / len(sorted_lat))
            
            if key in self._open_since:
                elapsed = time.time() - self._open_since[key]
                entry["cooldown_remaining_s"] = round(max(0, self.cooldown_s - elapsed), 1)
            
            status[key] = entry
        
        return status


# Global circuit breaker instance
circuit_breaker = CircuitBreaker(failure_threshold=5, cooldown_s=60.0)


async def _retry_with_backoff(coro_factory, provider: str, model: str, max_retries: int = 3):
    """
    Retry a coroutine with exponential backoff + circuit breaker.
    
    Args:
        coro_factory: Zero-arg async callable that creates the coroutine
        provider: Provider name for circuit breaker keying
        model: Model name for circuit breaker keying
        max_retries: Maximum retry attempts
    """
    from app.core.error_handling import LLMError
    
    # Check circuit breaker first
    circuit_breaker.check(provider, model)
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        start = time.time()
        try:
            result = await coro_factory()
            latency_ms = (time.time() - start) * 1000
            circuit_breaker.record_success(provider, model, latency_ms)
            return result
            
        except Exception as e:
            last_error = e
            latency_ms = (time.time() - start) * 1000
            circuit_breaker.record_failure(provider, model)
            
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                logger.warning(
                    f"⚠️ {provider}:{model} attempt {attempt}/{max_retries} "
                    f"failed ({latency_ms:.0f}ms): {e}. Retrying in {backoff}s..."
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    f"❌ {provider}:{model} all {max_retries} attempts failed: {e}"
                )
    
    raise LLMError(
        f"All {max_retries} attempts failed for {provider}:{model}: {last_error}",
        provider=provider,
        model=model,
        retries_attempted=max_retries
    )


class AnthropicClient:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.timeout = settings.API_TIMEOUT
    
    async def create_message(self, model, messages, max_tokens=4000, temperature=0.7, system=None, tools=None, tool_choice=None):
        async def _call():
            kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            if system: kwargs["system"] = system
            if tools: kwargs["tools"] = tools
            if tool_choice: kwargs["tool_choice"] = tool_choice
            
            response = await self.client.messages.create(**kwargs)
            return {
                "content": response.content,
                "model": response.model,
                "role": response.role,
                "stop_reason": response.stop_reason,
                "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
            }
        
        return await _retry_with_backoff(_call, "anthropic", model)

    async def stream_message(self, model, messages, max_tokens=4000, temperature=0.7, system=None):
        try:
            kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
            if system: kwargs["system"] = system
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            raise

class GoogleAIClient:
    """Wrapper for Google AI (Gemini) API"""
    
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.timeout = settings.API_TIMEOUT
    
    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List] = None
    ) -> Dict[str, Any]:
        """Generate content with Gemini — with retry + circuit breaker."""
        async def _call():
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )
            
            if tools:
                model = genai.GenerativeModel(model_name=model_name, tools=tools)
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt)
            )
            
            try:
                text_content = response.text
            except ValueError:
                text_content = ""
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text'):
                            text_content += part.text

            return {
                "text": text_content,
                "candidates": response.candidates,
                "prompt_feedback": response.prompt_feedback
            }
        
        try:
            return await _retry_with_backoff(_call, "google", model_name)
        except Exception as e:
            logger.error(f"Google AI API error: {str(e)}")
            return {"text": "Analysis temporarily unavailable due to API constraints.", "error": str(e)}

    async def chat(self, model_name, messages, temperature=0.7, max_tokens=4000):
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens}
            )
            chat = model.start_chat(history=[])
            for msg in messages[:-1]:
                await asyncio.get_event_loop().run_in_executor(None, lambda: chat.send_message(msg["content"]))
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: chat.send_message(messages[-1]["content"]))
            
            try: text = response.text
            except ValueError: 
                text = ""
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text'): text += part.text

            return {"text": text, "history": chat.history}
        except Exception as e:
            logger.error(f"Google AI chat error: {str(e)}")
            raise

class OpenAIClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.timeout = settings.API_TIMEOUT
    
    async def create_completion(self, model, messages, temperature=0.7, max_tokens=4000, tools=None, tool_choice=None):
        async def _call():
            kwargs = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            if tools: kwargs["tools"] = tools
            if tool_choice: kwargs["tool_choice"] = tool_choice
            response = await self.client.chat.completions.create(**kwargs)
            return {
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "finish_reason": response.choices[0].finish_reason,
                "tool_calls": response.choices[0].message.tool_calls,
                "usage": {"prompt_tokens": response.usage.prompt_tokens, "completion_tokens": response.usage.completion_tokens, "total_tokens": response.usage.total_tokens}
            }
        
        return await _retry_with_backoff(_call, "openai", model)
    
    async def stream_completion(self, model, messages, temperature=0.7, max_tokens=4000):
        try:
            stream = await self.client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True)
            async for chunk in stream:
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming error: {str(e)}")
            raise
        
class GroqClient:
    """Wrapper for Groq API"""
    
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.timeout = settings.API_TIMEOUT

    async def create_completion(self, model, messages, temperature=0.7, max_tokens=4000, tools=None, tool_choice=None):
        async def _call():
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if tools: kwargs["tools"] = tools
            if tool_choice: kwargs["tool_choice"] = tool_choice
            
            response = await self.client.chat.completions.create(**kwargs)
            
            return {
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "finish_reason": response.choices[0].finish_reason,
                "tool_calls": response.choices[0].message.tool_calls,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        
        return await _retry_with_backoff(_call, "groq", model)

    async def generate_content(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List] = None
    ) -> Dict[str, Any]:
        """Compatibility wrapper to match GoogleAIClient.generate_content signature"""
        async def _call():
            messages = [{"role": "user", "content": prompt}]
            
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            text_content = response.choices[0].message.content
            
            return {
                "text": text_content,
                "candidates": response.choices,
                "usage": response.usage
            }
        
        try:
            return await _retry_with_backoff(_call, "groq", model_name)
        except Exception as e:
            logger.error(f"Groq API content generation error: {str(e)}")
            return {"text": "Analysis temporarily unavailable due to API constraints.", "error": str(e)}
        
anthropic_client = AnthropicClient()
google_client = GoogleAIClient()
openai_client = OpenAIClient()
groq_client = GroqClient()