from celery.schedules import crontab
from datetime import timedelta

# Celery beat schedule
beat_schedule = {
    'process-email-queue': {
        'task': 'tasks.process_email_queue',
        'schedule': timedelta(minutes=1),
    },
    'update-email-statuses': {
        'task': 'tasks.update_email_statuses',
        'schedule': timedelta(minutes=5),
    },
}

# Task routes
task_routes = {
    'send_email': {'queue': 'email'},
    'send_scheduled_email': {'queue': 'scheduled_email'},
}

# Other Celery configurations
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True
broker_connection_retry_on_startup = True