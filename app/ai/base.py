from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAIService(ABC):
    """
    Abstract Base Class for all AI API Provider Services.
    Enforces consistent text generation and structured JSON extraction signatures.
    """
    
    @abstractmethod
    def generate_text(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        temperature: float = 0.2
    ) -> str:
        """
        Generate raw text response from the LLM provider.
        """
        pass

    @abstractmethod
    def generate_json(
        self, 
        prompt: str, 
        response_schema: Optional[Dict[str, Any]] = None, 
        system_instruction: Optional[str] = None, 
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Request the LLM to output a structured JSON object matching the provided schema.
        """
        pass
