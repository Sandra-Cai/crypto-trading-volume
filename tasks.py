from celery import Celery
import os
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

@celery.task
def refresh_trending_and_volumes():
    trending = fetch_coingecko_trending()
    for coin in trending:
        fetch_all_volumes(coin.upper())
    return f"Refreshed volumes for: {', '.join(trending)}"

@celery.task
def send_alerts():
    # Placeholder for alerting logic (e.g., check for volume/price spikes and notify users)
    pass

# Optionally, add periodic task schedule in Celery config
celery.conf.beat_schedule = {
    'refresh-every-10-minutes': {
        'task': 'tasks.refresh_trending_and_volumes',
        'schedule': 600.0,  # every 10 minutes
    },
}
celery.conf.timezone = 'UTC' 