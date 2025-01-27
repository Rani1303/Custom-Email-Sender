import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from config import Config

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
config = Config.from_env()

class DataHandler:
    SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def __init__(self, config: Config):
        self.config = config
        self.sheets_credentials = None
        self.sheets_service = None

    def validate_google_sheet_url(self, sheet_url: str) -> bool:
        return 'docs.google.com/spreadsheets/d/' in sheet_url

    def extract_sheet_id(self, sheet_url: str) -> str:
        return sheet_url.split("/d/")[1].split("/")[0]

    def get_sheets_service(self):
        try:
            sheets_creds_file = self.config.SHEETS_CREDS_FILE

            if not os.path.exists(sheets_creds_file):
                raise FileNotFoundError(f"Sheets credentials file not found: {sheets_creds_file}")

            self.sheets_credentials = service_account.Credentials.from_service_account_file(
                sheets_creds_file,
                scopes=self.SHEETS_SCOPES
            )
            self.sheets_service = build('sheets', 'v4', credentials=self.sheets_credentials)
            return self.sheets_service

        except Exception as e:
            logging.error(f"Error initializing Google Sheets service: {e}")
            raise

    def connect_google_sheet(self, sheet_url: str) -> pd.DataFrame:
        try:
            if not self.validate_google_sheet_url(sheet_url):
                raise ValueError("Invalid Google Sheets URL. Please provide a valid URL.")

            sheet_id = self.extract_sheet_id(sheet_url)
            service = self.get_sheets_service()

            sheet_metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheet_name = sheet_metadata.get('sheets', [{}])[0].get('properties', {}).get('title', 'Sheet1')

            range_name = f"{sheet_name}!A1:ZZ10000"
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            if not values:
                raise ValueError("No data found in sheet.")

            df = pd.DataFrame(values[1:], columns=values[0])
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            return df.dropna(how='all').dropna(axis=1, how='all')

        except HttpError as e:
            logging.error(f"Google Sheets API error: {e}")
            st.error(f"Google Sheets API error: {str(e)}")
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error connecting to Google Sheet: {e}")
            st.error(f"Error connecting to Google Sheet: {str(e)}")
            return pd.DataFrame()

    def read_csv(self, file) -> pd.DataFrame:
        try:
            return pd.read_csv(file)
        except Exception as e:
            logging.error(f"Error reading CSV file: {e}")
            st.error(f"Error reading CSV file: {str(e)}")
            return pd.DataFrame()

    def validate_sheets_credentials(self) -> bool:
        try:
            sheets_creds_file = self.config.SHEETS_CREDS_FILE
            if not os.path.exists(sheets_creds_file):
                raise FileNotFoundError(f"Sheets credentials file not found: {sheets_creds_file}")

            credentials = service_account.Credentials.from_service_account_file(
                sheets_creds_file,
                scopes=self.SHEETS_SCOPES
            )

            return credentials.valid
        except Exception as e:
            logging.error(f"Error validating Sheets credentials: {e}")
            return False

    def check_sheets_access(self) -> bool:
        try:
            if not self.validate_sheets_credentials():
                raise ValueError("Invalid or missing Google Sheets credentials.")

            self.get_sheets_service()
            return True

        except Exception as e:
            logging.error(f"Error checking Sheets access: {e}")
            st.error(f"Error checking Sheets access: {str(e)}")
            return False
