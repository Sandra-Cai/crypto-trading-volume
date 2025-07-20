from celery import Celery
import os
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical, detect_volume_spike
# Import alert functions and DB helpers from web_dashboard
from web_dashboard import send_telegram_alert, send_discord_alert, get_db, query_db, notify_major_alert

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
    # Query all users with alert settings
    db = get_db()
    users = query_db('SELECT id, username, telegram_id, discord_webhook, favorites FROM users')
    for user in users:
        user_id, username, telegram_id, discord_webhook, favorites = user
        if not telegram_id and not discord_webhook:
            continue
        # For each favorite coin, check for volume spike
        coins = favorites.split(',') if favorites else []
        for coin in coins:
            symbol = coin.upper()
            hist = fetch_all_historical(symbol)
            for ex, vols in hist.items():
                if vols and len(vols) >= 3:
                    is_spike, ratio = detect_volume_spike(vols)
                    if is_spike:
                        msg = f"[ALERT] {symbol} volume spike on {ex}: Current volume is {ratio:.2f}x average."
                        # Send Telegram alert
                        if telegram_id:
                            # Use your real bot token in production
                            send_telegram_alert(telegram_id, msg, bot_token=os.environ.get('TELEGRAM_BOT_TOKEN', 'demo'))
                        # Send Discord alert
                        if discord_webhook:
                            send_discord_alert(discord_webhook, msg)
                        # Create user notification
                        notify_major_alert(user_id, symbol, ex, 'volume_spike', msg)
    return "Alerts sent."

# Optionally, add periodic task schedule in Celery config
celery.conf.beat_schedule = {
    'refresh-every-10-minutes': {
        'task': 'tasks.refresh_trending_and_volumes',
        'schedule': 600.0,  # every 10 minutes
    },
    'alerts-every-5-minutes': {
        'task': 'tasks.send_alerts',
        'schedule': 300.0,  # every 5 minutes
    },
}
celery.conf.timezone = 'UTC' 