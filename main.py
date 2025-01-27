import os
import pandas as pd
import streamlit as st
from datetime import datetime
from email_handlers import EmailHandler
from visualizations import create_status_visualization, create_timeline_visualization
from config import Config
from llm import LLMProcessor
import logging
import redis
import json

class EmailProcessingApp:
    def __init__(self):
        self.config = Config.from_env()
        self.redis_client = redis.StrictRedis.from_url(self.config.REDIS_URL, decode_responses=True)
        self.email_handler = EmailHandler(self.config)
        self.llm_processor = LLMProcessor(config=self.config)
        
    def _get_available_placeholders(self, df):
        return [col for col in df.columns if col != 'email']

    def _setup_email_template(self):
        st.subheader("Email Template Setup")
        
        uploaded_file = st.file_uploader("Upload Recipient List (CSV)", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.write("Preview of uploaded data:")
            st.dataframe(df.head())

            if "email" not in df.columns:
                st.error("The uploaded file must contain an 'email' column.")
                return

            placeholders = self._get_available_placeholders(df)
            st.write("Available Placeholders:")
            placeholder_cols = st.columns(len(placeholders))
            for idx, p in enumerate(placeholders):
                with placeholder_cols[idx]:
                    if st.button(f"{{{{{p}}}}}"):
                        if 'edited_template' not in st.session_state:
                            st.session_state.edited_template = st.session_state.get('email_template', '')
                        st.session_state.edited_template += f" {{{{{p}}}}}"

            st.subheader("Email Customization")
            tone = st.selectbox("Email Tone", 
                              ["Professional", "Friendly", "Formal", "Casual"])
            purpose = st.text_input("Email Purpose")
            key_points = st.text_area("Key Points to Include")
            cta = st.text_input("Call to Action")

            if st.button("Generate Template"):
                prompt = f"""
                Write a professional email with:
                Tone: {tone}
                Purpose: {purpose}
                Key Points: {key_points}
                Call to Action: {cta}
                """
                generated_content = self.llm_processor.generate_email(
                    prompt=prompt,
                    placeholders=placeholders
                )
                
                if generated_content:
                    st.session_state.email_template = generated_content
                    st.session_state.edited_template = generated_content

            if 'email_template' in st.session_state:
                st.subheader("Edit Template")
                subject = st.text_input("Email Subject", 
                                      value=st.session_state.get('subject', ''))
                edited_template = st.text_area("Edit Email Body", 
                                             value=st.session_state.get('edited_template', ''),
                                             height=300)
                st.session_state.edited_template = edited_template
                st.session_state.subject = subject

                if st.button("Preview Emails"):
                    self._preview_emails(df, subject, edited_template)

                if st.button("Send Emails"):
                    batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    processed_batch = self._process_emails(df, batch_id, subject, edited_template)
                    if processed_batch:
                        st.success(f"Emails sent successfully! Batch ID: {batch_id}")
                    else:
                        st.error("Failed to send emails. Please check logs.")

    def _preview_emails(self, df, subject, template):
        for idx, row in df.head(3).iterrows():
            placeholders = {col: row[col] for col in df.columns if col != 'email'}
            try:
                formatted_content = template.format(**placeholders)
                formatted_subject = subject.format(**placeholders)
                
                st.write(f"Preview {idx + 1}:")
                st.write(f"To: {row['email']}")
                st.write(f"Subject: {formatted_subject}")
                st.write("Body:")
                st.write(formatted_content)
                st.divider()
            except KeyError as e:
                st.error(f"Invalid placeholder: {e}")

    def _process_emails(self, df, batch_id, subject, template):
        email_status = []
        
        for _, row in df.iterrows():
            try:
                placeholders = {col: row[col] for col in df.columns if col != 'email'}
                formatted_content = template.format(**placeholders)
                formatted_subject = subject.format(**placeholders)
                
                success = self.email_handler.send_email(
                    to_email=row['email'],
                    subject=formatted_subject,
                    content=formatted_content
                )
                
                status = {
                    "email": row['email'],
                    "status": "Sent" if success else "Failed",
                    "timestamp": datetime.now().isoformat()
                }
                email_status.append(status)
                
            except Exception as e:
                logging.error(f"Failed to send email to {row['email']}: {e}")
                email_status.append({
                    "email": row['email'],
                    "status": "Failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        self.redis_client.set(batch_id, json.dumps(email_status))
        return email_status

    def run(self):
        st.title("Email Processing Application")
        st.sidebar.title("Navigation")
        tabs = st.sidebar.radio("Go to", ["Email Template", "Analytics Dashboard"])

        if tabs == "Email Template":
            self._setup_email_template()
        elif tabs == "Analytics Dashboard":
            self._show_analytics_dashboard()

    def _show_analytics_dashboard(self, batch_id):
        st.subheader("Analytics Dashboard")

        try:
            batch_data = self.redis_client.get(batch_id)
            if batch_data:
                email_status = json.loads(batch_data)
                df = pd.DataFrame(email_status)

                st.write("Email Status Data:")
                st.dataframe(df)

                st.write("Email Status Visualization:")
                create_status_visualization(email_status)

                st.write("Email Timeline Visualization:")
                create_timeline_visualization(email_status)
            else:
                st.warning("No data found for the provided Batch ID.")
        except Exception as e:
            st.error(f"Failed to load analytics for Batch ID {batch_id}: {e}")


if __name__ == "__main__":
    app = EmailProcessingApp()
    app.run()
