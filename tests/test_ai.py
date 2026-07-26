from app.ai.service import get_ai_service
from app.ai.cache import AICache, CachedAIService
from app.ai.providers import MockAIProvider

def test_ai_provider_resolution():
    """
    Test that global factory returns a CachedAIService wrapping MockAIProvider by default.
    """
    service = get_ai_service()
    assert isinstance(service, CachedAIService)
    assert isinstance(service.service, MockAIProvider)

def test_prompt_caching(mocker, tmp_path):
    """
    Test that identical prompt calls hit the local cache instead of making repeated LLM calls.
    """
    test_db = tmp_path / "test_cache.db"
    cache = AICache(db_path=str(test_db))
    
    base_provider = MockAIProvider()
    cached_service = CachedAIService(base_provider, cache=cache)
    
    spy = mocker.spy(base_provider, "generate_text")
    
    prompt = "Compute high complexity algorithm steps."
    
    # Call 1: Should be cache miss, call MockAIProvider
    res1 = cached_service.generate_text(prompt)
    assert spy.call_count == 1
    assert "Mock response text" in res1
    
    # Call 2: Should be cache hit, bypass MockAIProvider
    res2 = cached_service.generate_text(prompt)
    assert spy.call_count == 1
    assert res2 == res1
