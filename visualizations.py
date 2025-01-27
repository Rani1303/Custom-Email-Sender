import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import matplotlib.dates as mdates
from datetime import datetime
import streamlit as st

def create_status_visualization(email_status):
    df = pd.DataFrame(email_status)
    status_counts = df['status'].value_counts()
    plt.figure(figsize=(10, 6))
    sns.barplot(
        x=status_counts.index,
        y=status_counts.values,
        hue=status_counts.index,
        legend=False
    )
    plt.title('Email Status Distribution')
    plt.xlabel('Status')
    plt.ylabel('Count')
    st.pyplot(plt)

def create_timeline_visualization(email_status):
    df = pd.DataFrame(email_status)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    plt.figure(figsize=(12, 6))
    sns.scatterplot(
        data=df,
        x='timestamp',
        y='status',
        hue='status',
        style='status'
    )
    plt.title('Email Sending Timeline')
    plt.xticks(rotation=45)
    st.pyplot(plt)