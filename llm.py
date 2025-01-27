from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from config import Config
load_dotenv()


class LLMProcessor:
    def __init__(self, config: Config):
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required in the configuration")
        self.client = Groq(api_key=config.GROQ_API_KEY)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_email(self, prompt: str, placeholders: list, temperature: float = 0.7) -> Optional[str]:
        try:
            placeholder_str = ", ".join([f"{{{{{placeholder}}}}}" for placeholder in placeholders])
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert email writer. Create professional emails that incorporate specified placeholder variables."
                },
                {
                    "role": "user",
                    "content": f"""
                    Generate a professional email based on this prompt:
                    {prompt}
                    
                    Include these placeholders: {placeholder_str}
                    Format placeholders exactly as provided (e.g., {{name}} for name).
                    """
                }
            ]

            chat_completion = self.client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=temperature,
                max_tokens=2000
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            logging.error(f"Email generation failed: {e}")
            return None

            
    def process_content(self, email_content: str, context: Dict[str, Any]) -> str:
        try:
            content_with_placeholders = email_content
            for key, value in context['variables'].items():
                content_with_placeholders = content_with_placeholders.replace(f"{{{{{key}}}}}", str(value))
            return content_with_placeholders
        except Exception as e:
            logging.error(f"Content processing failed: {e}")
            return email_content


