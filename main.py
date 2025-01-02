import logging
import streamlit as st
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import redis
import seaborn as sns
import io
import matplotlib.pyplot as plt
from config import Config
from data_handlers import DataHandler
from search_engine import SearchEngine
from llm import LLMProcessor
from email_handler import EmailHandler
from sendgrid.helpers.mail import (
    Mail, 
    Email, 
    To, 
    Content
)

class AnalyticsDashboard:
    @staticmethod
    def create_status_visualization(df_status: pd.DataFrame):
        """Create status distribution visualization using Seaborn."""
        sns.set_style("whitegrid")
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Bar plot
        sns.barplot(
            data=df_status,
            x='Status',
            y='Count',
            palette='husl',
            ax=ax1
        )
        ax1.set_title('Email Status Distribution')
        ax1.set_xlabel('Status')
        ax1.set_ylabel('Number of Emails')
        ax1.tick_params(axis='x', rotation=45)
        
        # Pie chart
        ax2.pie(
            df_status['Count'],
            labels=df_status['Status'],
            autopct='%1.1f%%'
        )
        ax2.set_title('Status Distribution (%)')
        
        plt.tight_layout()
        return fig

    @staticmethod
    def create_timeline_visualization(detailed_df: pd.DataFrame):
        """Create timeline visualization for email sending pattern."""
        for col in ['Scheduled Time', 'Sent Time']:
            detailed_df[col] = pd.to_datetime(detailed_df[col], errors='coerce')
        
        sent_times = detailed_df['Sent Time'].dropna()
        if not sent_times.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.histplot(
                data=sent_times.dt.hour,
                bins=24,
                ax=ax,
                color='skyblue'
            )
            ax.set_title('Email Sending Pattern by Hour')
            ax.set_xlabel('Hour of Day')
            ax.set_ylabel('Number of Emails')
            plt.tight_layout()
            return fig
        return None

    @staticmethod
    def create_status_heatmap(detailed_df: pd.DataFrame):
        """Create heatmap for status transitions."""
        if 'Status' in detailed_df.columns and 'Delivery Status' in detailed_df.columns:
            status_matrix = pd.crosstab(
                detailed_df['Status'],
                detailed_df['Delivery Status']
            )
            
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.heatmap(
                status_matrix,
                annot=True,
                fmt='d',
                cmap='YlOrRd',
                ax=ax
            )
            ax.set_title('Status Transition Heatmap')
            plt.tight_layout()
            return fig
        return None

class AIAgentDashboard:
    def __init__(self):
        st.set_page_config(
            page_title="AI Email Campaign Dashboard",
            page_icon="✉️",
            layout="wide"
        )
        self.config = Config.from_env()
        self.search_engine = SearchEngine(self.config.SERP_API_KEY)
        self.llm_processor = LLMProcessor(self.config.GROQ_API_KEY)
        self.data_handler = DataHandler(self.config)
        self.email_handler = EmailHandler(self.config)
        
        # Only initialize Redis client if email handler connected successfully
        if self.email_handler.redis_client:
            self.redis_client = self.email_handler.redis_client
        else:
            st.error("Failed to initialize Redis connection. Some features may not work.")
            self.redis_client = None
            
        self.analytics = AnalyticsDashboard()

    def _setup_sidebar(self):
        """Setup sidebar configuration."""
        with st.sidebar:
            st.subheader("Configuration")
            
            # Data Source Selection
            self.data_source = st.radio(
                "Choose Data Source",
                ["Upload CSV", "Google Sheets"]
            )
            
            # Email Provider Setup
            st.subheader("Email Setup")
            self.email_provider = st.selectbox(
                "Email Provider",
                ["SendGrid", "SMTP", "Gmail"]
            )
            
            if self.email_provider == "SMTP":
                self._setup_smtp_config()
            elif self.email_provider == "Gmail":
                self._setup_gmail_config()
            
            # Rate Limiting
            st.subheader("Rate Limiting")
            self.rate_limit = st.number_input(
                "Emails per Hour",
                min_value=1,
                max_value=1000,
                value=self.config.EMAIL_RATE_LIMIT
            )

    def _setup_smtp_config(self):
        """Configure SMTP settings."""
        smtp_server = st.text_input("SMTP Server")
        smtp_port = st.number_input("Port", value=587)
        smtp_user = st.text_input("Username")
        smtp_password = st.text_input("Password", type="password")
        
        if st.button("Test SMTP Connection"):
            try:
                success = self.email_handler.test_smtp_connection({
                    'server': smtp_server,
                    'port': smtp_port,
                    'username': smtp_user,
                    'password': smtp_password
                })
                if success:
                    st.success("SMTP connection successful!")
                else:
                    st.error("SMTP connection failed!")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")

    def _setup_gmail_config(self):
        """Configure Gmail OAuth."""
        try:
            if 'gmail_authenticated' not in st.session_state:
                st.session_state.gmail_authenticated = False
                
            if st.session_state.gmail_authenticated:
                st.success("Gmail already authenticated!")
                return
                
            if st.button("Connect Gmail Account"):
                auth_url = self.email_handler.get_gmail_auth_url()
                st.markdown("""
                    1. Click the link below to authorize Gmail
                    2. After authorizing, copy the code from the redirect URL
                    3. Paste the code below
                """)
                st.markdown(f"[Click here to authorize Gmail]({auth_url})")
                
                auth_code = st.text_input("Enter the authorization code:")
                if auth_code:
                    if self.email_handler.handle_gmail_callback(auth_code):
                        st.success("Gmail authentication successful!")
                        st.session_state.gmail_authenticated = True
                    else:
                        st.error("Gmail authentication failed. Please try again.")
                        
        except Exception as e:
            st.error(f"Gmail setup error: {str(e)}")
    def _get_data(self) -> Optional[pd.DataFrame]:
        """Get data from selected source."""
        try:
            if self.data_source == "Upload CSV":
                uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
                if uploaded_file is not None:
                    df = pd.read_csv(uploaded_file)
                    if isinstance(df, pd.DataFrame):
                        return df
                    else:
                        st.error("Uploaded file is not a valid DataFrame.")
                        return None
            else:
                sheet_url = st.text_input("Enter Google Sheets URL")
                if sheet_url:
                    df = self.data_handler.connect_google_sheet(
                        sheet_url,
                        self.config.SHEETS_CREDS_FILE
                    )
                    if isinstance(df, pd.DataFrame):
                        return df
                    else:
                        st.error("Google Sheets data is not a valid DataFrame.")
                        return None
            return None
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return None

    def _show_data_preview(self, df: pd.DataFrame):
        """Show data preview and column selection."""
        st.subheader("Data Preview")
        
        # Basic stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Rows", len(df))
        col2.metric("Total Columns", len(df.columns))
        col3.metric("Missing Values", df.isnull().sum().sum())
        
        # Data preview
        st.dataframe(df.head())
        
        # Column selection
        st.subheader("Column Selection")
        self.email_column = st.selectbox(
            "Select Email Column",
            options=df.columns,
            help="Choose the column containing email addresses"
        )
        
        self.template_columns = st.multiselect(
            "Select Template Variables",
            options=[col for col in df.columns if col != self.email_column],
            help="Choose columns to use as variables in your email template"
        )

    def _setup_email_template(self):
        """Configure email template and scheduling."""
        st.subheader("Email Configuration")
        
        # Template setup
        self.subject_template = st.text_input(
            "Email Subject Template",
            help="Use {variable} syntax for dynamic content"
        )
        
        self.content_template = st.text_area(
            "Email Content Template",
            help="Use {variable} syntax for dynamic content. The template will be processed by the LLM."
        )
        
        # Scheduling setup
        st.subheader("Schedule Configuration")
        self.schedule_type = st.radio(
            "Sending Schedule",
            ["Send Immediately", "Schedule for Later", "Batch Schedule"]
        )
        
        if self.schedule_type != "Send Immediately":
            col1, col2 = st.columns(2)
            with col1:
                self.schedule_date = st.date_input("Start Date")
            with col2:
                self.schedule_time = st.time_input("Start Time")
                
            if self.schedule_type == "Batch Schedule":
                self.batch_size = st.number_input(
                    "Emails per Batch",
                    min_value=1,
                    max_value=100,
                    value=20
                )
                self.batch_interval = st.number_input(
                    "Hours between Batches",
                    min_value=1,
                    max_value=24,
                    value=1
                )

    def _process_emails(self, df: pd.DataFrame, batch_id: str):
        """Process emails based on configuration."""
        try:
            # Ensure df is a DataFrame
            if not isinstance(df, pd.DataFrame):
                st.error("Data is not a DataFrame.")
                return None
            
            processed_rows = []
            for _, row in df.iterrows():
                subject = self.subject_template
                content = self.content_template
                
                for col in self.template_columns:
                    placeholder = f"{{{col}}}"
                    value = str(row[col])
                    subject = subject.replace(placeholder, value)
                    content = content.replace(placeholder, value)
                
                processed_content = self.llm_processor.process_content(
                    content,
                    context={
                        'recipient': row[self.email_column],
                        'variables': {col: str(row[col]) for col in self.template_columns}
                    }
                )
                
                processed_rows.append({
                    'email': row[self.email_column],
                    'subject': subject,
                    'content': processed_content
                })
            
            template_config = {
                'subject': self.subject_template,
                'content': self.content_template,
                'email_column': self.email_column
            }
            
            return self.email_handler.create_batch(processed_rows, template_config)
            
        except Exception as e:
            st.error(f"Error processing emails: {str(e)}")
            return None

    
    def _show_analytics_dashboard(self, batch_id: Optional[str] = None):
        """Display email analytics dashboard using Seaborn visualizations."""
        st.subheader("Email Analytics")
        
        if batch_id:
            try:
                analytics = self.email_handler.get_batch_analytics(batch_id)
                
                # Display metrics in columns
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Emails", analytics['total'])
                with col2:
                    st.metric("Sent", analytics['sent'])
                with col3:
                    st.metric("Failed", analytics['failed'])
                with col4:
                    st.metric("Opened", analytics['opened'])
                
                # Prepare data for visualization
                status_data = pd.DataFrame({
                    'Status': ['Sent', 'Failed', 'Scheduled', 'Pending'],
                    'Count': [
                        analytics['sent'],
                        analytics['failed'],
                        analytics['scheduled'],
                        analytics['total'] - analytics['sent'] - analytics['failed'] - analytics['scheduled']
                    ]
                })
                
                # Create visualizations
                if not status_data.empty:
                    st.subheader("Status Distribution")
                    fig_status = self.analytics.create_status_visualization(status_data)
                    st.pyplot(fig_status)
                
                # Get detailed status data
                detailed_status = self.email_handler.get_detailed_status(batch_id)
                if detailed_status is not None:
                    # Create and display timeline visualization
                    st.subheader("Sending Pattern")
                    fig_timeline = self.analytics.create_timeline_visualization(detailed_status)
                    if fig_timeline:
                        st.pyplot(fig_timeline)
                    
                    # Create and display status heatmap
                    st.subheader("Status Transitions")
                    fig_heatmap = self.analytics.create_status_heatmap(detailed_status)
                    if fig_heatmap:
                        st.pyplot(fig_heatmap)
                    
                    # Show detailed status table if requested
                    if st.checkbox("Show Detailed Status"):
                        st.dataframe(
                            detailed_status,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Export options
                        col1, col2 = st.columns(2)
                        
                        # CSV export
                        csv = detailed_status.to_csv(index=False)
                        col1.download_button(
                            label="Download CSV Report",
                            data=csv,
                            file_name=f"email_campaign_report_{batch_id}.csv",
                            mime="text/csv"
                        )
                        
                        # Excel export
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            detailed_status.to_excel(writer, sheet_name='Campaign Report', index=False)
                        col2.download_button(
                            label="Download Excel Report",
                            data=buffer.getvalue(),
                            file_name=f"email_campaign_report_{batch_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                
            except Exception as e:
                st.error(f"Error loading analytics: {str(e)}")
                st.exception(e)
        else:
            st.info("Select a campaign to view analytics.")

    def run(self):
        """Main application flow."""
        st.title("AI Email Campaign Dashboard")
        
        if not self.redis_client:
            st.error("Redis connection is required for email functionality.")
            st.stop()
            return
            
        # Setup sidebar
        self._setup_sidebar()
        
        # Main content area
        tabs = st.tabs(["Data Setup", "Email Configuration", "Analytics"])
        
        # Data Setup Tab
        with tabs[0]:
            df = self._get_data()
            if df is not None and not df.empty:
                self._show_data_preview(df)
                
        # Email Configuration Tab
        with tabs[1]:
            if df is not None and not df.empty:
                self._setup_email_template()
                
                if st.button("Start Email Campaign"):
                    batch_id = f"batch_{datetime.now().timestamp()}"
                    self._process_emails(df, batch_id)
            else:
                st.info("Please load your data first in the Data Setup tab.")
                
        # Analytics Tab
        with tabs[2]:
            batches = self.email_handler.get_batch_list()
            if batches:
                selected_batch = st.selectbox(
                    "Select Campaign",
                    options=batches
                )
                self._show_analytics_dashboard(selected_batch)
            else:
                st.info("No email campaigns found.")

# Entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sns.set_theme(style="whitegrid")
    dashboard = AIAgentDashboard()
    dashboard.run()