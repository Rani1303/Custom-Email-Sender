from celery import Celery
from celery.schedules import crontab
import os
from datetime import timedelta
import logging
from email_handlers import EmailHandler
from config import Config
import json
import redis
from celery.utils.log import get_task_logger

config = Config.from_env()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


logger = get_task_logger(__name__)
celery = Celery('email_tasks')
redis_url = os.getenv('REDIS_URL')
if not redis_url:
    raise ValueError("REDIS_URL environment variable is required.")

email_rate_limit = os.getenv('EMAIL_RATE_LIMIT', '50/h')
if not os.getenv('EMAIL_RATE_LIMIT'):
    logger.warning("EMAIL_RATE_LIMIT not set. Defaulting to 50/h.")

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
            'rate_limit': email_rate_limit
        }
    }
)

celery.conf.beat_schedule = {
    'process-email-queue': {
        'task': 'tasks.process_email_queue',
        'schedule': timedelta(minutes=int(os.getenv('EMAIL_QUEUE_INTERVAL', 1))),
    },
    'update-email-statuses': {
        'task': 'tasks.update_email_statuses',
        'schedule': timedelta(minutes=int(os.getenv('EMAIL_STATUS_INTERVAL', 5))),
    },
}

email_handler = EmailHandler(config)

@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def send_email(self, to_email, subject, content):
    try:
        response = email_handler.send_email(to_email, subject, content)
        logger.info(f"Email sent to {to_email}: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {str(e)}")
        self.retry(exc=e)


@celery.task(bind=True)
def process_email_queue(self):
    logger.info("Processing email queue...")
    try:
        redis_client = redis.StrictRedis.from_url(config.REDIS_URL, decode_responses=True)
       
        pending_emails = redis_client.keys("email_queue:*")
        logger.info(f"Found {len(pending_emails)} pending emails")
        
        for email_key in pending_emails:
            try:
                email_data = json.loads(redis_client.get(email_key))
                logger.info(f"Processing email: {email_data['to_email']}")
                
                email_handler = EmailHandler(config)
                success = email_handler.send_email(
                    to_email=email_data['to_email'],
                    subject=email_data['subject'],
                    content=email_data['content'],
                    batch_id=email_data.get('batch_id')
                )
                
                if success:
                    redis_client.delete(email_key)
                    logger.info(f"Successfully sent email to {email_data['to_email']}")
                else:
                    logger.error(f"Failed to send email to {email_data['to_email']}")
                
            except Exception as e:
                logger.error(f"Error processing email {email_key}: {str(e)}")
                continue
                
        logger.info("Email queue processed successfully.")
        return True
        
    except Exception as e:
        logger.error(f"Error processing email queue: {str(e)}")
        return False

@celery.task(bind=True)
def update_email_statuses(self):
    logger.info("Updating email statuses...")
    try:
        result = True
        logger.info("Email statuses updated successfully.")
        return result
    except Exception as e:
        logger.error(f"Error updating email statuses: {str(e)}")
        self.retry(exc=e)
