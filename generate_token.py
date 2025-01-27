from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import logging
logging.basicConfig(level=logging.DEBUG)


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    # "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send"
    # "https://www.googleapis.com/auth/gmail.compose"
]

GMAIL_CREDS_FILE = 'gmail_credentials.json'
GMAIL_TOKEN_FILE = 'token.json'            

def generate_gmail_token():
    creds = None
    if os.path.exists(GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDS_FILE,
                SCOPES
            )
            creds = flow.run_local_server(port=8080, state=None)
        with open(GMAIL_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            print(f"Token saved to {GMAIL_TOKEN_FILE}")
        
    else:
        flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(GMAIL_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logging.info(f"Token saved to {GMAIL_TOKEN_FILE}")

    return creds


if __name__ == "__main__":
    try:
        creds = generate_gmail_token()
        if creds:
            logging.info("Gmail token generated successfully!")
        else:
            logging.error("Failed to generate Gmail token.")
    except Exception as e:
        logging.error(f"Error during Gmail token generation: {str(e)}")
