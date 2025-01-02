from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import streamlit as st
from pathlib import Path
import os
import pickle
from dotenv import load_dotenv
from config import Config

# Load environment variables and config
load_dotenv()
config = Config.from_env()

class DataHandler:
    SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    
    def __init__(self, config: Config):
        self.config = config
        self.sheets_credentials = None
        self.sheets_service = None

    def connect_google_sheet(self, sheet_url: str) -> pd.DataFrame:
        """Connect to Google Sheets with proper error handling and authentication."""
        try:
            sheets_creds_file = self.config.SHEETS_CREDS_FILE
            
            if not os.path.exists(sheets_creds_file):
                st.error(f"Sheets credentials file not found: {sheets_creds_file}")
                return pd.DataFrame()

            try:
                self.sheets_credentials = service_account.Credentials.from_service_account_file(
                    sheets_creds_file,
                    scopes=self.SHEETS_SCOPES
                )
            except Exception as e:
                st.error(f"Error loading sheets credentials: {str(e)}")
                return pd.DataFrame()

            try:
                self.sheets_service = build('sheets', 'v4', credentials=self.sheets_credentials)
            except Exception as e:
                st.error(f"Error building sheets service: {str(e)}")
                return pd.DataFrame()

            if '/d/' not in sheet_url:
                st.error("Invalid Google Sheets URL. Please use the full URL from your browser.")
                return pd.DataFrame()

            sheet_id = sheet_url.split("/d/")[1].split("/")[0]

            try:
                sheet_metadata = self.sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
                sheets = sheet_metadata.get('sheets', '')

                if not sheets:
                    st.error("No sheets found in the specified document")
                    return pd.DataFrame()
                
                sheet_name = sheets[0]['properties']['title']

                range_name = f"{sheet_name}!A1:ZZ10000"
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=range_name
                ).execute()

                values = result.get("values", [])
                if not values:
                    st.error("No data found in sheet")
                    return pd.DataFrame()

                df = pd.DataFrame(values[1:], columns=values[0])

                df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

                df = df.dropna(how='all').dropna(axis=1, how='all')

                return df

            except HttpError as e:
                st.error(f"Google Sheets API error: {str(e)}")
                return pd.DataFrame()

        except Exception as e:
            st.error(f"Error connecting to Google Sheet: {str(e)}")
            return pd.DataFrame()

    def read_csv(self, file) -> pd.DataFrame:
        """Read CSV file with error handling."""
        try:
            df = pd.read_csv(file)
            return df
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")
            return pd.DataFrame()

    def validate_sheets_credentials(self) -> bool:
        """Validate Google Sheets credentials file."""
        try:
            sheets_creds_file = self.config.SHEETS_CREDS_FILE
            if not os.path.exists(sheets_creds_file):
                return False

            sheets_credentials = service_account.Credentials.from_service_account_file(
                sheets_creds_file,
                scopes=self.SHEETS_SCOPES
            )
            
            return sheets_credentials.valid

        except Exception:
            return False

    def check_sheets_access(self) -> bool:
        """Check if we have valid access to Google Sheets API."""
        try:
            if not self.validate_sheets_credentials():
                st.error("Invalid or missing Google Sheets credentials")
                return False

            credentials = service_account.Credentials.from_service_account_file(
                self.config.SHEETS_CREDS_FILE,
                scopes=self.SHEETS_SCOPES
            )
            service = build('sheets', 'v4', credentials=credentials)
            
            return True

        except Exception as e:
            st.error(f"Error checking Google Sheets access: {str(e)}")
            return False
