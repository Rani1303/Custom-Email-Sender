import base64
from email.mime.text import MIMEText
import redis
import logging
import os
import time
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from resend import Resend
from config import Config  # Import the Config class from config.py

load_dotenv()

# Initialize configuration
config = Config.from_env()

class EmailHandler:
    def __init__(self, config):
        """Initialize EmailHandler with configuration."""
        self.config = config
        self.redis_client = None
        self.gmail_creds = None
        self.smtp_settings = None
        self.resend_client = None

        if self._initialize_redis():
            self._setup_gmail_oauth()
            self._initialize_smtp()
            self._initialize_resend()

    def _initialize_redis(self) -> bool:
        """Initialize Redis connection with retry logic."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                redis_url = os.getenv('REDIS_URL', self.config.REDIS_URL)

                if 'redis://redis:' in redis_url and attempt == 0:
                    redis_url = redis_url.replace('redis://redis:', 'redis://localhost:')

                self.redis_client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    retry_on_timeout=True
                )

                self.redis_client.ping()
                logging.info("Successfully connected to Redis")
                return True

            except redis.ConnectionError as e:
                logging.warning(f"Redis connection attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error("Failed to connect to Redis after maximum retries.")
                    return False
                time.sleep(retry_delay)
            except Exception as e:
                logging.error(f"Redis initialization error: {str(e)}")
                return False

        return False

    def _initialize_resend(self):
        """Initialize Resend client."""
        resend_api_key = os.getenv('RESEND_API_KEY', self.config.RESEND_API_KEY)
        if not resend_api_key:
            logging.warning("Resend API key is not set. Emails will not be sent via Resend.")
            return

        self.resend_client = Resend(api_key=resend_api_key)

    def _setup_gmail_oauth(self):
        """Set up Gmail OAuth credentials."""
        creds_path = os.getenv('GMAIL_CREDS_FILE', self.config.GMAIL_CREDS_FILE)
        token_path = os.path.join(os.path.dirname(creds_path), 'token.json')
        scopes = ['https://www.googleapis.com/auth/gmail.send']

        try:
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, scopes)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
                creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            self.gmail_creds = creds
        except Exception as e:
            logging.error(f"Error setting up Gmail OAuth: {str(e)}")

    def _initialize_smtp(self):
        """Initialize SMTP settings."""
        self.smtp_settings = {
            'host': os.getenv('SMTP_HOST'),
            'port': os.getenv('SMTP_PORT'),
            'user': os.getenv('SMTP_USER'),
            'password': os.getenv('SMTP_PASSWORD'),
        }

    def send_email(self, to_email: str, subject: str, content: str) -> bool:
        """Send an email using the configured provider."""
        try:
            if self.resend_client:
                return self._send_via_resend(to_email, subject, content)
            elif self.gmail_creds:
                return self._send_via_gmail(to_email, subject, content)
            elif self.smtp_settings:
                return self._send_via_smtp(to_email, subject, content)
            else:
                logging.warning("No email provider configured.")
                return False

        except Exception as e:
            logging.error(f"Error sending email: {str(e)}")
            return False

    def _send_via_resend(self, to_email: str, subject: str, content: str) -> bool:
        """Send email using Resend."""
        try:
            self.resend_client.emails.send(
                from_email=self.config.SENDER_EMAIL,
                to=[to_email],
                subject=subject,
                html=content
            )
            logging.info(f"Email sent to {to_email} via Resend.")
            return True
        except Exception as e:
            logging.error(f"Error sending email via Resend: {str(e)}")
            return False

    def _send_via_gmail(self, to_email: str, subject: str, content: str) -> bool:
        """Send email using Gmail API."""
        try:
            service = build('gmail', 'v1', credentials=self.gmail_creds)
            message = MIMEText(content, 'html')
            message['to'] = to_email
            message['from'] = self.config.SENDER_EMAIL
            message['subject'] = subject

            service.users().messages().send(userId='me', body={'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}).execute()
            logging.info(f"Email sent to {to_email} via Gmail.")
            return True
        except Exception as e:
            logging.error(f"Error sending email via Gmail: {str(e)}")
            return False

    def _send_via_smtp(self, to_email: str, subject: str, content: str) -> bool:
        """Send email using SMTP."""
        try:
            with smtplib.SMTP(self.smtp_settings['host'], self.smtp_settings['port']) as server:
                server.starttls()
                server.login(self.smtp_settings['user'], self.smtp_settings['password'])

                message = MIMEMultipart()
                message['From'] = self.smtp_settings['user']
                message['To'] = to_email
                message['Subject'] = subject
                message.attach(MIMEText(content, 'html'))

                server.send_message(message)

            logging.info(f"Email sent to {to_email} via SMTP.")
            return True
        except Exception as e:
            logging.error(f"Error sending email via SMTP: {str(e)}")
            return False

    def create_email_batches(self, recipients: List[str], batch_size: int) -> List[List[str]]:
        """Divide recipients into batches of specified size."""
        return [recipients[i:i + batch_size] for i in range(0, len(recipients), batch_size)]

    def schedule_email_batches(self, batches: List[List[str]], subject: str, content: str):
        """Schedule email batches with delay between batches."""
        delay_between_batches = self.config.EMAIL_RATE_LIMIT

        for batch in batches:
            for recipient in batch:
                self.redis_client.rpush('email_queue', json.dumps({'to': recipient, 'subject': subject, 'content': content}))
            time.sleep(delay_between_batches)

    def process_email_queue(self):
        """Process the queued emails from Redis."""
        while True:
            email_data = self.redis_client.lpop('email_queue')
            if email_data:
                email_info = json.loads(email_data)
                self.send_email(email_info['to'], email_info['subject'], email_info['content'])
            else:
                logging.info("No emails in queue. Sleeping...")
                time.sleep(5)

    def track_email_status(self, email_id: str, status: str):
        """Track the status of emails in Redis."""
        self.redis_client.hset('email_status', email_id, status)

    def get_email_status(self, email_id: str) -> Optional[str]:
        """Retrieve the status of an email by ID."""
        return self.redis_client.hget('email_status', email_id)

    def get_email_analytics(self) -> Dict[str, int]:
        """Retrieve email analytics from Redis."""
        statuses = self.redis_client.hgetall('email_status')
        analytics = {'sent': 0, 'failed': 0, 'pending': 0}

        for status in statuses.values():
            if status in analytics:
                analytics[status] += 1

        return analytics
