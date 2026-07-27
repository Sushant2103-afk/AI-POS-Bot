from app.core.config import settings
from app.ai.base import BaseAIService
from app.ai.cache import CachedAIService
from app.ai.providers import (
    MockAIProvider,
    FallbackAIService,
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
    secondary live providers (e.g. Gemini) or MockAIProvider for seamless developer setups.
    All live providers are wrapped in FallbackAIService (to prevent crashes on 401/403/429 errors)
    and CachedAIService (to enable automatic caching).
    """
    provider_name = os.getenv("DEFAULT_AI_PROVIDER", settings.ai.provider).lower()
    base_service = None

    # Determine secondary backup provider if available
    secondary_backup = None
    if provider_name != "gemini" and settings.GEMINI_API_KEY and "mock" not in settings.GEMINI_API_KEY.lower():
        secondary_backup = GeminiProvider(api_key=settings.GEMINI_API_KEY)
    elif provider_name != "groq" and settings.GROQ_API_KEY and "mock" not in settings.GROQ_API_KEY.lower():
        secondary_backup = GroqProvider(api_key=settings.GROQ_API_KEY)
        
    backup_chain = secondary_backup or MockAIProvider()
    
    if provider_name == "groq":
        # Check for empty or local developer mock values
        if not settings.GROQ_API_KEY or "mock" in settings.GROQ_API_KEY.lower():
            base_service = backup_chain
        else:
            base_service = FallbackAIService(
                primary=GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.ai.model),
                backup=backup_chain
            )
        
    elif provider_name == "gemini":
        if not settings.GEMINI_API_KEY or "mock" in settings.GEMINI_API_KEY.lower():
            base_service = backup_chain
        else:
            base_service = FallbackAIService(
                primary=GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.ai.model),
                backup=backup_chain
            )
        
    elif provider_name == "openai":
        if not settings.OPENAI_API_KEY or "mock" in settings.OPENAI_API_KEY.lower():
            base_service = backup_chain
        else:
            base_service = FallbackAIService(
                primary=OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=settings.ai.model),
                backup=backup_chain
            )
        
    elif provider_name == "claude":
        if not settings.CLAUDE_API_KEY or "mock" in settings.CLAUDE_API_KEY.lower():
            base_service = backup_chain
        else:
            base_service = FallbackAIService(
                primary=ClaudeProvider(api_key=settings.CLAUDE_API_KEY, model=settings.ai.model),
                backup=backup_chain
            )
        
    elif provider_name == "ollama":
        base_service = FallbackAIService(
            primary=OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.ai.model),
            backup=backup_chain
        )
        
    if base_service is None:
        base_service = MockAIProvider()
        
    return CachedAIService(base_service)
