from celery import Celery
from celery.schedules import crontab
import os
from datetime import timedelta

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
celery = Celery('tasks', broker=redis_url, backend=redis_url)


celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_annotations={
        'tasks.send_email': {
            'rate_limit': f"{os.getenv('EMAIL_RATE_LIMIT', '50')}/h"
        }
    }
)

celery.conf.beat_schedule = {
    'process-email-queue': {
        'task': 'tasks.process_email_queue',
        'schedule': timedelta(minutes=1),
    },
    'update-email-statuses': {
        'task': 'tasks.update_email_statuses',
        'schedule': timedelta(minutes=5),
    },
}

@celery.task
def send_email(to_email, subject, content):
    """Send an email task."""
    try:
        print(f"Sending email to {to_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

@celery.task
def process_email_queue():
    """Process the email queue."""
    print("Processing email queue...")
    return True

@celery.task
def update_email_statuses():
    """Update email delivery statuses."""
    print("Updating email statuses...")
    return True