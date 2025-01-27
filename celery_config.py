from celery.schedules import crontab
from datetime import timedelta

beat_schedule = {
    'process-email-queue': {
        'task': 'tasks.process_email_queue',
        'schedule': crontab(minute='*/1'),
    },
    'update-email-statuses': {
        'task': 'tasks.update_email_statuses',
        'schedule': crontab(minute='*/5'),
    },
}

task_routes = {
    'tasks.send_email': {'queue': 'email'},
    'tasks.send_scheduled_email': {'queue': 'scheduled_email'},
}

task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'UTC'
enable_utc = True
broker_connection_retry_on_startup = True

task_acks_late = True
worker_max_tasks_per_child = 100

task_time_limit = 1800
task_soft_time_limit = 1500
worker_prefetch_multiplier = 1
broker_transport_options = {'visibility_timeout': 43200}
result_expires = 60 * 60 * 24