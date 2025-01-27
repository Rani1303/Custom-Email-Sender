from dataclasses import dataclass
from typing import Optional
import os
from dotenv import load_dotenv

@dataclass
class Config:
    SERP_API_KEY: str
    GROQ_API_KEY: str
    SHEETS_CREDS_FILE: str
    GMAIL_CREDS_FILE: str 
    GMAIL_TOKEN_FILE: str
    RESEND_API_KEY: str
    REDIS_URL: str
    SENDER_EMAIL: str
    GMAIL_USER: str
    MAX_REQUESTS: int = 100
    EMAIL_RATE_LIMIT: int = 50

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            SERP_API_KEY=os.getenv('SEARCH_API_KEY', ''),
            GROQ_API_KEY=os.getenv('GROQ_API_KEY', ''),
            SHEETS_CREDS_FILE=os.getenv('SHEETS_CREDS_FILE', 'credentials.json'),
            GMAIL_CREDS_FILE=os.getenv('GMAIL_CREDS_FILE', 'gmail_credentials.json'),
            GMAIL_TOKEN_FILE=os.getenv('GMAIL_TOKEN_FILE', 'token.json'),
            RESEND_API_KEY=os.getenv('RESEND_API_KEY', ''), 
            REDIS_URL=os.getenv('REDIS_URL', 'redis://redis:6379/0'),
            SENDER_EMAIL=os.getenv('SENDER_EMAIL', ''),
            GMAIL_USER=os.getenv('GMAIL_USER', ''),
            MAX_REQUESTS=int(os.getenv('MAX_REQUESTS', '100')),
            EMAIL_RATE_LIMIT=int(os.getenv('EMAIL_RATE_LIMIT', '50'))
        )
