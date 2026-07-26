import sqlite3
import hashlib
import json
import os
from typing import Dict, Any, Optional
from app.ai.base import BaseAIService
from app.core.logging import logger

class AICache:
    """
    SQLite-backed key-value store for caching LLM prompts and completions.
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Place cache DB in the configs directory of the workspace
            workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(workspace_dir, "configs", "ai_cache.db")
            
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prompt_cache (
                key TEXT PRIMARY KEY,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    def _hash_key(self, provider: str, model: str, prompt: str, system_instruction: Optional[str]) -> str:
        payload = {
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "system_instruction": system_instruction or ""
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def get(self, provider: str, model: str, prompt: str, system_instruction: Optional[str] = None) -> Optional[str]:
        key = self._hash_key(provider, model, prompt, system_instruction)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT response FROM prompt_cache WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                logger.info(f"Cache HIT for [{provider} : {model}]")
                return row[0]
        except Exception as e:
            logger.warning(f"Failed to read from cache: {e}")
        return None

    def set(self, provider: str, model: str, prompt: str, response: str, system_instruction: Optional[str] = None) -> None:
        key = self._hash_key(provider, model, prompt, system_instruction)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO prompt_cache (key, response) VALUES (?, ?)",
                (key, response)
            )
            conn.commit()
            conn.close()
            logger.debug(f"Cached response for [{provider} : {model}]")
        except Exception as e:
            logger.warning(f"Failed to write to cache: {e}")

ai_cache = AICache()

class CachedAIService(BaseAIService):
    """
    Transparent decorator wrapper that implements BaseAIService and adds caching.
    """
    def __init__(self, service: BaseAIService, cache: AICache = None):
        self.service = service
        self.cache = cache or ai_cache

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        provider = getattr(self.service, "name", self.service.__class__.__name__)
        model = getattr(self.service, "model", "default")
        
        cached = self.cache.get(provider, model, prompt, system_instruction)
        if cached is not None:
            return cached
            
        res = self.service.generate_text(prompt, system_instruction, temperature)
        self.cache.set(provider, model, prompt, res, system_instruction)
        return res

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        provider = getattr(self.service, "name", self.service.__class__.__name__)
        model = getattr(self.service, "model", "default")
        
        schema_str = json.dumps(response_schema, sort_keys=True) if response_schema else ""
        prompt_with_schema = f"{prompt}\nSchema: {schema_str}"
        
        cached = self.cache.get(provider, model, prompt_with_schema, system_instruction)
        if cached is not None:
            try:
                return json.loads(cached)
            except Exception:
                pass
            
        res = self.service.generate_json(prompt, response_schema, system_instruction, temperature)
        self.cache.set(provider, model, prompt_with_schema, json.dumps(res), system_instruction)
        return res
