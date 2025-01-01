import requests
from typing import Dict, Any
import logging
import streamlit as st
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

# Initialize configuration
config = Config.from_env()

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

    def process_content(self, content: str, context: Dict[str, Any]) -> str:
        """Process email content with LLM."""
        try:
            st.write("Processing content with LLM...")
            
            # Create the prompt
            prompt = f"""
            Please enhance this email content while maintaining all personalization variables.
            Make it more engaging and professional while keeping the same intent.

            Original Content:
            {content}

            Context:
            - Recipient Email: {context['recipient']}
            - Variables Available: {context['variables']}

            Please return only the enhanced content, maintaining any HTML formatting if present.
            """

            # Make API call
            response = requests.post(
                self.url,
                headers=self.headers,
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": [
                        {"role": "system", "content": "You are a professional email content enhancer. Maintain all personalization variables and HTML formatting while improving the content."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=30
            )
            
            if response.status_code == 429:
                st.warning("Rate limit exceeded. Using original content.")
                return content
                
            response.raise_for_status()
            enhanced_content = response.json()['choices'][0]['message']['content']
            
            st.success("Content processed successfully!")
            return enhanced_content
            
        except Exception as e:
            st.error(f"Error processing content with LLM: {str(e)}")
            logging.error(f"LLM processing error: {str(e)}")
            # Return original content if processing fails
            return content

    def test_connection(self) -> bool:
        """Test the LLM API connection."""
        try:
            response = requests.post(
                self.url,
                headers=self.headers,
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": [
                        {"role": "user", "content": "Test connection"}
                    ],
                    "max_tokens": 10
                }
            )
            return response.status_code == 200
        except Exception:
            return False

