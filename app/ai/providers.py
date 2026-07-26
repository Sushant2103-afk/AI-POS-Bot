import json
import httpx
from typing import Dict, Any, Optional
from app.ai.base import BaseAIService
from app.core.logging import logger

class MockAIProvider(BaseAIService):
    """
    Mock AI Service for offline development and local test suites.
    Returns valid structures for roadmap parsing.
    """
    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        logger.info("[Mock AI] Generating text mock response.")
        return "Mock response text generated successfully by MockAIProvider."

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        logger.info("[Mock AI] Generating JSON mock response.")
        
        # Detect if this is a roadmap import prompt
        if "roadmap" in prompt.lower() or "syllabus" in prompt.lower() or "topic" in prompt.lower():
            return {
                "title": "Mock SDE Prep Roadmap",
                "description": "Seeded via Mock AI parsing engine",
                "months": [
                    {
                        "month_number": 1,
                        "title": "Dynamic Programming & Array Foundations",
                        "target_hours": 60.0,
                        "weeks": [
                            {
                                "week_number": 1,
                                "title": "1D Dynamic Programming & Arrays",
                                "target_hours": 15.0,
                                "topics": [
                                    {
                                        "title": "Climbing Stairs & Array Dictionaries",
                                        "description": "Introduction to memoization and list iterations.",
                                        "priority": "high",
                                        "estimated_hours": 8.0,
                                        "energy_level": "high",
                                        "tasks": [
                                            {
                                                "title": "Solve LeetCode 70 (Climbing Stairs)",
                                                "description": "Optimize recursive relation using a memo table.",
                                                "estimated_minutes": 30,
                                                "priority": "high",
                                                "energy_level": "high"
                                            },
                                            {
                                                "title": "Solve LeetCode 1 (Two Sum)",
                                                "description": "Single-pass hash map resolution.",
                                                "estimated_minutes": 20,
                                                "priority": "medium",
                                                "energy_level": "low"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        
        return {"status": "success", "message": "Mock JSON generated successfully."}

def _clean_json_string(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

class GroqProvider(BaseAIService):
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.error(f"Groq API Error Response ({response.status_code}): {response.text}")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Groq API Call failed: {e}")
            raise e

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        res = self._call_api(payload)
        return res["choices"][0]["message"]["content"]

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        messages = []
        sys_inst = system_instruction or ""
        sys_inst += "\nIMPORTANT: You must output a valid JSON block that conforms exactly to the required structure. Do not output conversational formatting."
        
        messages.append({"role": "system", "content": sys_inst.strip()})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        res = self._call_api(payload)
        content = res["choices"][0]["message"]["content"]
        return json.loads(_clean_json_string(content))

class GeminiProvider(BaseAIService):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model
        self.endpoint_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(self.endpoint_url, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini generateContent call failed: {e}")
            raise e

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json"
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(self.endpoint_url, json=payload)
                res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except Exception as e:
            logger.error(f"Gemini generate_json call failed: {e}")
            raise e

class OpenAIProvider(BaseAIService):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise e

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        res = self._call_api(payload)
        return res["choices"][0]["message"]["content"]

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        messages = []
        sys_inst = system_instruction or ""
        sys_inst += "\nOutput must be valid JSON."
        messages.append({"role": "system", "content": sys_inst})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        res = self._call_api(payload)
        content = res["choices"][0]["message"]["content"]
        return json.loads(content)

class ClaudeProvider(BaseAIService):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        if system_instruction:
            payload["system"] = system_instruction

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(self.endpoint, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                return data["content"][0]["text"]
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise e

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        sys_inst = system_instruction or ""
        sys_inst += "\nReturn only valid JSON, without any markdown code block wrappers."
        
        text = self.generate_text(prompt, system_instruction=sys_inst, temperature=temperature)
        try:
            # Strip potential Markdown wrappers if Claude outputs them
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.error(f"Claude JSON parsing failed for response: {text}. Error: {e}")
            raise e

class OllamaProvider(BaseAIService):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model
        self.endpoint = f"{base_url}/api/chat"

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": False
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(self.endpoint, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama local API call failed: {e}")
            raise e

    def generate_json(self, prompt: str, response_schema: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature},
            "format": "json",
            "stream": False
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(self.endpoint, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data["message"]["content"]
                return json.loads(content)
        except Exception as e:
            logger.error(f"Ollama local JSON call failed: {e}")
            raise e
