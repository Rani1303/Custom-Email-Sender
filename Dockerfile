FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy both credential files and the rest of the application
COPY credentials.json .
COPY gmail_credentials.json .
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py"]