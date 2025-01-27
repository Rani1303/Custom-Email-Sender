import base64
import json
import logging
import os
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional
import smtplib
import pandas as pd
import redis
import requests
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from config import Config
load_dotenv()

class EmailHandler:
    def __init__(self, config: Config):
        self.config = config
        self.smtp_settings = {
            'host': 'smtp.gmail.com',
            'port': 587,
            'user': config.GMAIL_USER,
        }

        if self._initialize_redis():
            self._setup_gmail_oauth()

    def _initialize_redis(self) -> bool:
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                redis_url = os.getenv('REDIS_URL', self.config.REDIS_URL)
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
                    st.error(f"Failed to connect to Redis after {max_retries} attempts.")
                    return False
                time.sleep(retry_delay)

            except Exception as e:
                logging.error(f"Unexpected Redis error: {str(e)}")
                return False

        return False

    def _send_via_resend(self, to_email: str, subject: str, content: str) -> bool:
        try:
            if not self.config.RESEND_API_KEY:
                raise Exception("Resend API key not configured")

            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {self.config.RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": self.config.SENDER_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": content
            }

            response = requests.post(url, headers=headers, json=payload)
            if response.status_code not in [200, 202]:
                logging.error(f"Resend API error: {response.status_code} - {response.text}")
                return False

            logging.info("Email sent successfully via Resend")
            return True

        except Exception as e:
            logging.error(f"Resend sending error: {str(e)}")
            return False

    def send_email(self, to_email: str, subject: str, content: str, batch_id: str = None) -> bool:
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not hasattr(self, 'gmail_creds') or not self.gmail_creds:
                    logging.error("Gmail credentials not initialized")
                    raise Exception("Gmail not authenticated. Please complete OAuth setup.")

                if not self.gmail_creds.valid:
                    if self.gmail_creds.expired and self.gmail_creds.refresh_token:
                        self.gmail_creds.refresh(Request())
                    else:
                        raise Exception("Invalid Gmail credentials. Please re-authenticate.")

                service = build('gmail', 'v1', credentials=self.gmail_creds)
                message = MIMEMultipart()
                message['to'] = to_email
                message['from'] = self.config.GMAIL_USER
                message['subject'] = subject
                message.attach(MIMEText(content, 'html'))

                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                sent_message = service.users().messages().send(
                    userId='me',
                    body={'raw': raw_message}
                ).execute()

                if batch_id:
                    metadata = {
                        'email': to_email,
                        'status': 'sent',
                        'timestamp': datetime.now().isoformat(),
                        'message_id': sent_message.get('id')
                    }
                    self.store_in_redis(f"{batch_id}:{to_email}", json.dumps(metadata))

                logging.info(f"Email sent successfully to {to_email}")
                return True

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    error_msg = f"Failed to send email to {to_email} after {max_retries} attempts: {str(e)}"
                    logging.error(error_msg)
                    if batch_id:
                        metadata = {
                            'email': to_email,
                            'status': 'failed',
                            'error': str(e),
                            'timestamp': datetime.now().isoformat()
                        }
                        self.store_in_redis(f"{batch_id}:{to_email}", json.dumps(metadata))
                    return False

    def _simulate_email_send(self, to_email: str, subject: str, content: str) -> bool:
        logging.info(f"Simulating email send to {to_email} with subject '{subject}'.")
        return True

    def _setup_gmail_oauth(self):
        try:
            self.GMAIL_SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
                # "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.send"
                # "https://www.googleapis.com/auth/gmail.compose"
            ]
            self.credentials_path = self.config.GMAIL_CREDS_FILE
            self.token_path = self.config.GMAIL_TOKEN_FILE

            self.gmail_creds = None
            if os.path.exists(self.token_path):
                self.gmail_creds = Credentials.from_authorized_user_file(self.token_path, self.GMAIL_SCOPES)

            if not self.gmail_creds or not self.gmail_creds.valid:
                if self.gmail_creds and self.gmail_creds.expired and self.gmail_creds.refresh_token:
                    self.gmail_creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.GMAIL_SCOPES
                    )
                    self.gmail_creds = flow.run_local_server(port=0)

                with open(self.token_path, 'w') as token:
                    token.write(self.gmail_creds.to_json())

        except Exception as e:
            if 'error' in str(e).lower() and 'invalid_scope' in str(e).lower():
                logging.error(f"Requested scopes: {self.GMAIL_SCOPES}. Verify these scopes in your Google Cloud project.")
            logging.error(f"Gmail OAuth setup error: {str(e)}")



    def _send_via_gmail(self, to_email: str, subject: str, content: str) -> bool:
        try:
            if not self.gmail_creds:
                raise Exception("Gmail not authenticated. Please complete OAuth setup.")

            service = build('gmail', 'v1', credentials=self.gmail_creds)
            message = MIMEMultipart()
            message['to'] = to_email
            message['subject'] = subject
            message.attach(MIMEText(content, 'html'))

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            logging.info("Email sent successfully via Gmail")
            return True

        except Exception as e:
            logging.error(f"Gmail sending error: {str(e)}")
            return False


    def store_in_redis(self, key: str, value: str) -> bool:
        try:
            self.redis_client.set(key, value)
            logging.info(f"Stored {key} in Redis")
            return True
        except Exception as e:
            logging.error(f"Redis storage error: {str(e)}")
            return False