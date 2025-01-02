import requests
from typing import Dict, Any, Optional
import logging
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMProcessor:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GROQ API key is required")
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_api_call(self, messages: list, temperature: float = 0.7) -> Optional[str]:
        try:
            response = requests.post(
                self.url,
                headers=self.headers,
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 2000
                },
                timeout=30
            )
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded")
                
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
            
        except requests.exceptions.Timeout:
            raise Exception("API request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    def process_content(self, content: str, context: Dict[str, Any]) -> str:
        try:
            prompt = [
                {
                    "role": "system",
                    "content": "You are a professional email content enhancer. Maintain all personalization variables and HTML formatting while improving the content."
                },
                {
                    "role": "user",
                    "content": f"""
                    Enhance this email while keeping all personalization variables:
                    {content}
                    
                    Context:
                    Recipient: {context['recipient']}
                    Variables: {context['variables']}
                    """
                }
            ]

            enhanced_content = self._make_api_call(prompt)
            return enhanced_content if enhanced_content else content

        except Exception as e:
            logging.error(f"Content processing error: {str(e)}")
            return content

    def test_connection(self) -> bool:
        try:
            test_message = [{"role": "user", "content": "Test connection"}]
            return bool(self._make_api_call(test_message, temperature=0.1))
        except Exception:
            return False