from app.core.config import settings
from app.ai.base import BaseAIService
from app.ai.cache import CachedAIService
from app.ai.providers import (
    MockAIProvider,
    GroqProvider,
    GeminiProvider,
    OpenAIProvider,
    ClaudeProvider,
    OllamaProvider
)

import os

def get_ai_service() -> BaseAIService:
    """
    Factory function to retrieve the configured AI provider client.
    Detects if API keys are mock values, and automatically falls back to 
    MockAIProvider for seamless developer setups.
    All clients are wrapped in CachedAIService to enable automatic caching.
    """
    provider_name = os.getenv("DEFAULT_AI_PROVIDER", settings.ai.provider).lower()
    base_service = None
    
    if provider_name == "groq":
        # Check for empty or local developer mock values
        if not settings.GROQ_API_KEY or "mock" in settings.GROQ_API_KEY.lower():
            base_service = MockAIProvider()
        else:
            base_service = GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.ai.model)
        
    elif provider_name == "gemini":
        if not settings.GEMINI_API_KEY or "mock" in settings.GEMINI_API_KEY.lower():
            base_service = MockAIProvider()
        else:
            base_service = GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.ai.model)
        
    elif provider_name == "openai":
        if not settings.OPENAI_API_KEY or "mock" in settings.OPENAI_API_KEY.lower():
            base_service = MockAIProvider()
        else:
            base_service = OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=settings.ai.model)
        
    elif provider_name == "claude":
        if not settings.CLAUDE_API_KEY or "mock" in settings.CLAUDE_API_KEY.lower():
            base_service = MockAIProvider()
        else:
            base_service = ClaudeProvider(api_key=settings.CLAUDE_API_KEY, model=settings.ai.model)
        
    elif provider_name == "ollama":
        base_service = OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.ai.model)
        
    if base_service is None:
        base_service = MockAIProvider()
        
    return CachedAIService(base_service)
