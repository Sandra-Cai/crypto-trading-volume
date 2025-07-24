from flask import Flask, render_template_string, request, redirect, url_for, session, g, jsonify
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical, detect_volume_spike, calculate_price_volume_correlation
from trading_bot import TradingBot, create_strategy_config
from functools import wraps
import plotly.graph_objs as go
import plotly.offline as pyo
import requests
import csv
import io
import threading
import sqlite3
import hashlib
import time
import os
import json
from werkzeug.security import generate_password_hash
from datetime import datetime
import secrets
import requests as ext_requests
from pywebpush import webpush, WebPushException
import smtplib
from email.mime.text import MIMEText
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from flasgger import Swagger, swag_from
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production
DATABASE = 'users.db'

swagger = Swagger(app)
limiter = Limiter(app, key_func=get_remote_address)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Check if user is admin
        db = get_db()
        user = query_db('SELECT is_admin FROM users WHERE id = ?', [session['user_id']], one=True)
        if not user or not user[0]:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- i18n dictionary ---
LANGUAGES = {
    'en': {
        'login': 'Login',
        'register': 'Register',
        'logout': 'Logout',
        'user_profile': 'User Profile',
        'favorites': 'Favorite Coins',
        'save_favorites': 'Save Favorites',
        'trading_bot': 'Trading Bot (Demo Mode)',
        'start_bot': 'Start Bot',
        'stop_bot': 'Stop Bot',
        'strategy': 'Strategy',
        'coin': 'Coin',
        'all': 'All',
        'volume_spike': 'Volume Spike',
        'rsi': 'RSI',
        'price_alerts': 'Price Alerts',
        'portfolio_value': 'Portfolio Value',
        'trade_log': 'Trade Log',
        'backtesting': 'Backtesting',
        'days': 'Days',
        'run_backtest': 'Run Backtest',
        'user_profile': 'User Profile',
        'already_account': 'Already have an account?',
        'dont_account': "Don't have an account?",
        'save': 'Save',
        'update': 'Update',
        'live_binance': 'Live (Binance)',
        'select_language': 'Select Language',
        'english': 'English',
        'spanish': 'Spanish',
    },
    'es': {
        'login': 'Iniciar sesión',
        'register': 'Registrarse',
        'logout': 'Cerrar sesión',
        'user_profile': 'Perfil de usuario',
        'favorites': 'Monedas favoritas',
        'save_favorites': 'Guardar favoritos',
        'trading_bot': 'Bot de Trading (Modo Demo)',
        'start_bot': 'Iniciar Bot',
        'stop_bot': 'Detener Bot',
        'strategy': 'Estrategia',
        'coin': 'Moneda',
        'all': 'Todas',
        'volume_spike': 'Volumen Pico',
        'rsi': 'RSI',
        'price_alerts': 'Alertas de Precio',
        'portfolio_value': 'Valor de Portafolio',
        'trade_log': 'Registro de Operaciones',
        'backtesting': 'Backtesting',
        'days': 'Días',
        'run_backtest': 'Ejecutar Backtest',
        'user_profile': 'Perfil de usuario',
        'already_account': '¿Ya tienes una cuenta?',
        'dont_account': '¿No tienes una cuenta?',
        'save': 'Guardar',
        'update': 'Actualizar',
        'live_binance': 'En Vivo (Binance)',
        'select_language': 'Seleccionar idioma',
        'english': 'Inglés',
        'spanish': 'Español',
    }
}

def t(key):
    lang = session.get('lang', 'en')
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, key)

@app.route('/setlang', methods=['POST'])
def set_language():
    lang = request.form.get('lang', 'en')
    session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# --- User DB helpers ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, favorites TEXT)''')
        db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- Registration ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            db = get_db()
            db.execute('INSERT INTO users (username, password, favorites) VALUES (?, ?, ?)', (username, hashed, ''))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already exists.'
    return render_template_string('''
    <html><head><title>Register</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Register</h2>
    {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
    <form method="post" class="w-100 w-md-50 mx-auto">
        <div class="mb-3"><label class="form-label">Username:</label><input class="form-control" type="text" name="username"></div>
        <div class="mb-3"><label class="form-label">Password:</label><input class="form-control" type="password" name="password"></div>
        <button class="btn btn-primary" type="submit">Register</button>
    </form>
    <div class="mt-3">Already have an account? <a href="{{ url_for('login') }}">Login</a></div>
    </body></html>
    ''', error=error)

# --- Login (update to use DB) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        user = query_db('SELECT * FROM users WHERE username = ? AND password = ?', [username, hashed], one=True)
        if user:
            session['logged_in'] = True
            session['user_id'] = user[0]
            session['username'] = username
            # Log login event
            log_event('login', user[0], username, 'User logged in')
            return redirect(url_for('index'))
        else:
            error = 'Invalid credentials'
    return render_template_string('''
    <html><head><title>Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Login</h2>
    {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
    <form method="post" class="w-100 w-md-50 mx-auto">
        <div class="mb-3"><label class="form-label">Username:</label><input class="form-control" type="text" name="username"></div>
        <div class="mb-3"><label class="form-label">Password:</label><input class="form-control" type="password" name="password"></div>
        <button class="btn btn-primary" type="submit">Login</button>
    </form>
    <div class="mt-3">Don't have an account? <a href="{{ url_for('register') }}">Register</a></div>
    </body></html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

# --- Favorite coins (profile) ---
@app.route('/favorites', methods=['POST'])
@login_required
def save_favorites():
    user_id = session.get('user_id')
    favorites = request.form.getlist('favorites')
    db = get_db()
    db.execute('UPDATE users SET favorites = ? WHERE id = ?', (','.join(favorites), user_id))
    db.commit()
    return redirect(url_for('index'))



@app.route('/bot', methods=['POST'])
def bot_control():
    action = request.form.get('bot_action')
    coin = request.form.get('bot_coin')
    strategy = request.form.get('bot_strategy')
    session_id = session.get('user_id', 'default')
    if action == 'start' and coin:
        config = create_strategy_config()
        if strategy == 'volume_spike':
            config['rsi_enabled'] = False
            config['price_alerts_enabled'] = False
        elif strategy == 'rsi':
            config['volume_spike_enabled'] = False
            config['price_alerts_enabled'] = False
        elif strategy == 'price_alerts':
            config['volume_spike_enabled'] = False
            config['rsi_enabled'] = False
        bot = TradingBot(config, demo_mode=True)
        bot_instances[session_id] = bot
        t = threading.Thread(target=bot.start, args=(coin,))
        t.daemon = True
        t.start()
        session['bot_running'] = True
        session['bot_coin'] = coin
        session['bot_strategy'] = strategy
    elif action == 'stop':
        bot = bot_instances.get(session_id)
        if bot:
            bot.stop()
        session['bot_running'] = False
    return redirect(url_for('index'))

@app.route('/backtest', methods=['POST'])
def backtest_control():
    coin = request.form.get('backtest_coin')
    strategy = request.form.get('backtest_strategy')
    days = int(request.form.get('backtest_days', 30))
    result = ''
    if coin and strategy:
        import io
        import sys
        buf = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        if strategy == 'volume_spike':
            backtest_volume_spike(coin, days=days)
        elif strategy == 'rsi':
            backtest_rsi(coin, days=days)
        sys.stdout = sys_stdout
        result = buf.getvalue()
    session['backtest_result'] = result
    session['backtest_coin'] = coin
    session['backtest_strategy'] = strategy
    session['backtest_days'] = days
    return redirect(url_for('index'))

# --- News Aggregation & Sentiment ---
def fetch_news(coin):
    # Use CryptoPanic or NewsAPI for demo (CryptoPanic is free for headlines)
    url = f'https://cryptopanic.com/api/v1/posts/?auth_token=demo&currencies={coin.lower()}'
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return [item['title'] for item in data.get('results', [])]
    except Exception:
        pass
    return []

def fetch_price_history(symbol, days=7):
    """Fetch price history for a given symbol"""
    try:
        url = f'https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_chart?vs_currency=usd&days={days}'
        response = requests.get(url)
        if response.status_code != 200:
            return []
        data = response.json()
        return [price[1] for price in data['prices']]
    except Exception as e:
        print(f"Error fetching price history for {symbol}: {e}")
        return []

def simple_sentiment(text):
    # Very basic sentiment: positive if contains 'up', 'bull', negative if 'down', 'bear', else neutral
    text = text.lower()
    if any(word in text for word in ['up', 'bull', 'gain', 'surge', 'rise', 'positive']):
        return 'positive'
    if any(word in text for word in ['down', 'bear', 'loss', 'drop', 'fall', 'negative']):
        return 'negative'
    return 'neutral'

# --- Telegram/Discord Integration ---
def send_telegram_alert(chat_id, message, bot_token):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {'chat_id': chat_id, 'text': message}
    try:
        requests.post(url, data=data)
    except Exception:
        pass

def send_discord_alert(webhook_url, message):
    data = {'content': message}
    try:
        requests.post(webhook_url, json=data)
    except Exception:
        pass

# --- Update user DB for alert settings ---
def add_alert_settings_column():
    with app.app_context():
        db = get_db()
        db.execute('''ALTER TABLE users ADD COLUMN telegram_id TEXT''')
        db.execute('''ALTER TABLE users ADD COLUMN discord_webhook TEXT''')
        db.commit()

def add_webhook_columns():
    with app.app_context():
        db = get_db()
        try:
            db.execute('ALTER TABLE users ADD COLUMN webhook_url TEXT')
            db.execute('ALTER TABLE users ADD COLUMN webhook_alert_types TEXT')
            db.commit()
        except Exception:
            pass
add_webhook_columns()

# --- Settings page for alerts ---
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session.get('user_id')
    db = get_db()
    error = None
    test_result = None
    if request.method == 'POST':
        if 'test_webhook' in request.form:
            # Test webhook logic
            row = query_db('SELECT webhook_url FROM users WHERE id = ?', [user_id], one=True)
            webhook_url = row[0] if row else ''
            if not webhook_url:
                test_result = ('danger', 'No webhook URL set.')
            else:
                import requests
                payload = {
                    'user': session.get('username'),
                    'coin': 'bitcoin',
                    'exchange': 'binance',
                    'alert_type': 'test',
                    'message': 'This is a test webhook from Crypto Trading Volume.'
                }
                try:
                    resp = requests.post(webhook_url, json=payload, timeout=5)
                    if resp.status_code == 200:
                        test_result = ('success', 'Webhook test successful!')
                    else:
                        test_result = ('danger', f'Webhook test failed (status {resp.status_code})')
                except Exception as e:
                    test_result = ('danger', f'Webhook test failed: {e}')
        else:
            telegram_id = request.form.get('telegram_id', '')
            discord_webhook = request.form.get('discord_webhook', '')
            webhook_url = request.form.get('webhook_url', '')
            webhook_alert_types = ','.join(request.form.getlist('webhook_alert_types'))
            email = request.form.get('email', '')
            db.execute('UPDATE users SET telegram_id = ?, discord_webhook = ?, webhook_url = ?, webhook_alert_types = ?, email = ? WHERE id = ?',
                       (telegram_id, discord_webhook, webhook_url, webhook_alert_types, email, user_id))
            db.commit()
            return redirect(url_for('settings'))
    row = query_db('SELECT telegram_id, discord_webhook, webhook_url, webhook_alert_types, email FROM users WHERE id = ?', [user_id], one=True)
    telegram_id = row[0] if row else ''
    discord_webhook = row[1] if row else ''
    webhook_url = row[2] if row and len(row) > 2 else ''
    webhook_alert_types = row[3].split(',') if row and row[3] else []
    email = row[4] if row and len(row) > 4 else ''
    alert_type_options = ['volume_spike', 'price_spike', 'whale_alert', 'technical', 'arbitrage', 'news', 'daily_summary']
    browser_notifications = False
    row2 = query_db('SELECT browser_notifications FROM users WHERE id = ?', [user_id], one=True)
    if row2 and row2[0]:
        browser_notifications = bool(row2[0])
    if request.method == 'POST':
        browser_notifications = 1 if request.form.get('browser_notifications') == 'on' else 0
        db.execute('UPDATE users SET browser_notifications = ? WHERE id = ?', (browser_notifications, user_id))
        db.commit()
    return render_template_string('''
    <html><head><title>Alert Settings</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Alert Settings</h2>
    {% if test_result %}
    <div class="alert alert-{{ test_result[0] }}">{{ test_result[1] }}</div>
    {% endif %}
    <form method="post" class="w-100 w-md-50 mx-auto" id="settings-form">
        <div class="mb-3"><label class="form-label">Email:</label><input class="form-control" type="email" name="email" value="{{ email }}"></div>
        <div class="mb-3"><label class="form-label">Telegram Chat ID:</label><input class="form-control" type="text" name="telegram_id" value="{{ telegram_id }}"></div>
        <div class="mb-3"><label class="form-label">Discord Webhook URL:</label><input class="form-control" type="text" name="discord_webhook" value="{{ discord_webhook }}"></div>
        <div class="mb-3"><label class="form-label">Webhook URL:</label><input class="form-control" type="text" name="webhook_url" value="{{ webhook_url }}"></div>
        <div class="mb-3"><label class="form-label">Webhook Alert Types:</label>
            {% for t in alert_type_options %}
            <div class="form-check">
                <input class="form-check-input" type="checkbox" name="webhook_alert_types" value="{{ t }}" id="{{ t }}" {% if t in webhook_alert_types %}checked{% endif %}>
                <label class="form-check-label" for="{{ t }}">{{ t.replace('_', ' ').title() }}</label>
            </div>
            {% endfor %}
        </div>
        <div class="mb-3 form-check">
            <input class="form-check-input" type="checkbox" name="browser_notifications" id="browser_notifications" {% if browser_notifications %}checked{% endif %}>
            <label class="form-check-label" for="browser_notifications">Enable Browser Notifications</label>
        </div>
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn btn-secondary ms-2" name="test_webhook" value="1" type="submit">Test Webhook</button>
    </form>
    <script>
    if ('serviceWorker' in navigator && window.PushManager) {
        navigator.serviceWorker.register('/static/sw.js').then(function(reg) {
            if (Notification.permission === 'granted') {
                reg.pushManager.getSubscription().then(function(sub) {
                    if (!sub) {
                        reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: 'BElL0...YOUR_PUBLIC_KEY...'}).then(function(newSub) {
                            fetch('/api/push_subscription', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(newSub)});
                        });
                    } else {
                        fetch('/api/push_subscription', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(sub)});
                    }
                });
            } else {
                Notification.requestPermission();
            }
        });
    }
    </script>
    <div class="mt-3"><a href="{{ url_for('index') }}">Back to Dashboard</a></div>
    </body></html>
    ''', telegram_id=telegram_id, discord_webhook=discord_webhook, webhook_url=webhook_url, webhook_alert_types=webhook_alert_types, alert_type_options=alert_type_options, test_result=test_result, email=email, browser_notifications=browser_notifications)

# --- Enhanced Whale Alerts (mocked, with Redis cache) ---
def fetch_whale_alerts(coin):
    key = f'whale_alerts_{coin.lower()}'
    if redis_client:
        cached = redis_client.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass
    # Demo/mock data for several coins
    data = []
    if coin.lower() == 'bitcoin':
        data = [
            {'amount': 1200, 'from': 'ExchangeA', 'to': 'Wallet', 'timestamp': '2024-05-01 12:00', 'txid': 'abc123'},
            {'amount': 800, 'from': 'Wallet', 'to': 'ExchangeB', 'timestamp': '2024-05-01 10:30', 'txid': 'def456'},
        ]
    elif coin.lower() == 'ethereum':
        data = [
            {'amount': 5000, 'from': 'ExchangeC', 'to': 'Wallet', 'timestamp': '2024-05-01 11:00', 'txid': 'eth789'},
            {'amount': 3000, 'from': 'Wallet', 'to': 'ExchangeD', 'timestamp': '2024-05-01 09:45', 'txid': 'eth012'},
        ]
    elif coin.lower() == 'solana':
        data = [
            {'amount': 100000, 'from': 'ExchangeE', 'to': 'Wallet', 'timestamp': '2024-05-01 08:00', 'txid': 'sol345'},
        ]
    if redis_client:
        try:
            redis_client.setex(key, 300, json.dumps(data))
        except Exception:
            pass
    return data

# --- Enhanced On-chain Stats (mocked, with Redis cache) ---
def fetch_onchain_stats(coin):
    key = f'onchain_stats_{coin.lower()}'
    if redis_client:
        cached = redis_client.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass
    # Demo/mock data for several coins
    if coin.lower() == 'bitcoin':
        data = {'active_addresses': 950000, 'large_transfers': 120, 'total_volume': 3500000}
    elif coin.lower() == 'ethereum':
        data = {'active_addresses': 600000, 'large_transfers': 80, 'total_volume': 2100000}
    elif coin.lower() == 'solana':
        data = {'active_addresses': 150000, 'large_transfers': 20, 'total_volume': 500000}
    else:
        data = {'active_addresses': 0, 'large_transfers': 0, 'total_volume': 0}
    if redis_client:
        try:
            redis_client.setex(key, 300, json.dumps(data))
        except Exception:
            pass
    return data

def add_dashboard_prefs_column():
    with app.app_context():
        db = get_db()
        try:
            db.execute('ALTER TABLE users ADD COLUMN dashboard_prefs TEXT')
            db.commit()
        except Exception:
            pass  # Column may already exist

def add_is_admin_column():
    with app.app_context():
        db = get_db()
        try:
            db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
            db.commit()
        except Exception:
            pass  # Column may already exist

def add_event_log_table():
    with app.app_context():
        db = get_db()
        try:
            db.execute('''CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                user_id INTEGER,
                username TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            db.commit()
        except Exception:
            pass

add_is_admin_column()
add_event_log_table()

# Call this on startup to ensure column exists
add_dashboard_prefs_column()

# --- Log event helper ---
def log_event(event_type, user_id, username, details):
    db = get_db()
    db.execute('INSERT INTO event_log (event_type, user_id, username, details) VALUES (?, ?, ?, ?)',
               (event_type, user_id, username, details))
    db.commit()

def log_api_event(event_type, endpoint, user_id=None, username=None, details=None):
    db = get_db()
    db.execute('INSERT INTO event_log (event_type, user_id, username, details) VALUES (?, ?, ?, ?)',
               (event_type, user_id, username, f'Endpoint: {endpoint} | {details or ""}'))
    db.commit()

# --- Log alert event helper ---
def log_alert_event(user_id, username, coin, exchange, alert_type, channel, message):
    db = get_db()
    details = f'coin={coin}, exchange={exchange}, type={alert_type}, channel={channel}, message={message}'
    db.execute('INSERT INTO event_log (event_type, user_id, username, details) VALUES (?, ?, ?, ?)',
               ('alert', user_id, username, details))
    db.commit()

# --- Resend alert helper ---
def resend_alert(user_id, channel, message):
    user = query_db('SELECT telegram_id, discord_webhook FROM users WHERE id = ?', [user_id], one=True)
    if not user:
        return False
    telegram_id, discord_webhook = user
    if channel == 'telegram' and telegram_id:
        send_telegram_alert(telegram_id, message, bot_token=os.environ.get('TELEGRAM_BOT_TOKEN', 'demo'))
        return True
    if channel == 'discord' and discord_webhook:
        send_discord_alert(discord_webhook, message)
        return True
    return False

# --- Webhook alert sending helper with retry ---
def send_webhook_alert(user_id, coin, exchange, alert_type, message):
    user = query_db('SELECT username, webhook_url, webhook_alert_types FROM users WHERE id = ?', [user_id], one=True)
    if not user:
        return False
    username, webhook_url, webhook_alert_types = user
    if not webhook_url or not webhook_alert_types:
        return False
    types = webhook_alert_types.split(',') if webhook_alert_types else []
    if alert_type not in types:
        return False
    import requests
    payload = {
        'user': username,
        'coin': coin,
        'exchange': exchange,
        'alert_type': alert_type,
        'message': message
    }
    for attempt in range(1, 4):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=5)
            log_event('webhook_alert', user_id, username, f'Webhook attempt {attempt}: {alert_type} {coin} {exchange} {message} (status {resp.status_code})')
            if resp.status_code == 200:
                return True
        except Exception as e:
            log_event('webhook_alert', user_id, username, f'Webhook attempt {attempt} failed: {alert_type} {coin} {exchange} {message} ({e})')
        time.sleep(1)
    return False

# --- Admin dashboard with audit log search/filter and API stats ---
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    # --- Audit log search/filter form ---
    event_type = request.form.get('event_type', '')
    username = request.form.get('username', '')
    date_from = request.form.get('date_from', '')
    date_to = request.form.get('date_to', '')
    query = 'SELECT event_type, username, details, timestamp FROM event_log WHERE 1=1'
    params = []
    if event_type:
        query += ' AND event_type = ?'
        params.append(event_type)
    if username:
        query += ' AND username = ?'
        params.append(username)
    if date_from:
        query += ' AND timestamp >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND timestamp <= ?'
        params.append(date_to)
    query += ' ORDER BY timestamp DESC LIMIT 50'
    events = query_db(query, params)
    # User activity
    users = query_db('SELECT id, username, is_admin, password FROM users ORDER BY id')
    # Background job status (mocked for now)
    celery_status = 'OK (demo)'
    # Cache stats (mocked for now)
    cache_stats = {'redis': 'OK' if redis_client else 'Unavailable'}
    # --- API usage/error stats ---
    api_stats = query_db('SELECT event_type, COUNT(*) FROM event_log WHERE event_type LIKE "api_%" GROUP BY event_type')
    api_labels = [row[0] for row in api_stats]
    api_counts = [row[1] for row in api_stats]
    api_bar = ''
    if api_labels:
        fig = go.Figure([go.Bar(x=api_labels, y=api_counts)])
        fig.update_layout(title='API Usage & Error Events', xaxis_title='Event Type', yaxis_title='Count')
        api_bar = pyo.plot(fig, output_type='div', include_plotlyjs=False)
    return render_template_string('''
    <html><head><title>Admin Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    </head><body class="container py-5">
    <h2>Admin Dashboard</h2>
    <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">Back to Dashboard</a>
    <div class="mb-4">
        <h4>Audit Log Search/Filter</h4>
        <form method="post" class="row g-2 mb-3">
            <div class="col-md-2"><input class="form-control" type="text" name="event_type" placeholder="Event Type" value="{{ request.form.get('event_type', '') }}"></div>
            <div class="col-md-2"><input class="form-control" type="text" name="username" placeholder="Username" value="{{ request.form.get('username', '') }}"></div>
            <div class="col-md-2"><input class="form-control" type="date" name="date_from" value="{{ request.form.get('date_from', '') }}"></div>
            <div class="col-md-2"><input class="form-control" type="date" name="date_to" value="{{ request.form.get('date_to', '') }}"></div>
            <div class="col-md-2"><button class="btn btn-primary" type="submit">Filter</button></div>
        </form>
        <table class="table table-bordered table-striped">
            <thead><tr><th>Type</th><th>User</th><th>Details</th><th>Time</th></tr></thead>
            <tbody>
            {% for e in events %}
            <tr><td>{{ e[0] }}</td><td>{{ e[1] }}</td><td>{{ e[2] }}</td><td>{{ e[3] }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="mb-4">
        <h4>API Usage & Error Stats</h4>
        <div>{{ api_bar|safe }}</div>
    </div>
    <div class="mb-4">
        <h4>User Accounts</h4>
        <table class="table table-bordered table-striped">
            <thead><tr><th>ID</th><th>Username</th><th>Admin?</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
            {% for u in users %}
            <tr>
                <td>{{ u[0] }}</td>
                <td>{{ u[1] }}</td>
                <td>{{ 'Yes' if u[2] else 'No' }}</td>
                <td>{% if u[3] == 'DEACTIVATED' %}<span class="badge bg-danger">Deactivated</span>{% else %}<span class="badge bg-success">Active</span>{% endif %}</td>
                <td>
                    {% if not u[2] %}
                        <a href="{{ url_for('promote_user', user_id=u[0]) }}" class="btn btn-sm btn-success">Promote to Admin</a>
                    {% else %}
                        <a href="{{ url_for('demote_user', user_id=u[0]) }}" class="btn btn-sm btn-warning">Demote Admin</a>
                    {% endif %}
                    {% if u[3] != 'DEACTIVATED' %}
                        <a href="{{ url_for('deactivate_user', user_id=u[0]) }}" class="btn btn-sm btn-danger">Deactivate</a>
                    {% else %}
                        <form method="post" action="{{ url_for('reactivate_user', user_id=u[0]) }}" style="display:inline-block">
                            <input type="password" name="new_password" placeholder="New password" class="form-control form-control-sm d-inline w-auto" required>
                            <button type="submit" class="btn btn-sm btn-primary">Reactivate</button>
                        </form>
                    {% endif %}
                    <form method="post" action="{{ url_for('reset_password', user_id=u[0]) }}" style="display:inline-block">
                        <input type="password" name="new_password" placeholder="New password" class="form-control form-control-sm d-inline w-auto" required>
                        <button type="submit" class="btn btn-sm btn-secondary">Reset Password</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="mb-4">
        <h4>Background Jobs</h4>
        <div>Status: <b>{{ celery_status }}</b></div>
    </div>
    <div class="mb-4">
        <h4>Cache</h4>
        <div>Redis: <b>{{ cache_stats['redis'] }}</b></div>
    </div>
    </body></html>
    ''', events=events, users=users, celery_status=celery_status, cache_stats=cache_stats, api_bar=api_bar)

# ... (rest of the code remains unchanged)

# --- Alerts management in admin dashboard ---
@app.route('/admin/alerts', methods=['GET', 'POST'])
@admin_required
def admin_alerts():
    # Filters
    username = request.form.get('username', '')
    coin = request.form.get('coin', '')
    alert_type = request.form.get('alert_type', '')
    channel = request.form.get('channel', '')
    date_from = request.form.get('date_from', '')
    date_to = request.form.get('date_to', '')
    query = "SELECT id, user_id, username, details, timestamp FROM event_log WHERE event_type = 'alert'"
    params = []
    if username:
        query += ' AND username = ?'
        params.append(username)
    if coin:
        query += " AND details LIKE ?"
        params.append(f'%coin={coin}%')
    if alert_type:
        query += " AND details LIKE ?"
        params.append(f'%type={alert_type}%')
    if channel:
        query += " AND details LIKE ?"
        params.append(f'%channel={channel}%')
    if date_from:
        query += ' AND timestamp >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND timestamp <= ?'
        params.append(date_to)
    query += ' ORDER BY timestamp DESC LIMIT 50'
    alerts = query_db(query, params)
    # Resend logic
    if request.method == 'POST' and 'resend_id' in request.form:
        alert_id = int(request.form['resend_id'])
        alert = query_db('SELECT user_id, details FROM event_log WHERE id = ?', [alert_id], one=True)
        if alert:
            user_id, details = alert
            # Parse channel and message
            channel = 'telegram' if 'channel=telegram' in details else 'discord' if 'channel=discord' in details else None
            msg_start = details.find('message=')
            message = details[msg_start+8:] if msg_start != -1 else details
            resend_alert(user_id, channel, message)
    return render_template_string('''
    <html><head><title>Alert Management</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Alert Management</h2>
    <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary mb-3">Back to Admin Dashboard</a>
    <form method="post" class="row g-2 mb-3">
        <div class="col-md-2"><input class="form-control" type="text" name="username" placeholder="Username" value="{{ request.form.get('username', '') }}"></div>
        <div class="col-md-2"><input class="form-control" type="text" name="coin" placeholder="Coin" value="{{ request.form.get('coin', '') }}"></div>
        <div class="col-md-2"><input class="form-control" type="text" name="alert_type" placeholder="Alert Type" value="{{ request.form.get('alert_type', '') }}"></div>
        <div class="col-md-2"><input class="form-control" type="text" name="channel" placeholder="Channel" value="{{ request.form.get('channel', '') }}"></div>
        <div class="col-md-2"><input class="form-control" type="date" name="date_from" value="{{ request.form.get('date_from', '') }}"></div>
        <div class="col-md-2"><input class="form-control" type="date" name="date_to" value="{{ request.form.get('date_to', '') }}"></div>
        <div class="col-md-2"><button class="btn btn-primary" type="submit">Filter</button></div>
    </form>
    <table class="table table-bordered table-striped">
        <thead><tr><th>User</th><th>Coin</th><th>Exchange</th><th>Type</th><th>Channel</th><th>Message</th><th>Time</th><th>Actions</th></tr></thead>
        <tbody>
        {% for a in alerts %}
        <tr>
            <td>{{ a[2] }}</td>
            <td>{{ a[3].split('coin=')[1].split(',')[0] if 'coin=' in a[3] else '' }}</td>
            <td>{{ a[3].split('exchange=')[1].split(',')[0] if 'exchange=' in a[3] else '' }}</td>
            <td>{{ a[3].split('type=')[1].split(',')[0] if 'type=' in a[3] else '' }}</td>
            <td>{{ a[3].split('channel=')[1].split(',')[0] if 'channel=' in a[3] else '' }}</td>
            <td>{{ a[3].split('message=')[1] if 'message=' in a[3] else a[3] }}</td>
            <td>{{ a[4] }}</td>
            <td>
                <form method="post" style="display:inline-block">
                    <input type="hidden" name="resend_id" value="{{ a[0] }}">
                    <button type="submit" class="btn btn-sm btn-info">Resend</button>
                </form>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    </body></html>
    ''', alerts=alerts)

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    trending = fetch_coingecko_trending()
    selected_coin = request.form.get('coin', trending[0])
    selected_exchange = request.form.get('exchange', 'all')
    show_trend = request.form.get('trend', 'off') == 'on'
    live = request.form.get('live', 'off') == 'on'
    alert_volume = request.form.get('alert_volume', type=float)
    alert_price = request.form.get('alert_price', type=float)
    detect_spikes = request.form.get('detect_spikes', 'off') == 'on'
    show_correlation = request.form.get('correlation', 'off') == 'on'
    coins = trending
    volumes = fetch_all_volumes(selected_coin.upper())
    price = fetch_price(selected_coin)
    hist = fetch_all_historical(selected_coin.upper()) if show_trend else None
    exchanges = ['binance', 'coinbase', 'kraken', 'kucoin', 'okx', 'bybit'] if selected_exchange == 'all' else [selected_exchange]
    bar = go.Bar(x=exchanges, y=[volumes[ex] if volumes[ex] else 0 for ex in exchanges])
    layout = go.Layout(title=f'{selected_coin.upper()} 24h Trading Volume', xaxis=dict(title='Exchange'), yaxis=dict(title='Volume'))
    fig = go.Figure(data=[bar], layout=layout)
    plot_div = pyo.plot(fig, output_type='div', include_plotlyjs=False)
    trend_div = ''
    spike_alerts = []
    correlation_results = {}
    
    # --- Error feedback for missing data ---
    failed_exchanges = [ex for ex in exchanges if volumes[ex] is None]
    if show_trend and hist:
        for ex in exchanges:
            vols = hist[ex]
            if not vols:
                failed_exchanges.append(ex)
    failed_exchanges = sorted(set(failed_exchanges))

    if show_trend and hist:
        for ex in exchanges:
            vols = hist[ex]
            if vols:
                trend_fig = go.Figure()
                trend_fig.add_trace(go.Scatter(x=list(range(len(vols))), y=vols, mode='lines+markers', name=f'{ex} volume'))
                if len(vols) >= 3:
                    ma = [sum(vols[max(0,i-2):i+1])/min(i+1,3) for i in range(len(vols))]
                    trend_fig.add_trace(go.Scatter(x=list(range(len(ma))), y=ma, mode='lines', name=f'{ex} 3-day MA'))
                trend_fig.update_layout(title=f'{selected_coin.upper()} 7-Day Volume Trend ({ex})', xaxis_title='Days Ago', yaxis_title='Volume')
                trend_div += pyo.plot(trend_fig, output_type='div', include_plotlyjs=False)
                
                # Spike detection
                if detect_spikes:
                    is_spike, ratio = detect_volume_spike(vols)
                    if is_spike:
                        spike_alerts.append(f'{ex}: Volume spike detected! Current volume is {ratio:.2f}x average')
                
                # Correlation analysis
                if show_correlation:
                    price_history = fetch_price_history(selected_coin)
                    if price_history and len(price_history) == len(vols):
                        correlation = calculate_price_volume_correlation(price_history, vols)
                        correlation_results[ex] = correlation
    
    alert_msgs = []
    for ex in exchanges:
        vol = volumes[ex]
        if alert_volume and vol and vol > alert_volume:
            alert_msgs.append(f'ALERT: {selected_coin.upper()} on {ex} volume {vol:,.2f} exceeds {alert_volume}')
        if alert_price and price and price > alert_price:
            alert_msgs.append(f'ALERT: {selected_coin.upper()} price {price:,.2f} exceeds {alert_price}')
    
    portfolio_results = None
    if request.method == 'POST' and 'portfolio' in request.files and request.files['portfolio'].filename:
        portfolio = parse_portfolio(request.files['portfolio'])
        total_value = 0
        total_volumes = {'binance': 0, 'coinbase': 0, 'kraken': 0, 'kucoin': 0, 'okx': 0, 'bybit': 0}
        details = []
        for entry in portfolio:
            coin = entry['coin']
            amount = entry['amount']
            symbol = coin.upper()
            p = fetch_price(coin)
            vols = fetch_all_volumes(symbol)
            value = p * amount if p else 0
            details.append({'coin': symbol, 'amount': amount, 'price': p, 'value': value})
            for ex in total_volumes:
                v = vols[ex]
                if v:
                    total_volumes[ex] += v * amount
            total_value += value
        portfolio_results = {'total_value': total_value, 'total_volumes': total_volumes, 'details': details}
        # --- Portfolio event notifications ---
        prev_portfolio = session.get('last_portfolio', {})
        prev_value = session.get('last_portfolio_value', 0)
        new_coins = set([d['coin'] for d in details]) - set(prev_portfolio.keys())
        for coin in new_coins:
            notify_portfolio_event(user_id, 'new_coin', f'New coin added to your portfolio: {coin}')
        if prev_value > 0:
            change = abs(total_value - prev_value) / prev_value
            if change > 0.1:
                direction = 'increased' if total_value > prev_value else 'decreased'
                notify_portfolio_event(user_id, 'value_change', f'Portfolio value {direction} by {change*100:.1f}% to ${total_value:,.2f}')
        # Store new portfolio state
        session['last_portfolio'] = {d['coin']: d['amount'] for d in details}
        session['last_portfolio_value'] = total_value
    
    # Trading bot state
    session_id = session.get('user_id', 'default')
    bot = bot_instances.get(session_id)
    bot_running = session.get('bot_running', False)
    bot_coin = session.get('bot_coin', '')
    bot_strategy = session.get('bot_strategy', 'all')
    bot_portfolio = bot.get_portfolio_value() if bot and bot_running else None
    bot_trades = bot.trade_history if bot and bot_running else []
    
    backtest_result = session.pop('backtest_result', None)
    backtest_coin = session.pop('backtest_coin', '')
    backtest_strategy = session.pop('backtest_strategy', 'volume_spike')
    backtest_days = session.pop('backtest_days', 30)

    # Load user favorites
    user_id = session.get('user_id')
    user_favorites = []
    if user_id:
        row = query_db('SELECT favorites FROM users WHERE id = ?', [user_id], one=True)
        if row and row[0]:
            user_favorites = row[0].split(',') if row[0] else []

    lang = session.get('lang', 'en')
    # News aggregation
    news_headlines = fetch_news(selected_coin)
    news_with_sentiment = [(headline, simple_sentiment(headline)) for headline in news_headlines]

    # Advanced analytics
    whale_alerts = fetch_whale_alerts(selected_coin)
    onchain_stats = fetch_onchain_stats(selected_coin)

    # Load user dashboard widget preferences
    user_id = session.get('user_id')
    row = query_db('SELECT dashboard_prefs FROM users WHERE id = ?', [user_id], one=True)
    widget_prefs = ['market_share', 'top_gainers', 'correlation', 'volatility'] # Default to all
    if row and row[0]:
        try:
            widget_prefs = row[0].split(',')
        except Exception:
            pass

    # Notification badge
    user_id = session.get('user_id')
    unread_count = 0
    if user_id:
        unread_count = query_db('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0', [user_id], one=True)[0]

    # Whale alert notifications
    user_favorites = []
    row = query_db('SELECT favorites, email FROM users WHERE id = ?', [user_id], one=True)
    if row and row[0]:
        user_favorites = row[0].split(',') if row[0] else []
        email = row[1]
        for coin in user_favorites:
            whale_alerts = fetch_whale_alerts(coin)
            last_whale_alerts = session.get(f'last_whale_{coin}', set())
            for alert in whale_alerts:
                alert_id = alert.get('txid')
                if alert_id and alert_id not in last_whale_alerts:
                    msg = f'Whale alert: {alert["amount"]} {coin.upper()} from {alert["from"]} to {alert["to"]} at {alert["timestamp"]}'
                    notify_major_alert_with_push(user_id, coin, 'whale', 'whale_alert', msg)
                    if email:
                        send_email_notification(email, f'Whale Alert for {coin.upper()}', msg)
            session[f'last_whale_{coin}'] = set([a.get('txid') for a in whale_alerts if a.get('txid')])

    # --- Technical indicator notifications ---
    if 'technical' in alert_types:
        for coin in user_favorites:
            # Example: RSI and MACD
            rsi = calculate_rsi(fetch_historical_prices(coin))
            macd, signal, hist_macd = calculate_macd(fetch_historical_prices(coin))
            if rsi and rsi > 70:
                msg = f'RSI for {coin.upper()} is overbought ({rsi:.1f})'
                notify_major_alert_with_push(user_id, coin, 'technical', 'rsi_overbought', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if rsi and rsi < 30:
                msg = f'RSI for {coin.upper()} is oversold ({rsi:.1f})'
                notify_major_alert_with_push(user_id, coin, 'technical', 'rsi_oversold', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if macd and signal and macd > signal:
                msg = f'MACD bullish crossover detected for {coin.upper()} (MACD: {macd:.2f}, Signal: {signal:.2f})'
                notify_major_alert_with_push(user_id, coin, 'technical', 'macd_bullish', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if macd and signal and macd < signal:
                msg = f'MACD bearish crossover detected for {coin.upper()} (MACD: {macd:.2f}, Signal: {signal:.2f})'
                notify_major_alert_with_push(user_id, coin, 'technical', 'macd_bearish', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)

    # --- Arbitrage opportunity notifications ---
    if 'arbitrage' in alert_types:
        for coin in user_favorites:
            arb = detect_arbitrage_opportunities(coin)
            if arb:
                msg = f'Arbitrage opportunity for {coin.upper()}: Buy on {arb["buy_exchange"]} at {arb["buy_price"]}, sell on {arb["sell_exchange"]} at {arb["sell_price"]} (spread: {arb["spread"]:.2f}%)'
                notify_major_alert_with_push(user_id, coin, 'arbitrage', 'arbitrage_opportunity', msg)
                if email:
                    send_email_notification(email, f'Arbitrage Alert for {coin.upper()}', msg)

    # --- News sentiment spike notifications ---
    if 'news' in alert_types:
        for coin in user_favorites:
            sentiment = fetch_social_sentiment(coin)
            if sentiment and abs(sentiment['change']) > 0.5:
                direction = 'positive' if sentiment['change'] > 0 else 'negative'
                msg = f'News sentiment spike for {coin.upper()}: {direction} ({sentiment["score"]:.2f}, change: {sentiment["change"]:+.2f})'
                notify_major_alert_with_push(user_id, coin, 'news', f'news_sentiment_{direction}', msg)
                if email:
                    send_email_notification(email, f'News Sentiment Alert for {coin.upper()}', msg)

    # --- Add dashboard_prefs column to users table if not present ---
    def add_dashboard_prefs_column():
        with app.app_context():
            db = get_db()
            try:
                db.execute('''CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    message TEXT,
                    link TEXT,
                    read INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                db.commit()
            except Exception:
                pass
    add_notifications_table()

    # --- Helper to create a notification ---
    def create_notification(user_id, ntype, message, link=None):
        db = get_db()
        db.execute('INSERT INTO notifications (user_id, type, message, link, read) VALUES (?, ?, ?, ?, 0)',
                   (user_id, ntype, message, link))
        db.commit()

    @app.route('/notifications', methods=['GET', 'POST'])
    @login_required
    def notifications():
        user_id = session.get('user_id')
        db = get_db()
        if request.method == 'POST':
            if 'mark_read' in request.form:
                db.execute('UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?', (request.form['mark_read'], user_id))
                db.commit()
            if 'clear_all' in request.form:
                db.execute('DELETE FROM notifications WHERE user_id = ?', (user_id,))
                db.commit()
        notes = query_db('SELECT id, type, message, link, read, timestamp FROM notifications WHERE user_id = ? ORDER BY timestamp DESC', [user_id])
        return render_template_string('''
        <html><head><title>Notifications</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        </head><body class="container py-5">
        <h2>Notifications</h2>
        <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">Back to Dashboard</a>
        <form method="post" class="mb-3">
            <button class="btn btn-danger" name="clear_all" value="1" type="submit">Clear All</button>
        </form>
        <table class="table table-bordered table-striped">
            <thead><tr><th>Type</th><th>Message</th><th>Link</th><th>Status</th><th>Time</th><th>Actions</th></tr></thead>
            <tbody>
            {% for n in notes %}
            <tr {% if not n[4] %}class="table-info"{% endif %}>
                <td>{{ n[1] }}</td>
                <td>{{ n[2] }}</td>
                <td>{% if n[3] %}<a href="{{ n[3] }}">View</a>{% endif %}</td>
                <td>{% if n[4] %}Read{% else %}Unread{% endif %}</td>
                <td>{{ n[5] }}</td>
                <td>
                    {% if not n[4] %}
                    <form method="post" style="display:inline-block">
                        <input type="hidden" name="mark_read" value="{{ n[0] }}">
                        <button class="btn btn-sm btn-success">Mark Read</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        </body></html>
        ''', notes=notes)

    # --- Add notification on admin feedback response ---
    # In admin_feedback, after responding, create_notification for the user
    # --- Add notification for changelog updates (demo: notify all users on /changelog load) ---
    # In changelog(), create_notification for all users if new entry
    # --- Show notification count in dashboard header ---
    # In index(), count unread notifications and pass to template

    @app.route('/admin/feedback', methods=['GET', 'POST'])
    @admin_required
    def admin_feedback():
        db = get_db()
        msg = None
        if request.method == 'POST':
            fid = request.form.get('fid')
            response = request.form.get('response', '').strip()
            action = request.form.get('action')
            if action == 'respond' and fid and response:
                db.execute('UPDATE feedback SET response = ?, status = ? WHERE id = ?', (response, 'resolved', fid))
                db.commit()
                # Notify user
                row = query_db('SELECT user_id FROM feedback WHERE id = ?', [fid], one=True)
                if row:
                    create_notification(row[0], 'feedback_response', f'Admin responded to your feedback: {response}', link=url_for('feedback'))
                msg = ('success', 'Response sent and marked as resolved.')
            elif action == 'resolve' and fid:
                db.execute('UPDATE feedback SET status = ? WHERE id = ?', ('resolved', fid))
                db.commit()
                # Notify user
                row = query_db('SELECT user_id FROM feedback WHERE id = ?', [fid], one=True)
                if row:
                    create_notification(row[0], 'feedback_resolved', 'Your feedback was marked as resolved.', link=url_for('feedback'))
                msg = ('success', 'Marked as resolved.')
        feedbacks = query_db('SELECT id, username, type, message, status, response, timestamp FROM feedback ORDER BY timestamp DESC LIMIT 50')
        return render_template_string('''
        <html><head><title>Admin Feedback</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        </head><body class="container py-5">
        <h2>Admin Feedback</h2>
        <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary mb-3">Back to Admin Dashboard</a>
        <div class="mb-4">
            <h4>Unresolved Feedback</h4>
            <table class="table table-bordered table-striped">
                <thead><tr><th>ID</th><th>User</th><th>Type</th><th>Message</th><th>Status</th><th>Response</th><th>Time</th><th>Actions</th></tr></thead>
                <tbody>
                {% for f in feedbacks %}
                <tr>
                    <td>{{ f[0] }}</td>
                    <td>{{ f[1] }}</td>
                    <td>{{ f[2] }}</td>
                    <td>{{ f[3] }}</td>
                    <td>{{ f[4] }}</td>
                    <td>{{ f[5] }}</td>
                    <td>{{ f[6] }}</td>
                    <td>
                        {% if f[4] == 'pending' %}
                        <form method="post" style="display:inline-block">
                            <input type="hidden" name="fid" value="{{ f[0] }}">
                            <input type="hidden" name="action" value="respond">
                            <button type="submit" class="btn btn-sm btn-primary">Respond</button>
                        </form>
                        <form method="post" style="display:inline-block">
                            <input type="hidden" name="fid" value="{{ f[0] }}">
                            <input type="hidden" name="action" value="resolve">
                            <button type="submit" class="btn btn-sm btn-success">Mark as Resolved</button>
                        </form>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        </body></html>
        ''', feedbacks=feedbacks, msg=msg)

    # --- In alert logic, create notification for major alert ---
    def notify_major_alert(user_id, coin, exchange, alert_type, message):
        create_notification(user_id, f'alert_{alert_type}', f'Alert for {coin} on {exchange}: {message}', link=url_for('index'))

    # In send_alerts or send_webhook_alert, call notify_major_alert for each user as appropriate
    # --- In portfolio logic, create notification for significant value change or new coin added ---
    def notify_portfolio_event(user_id, event_type, message):
        create_notification(user_id, f'portfolio_{event_type}', message, link=url_for('index'))

    # Expose notify_portfolio_event for import
    notify_portfolio_event = notify_portfolio_event

    def add_email_column():
        with app.app_context():
            db = get_db()
            try:
                db.execute('ALTER TABLE users ADD COLUMN email TEXT')
                db.commit()
            except Exception:
                pass
    add_email_column()

    # --- Email notification helper (real SMTP) ---
    # Required environment variables:
    #   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    def send_email_notification(email, subject, message):
        smtp_host = os.environ.get('SMTP_HOST')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        smtp_from = os.environ.get('SMTP_FROM', smtp_user)
        if not (smtp_host and smtp_port and smtp_user and smtp_password and smtp_from):
            print(f"[EMAIL] Missing SMTP config, not sending real email. To: {email} | Subject: {subject} | Message: {message}")
            return
        try:
            msg = MIMEText(message)
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [email], msg.as_string())
            print(f"[EMAIL] Sent to {email} | Subject: {subject}")
        except Exception as e:
            print(f"[EMAIL] Failed to send to {email}: {e}")

    def generate_daily_summary(user_id, email, user_favorites):
        # Gather summary data for user's favorite coins
        lines = []
        for coin in user_favorites:
            price = fetch_market_data(coin).get('price')
            volume = fetch_market_data(coin).get('volume')
            whale_alerts = fetch_whale_alerts(coin)
            sentiment = fetch_social_sentiment(coin)
            lines.append(f"{coin.upper()}: Price ${price}, 24h Vol {volume}, Whale txs: {len(whale_alerts)}, Sentiment: {sentiment.get('score') if sentiment else 'N/A'}")
        summary = '\n'.join(lines)
        notify_major_alert_with_push(user_id, None, 'summary', 'daily_summary', f"Daily summary for your portfolio:\n{summary}")
        if email:
            send_email_notification(email, "Your Daily Crypto Summary", summary)

    # --- Manual endpoint to trigger daily summary for all users (for demo/testing) ---
    @app.route('/admin/send_daily_summaries')
    @admin_required
    def send_daily_summaries():
        users = query_db('SELECT id, favorites, email, webhook_alert_types FROM users')
        count = 0
        for user_id, favorites, email, alert_types in users:
            if not alert_types or 'daily_summary' not in alert_types.split(','):
                continue
            user_favorites = favorites.split(',') if favorites else []
            if not user_favorites:
                continue
            generate_daily_summary(user_id, email, user_favorites)
            count += 1
        return f"Sent daily summaries to {count} users."

    # Add browser_notifications column to users table if not present
    def add_browser_notifications_column():
        with app.app_context():
            db = get_db()
            try:
                db.execute('ALTER TABLE users ADD COLUMN browser_notifications INTEGER DEFAULT 0')
                db.execute('ALTER TABLE users ADD COLUMN push_subscription TEXT')
                db.commit()
            except Exception:
                pass
    add_browser_notifications_column()

    # --- Endpoint to receive push subscription ---
    @app.route('/api/push_subscription', methods=['POST'])
    @login_required
    def save_push_subscription():
        user_id = session.get('user_id')
        sub = request.get_json()
        db = get_db()
        db.execute('UPDATE users SET push_subscription = ? WHERE id = ?', (json.dumps(sub), user_id))
        db.commit()
        return {'status': 'ok'}

    # --- Helper to send push notification ---
    def send_push_notification(user_id, title, message):
        from pywebpush import webpush, WebPushException
        row = query_db('SELECT push_subscription FROM users WHERE id = ?', [user_id], one=True)
        if not row or not row[0]:
            return
        sub = json.loads(row[0])
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({'title': title, 'body': message}),
                vapid_private_key=os.environ.get('VAPID_PRIVATE_KEY', 'test'),
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
        except WebPushException as ex:
            print(f"WebPush failed: {ex}")

    # --- When sending notifications, also send push if enabled ---
    def notify_major_alert_with_push(user_id, coin, category, event_type, message):
        notify_major_alert(user_id, coin, category, event_type, message)
        row = query_db('SELECT browser_notifications FROM users WHERE id = ?', [user_id], one=True)
        if row and row[0]:
            send_push_notification(user_id, f"{category.title()} Alert", message)

    # --- Helper: calculate correlation matrix for coins ---
    def calculate_correlation_matrix(coins):
        price_histories = []
        for coin in coins:
            prices = fetch_price_history(coin)
            if prices and len(prices) >= 7:
                price_histories.append(prices[-7:])
            else:
                price_histories.append([0]*7)
        arr = np.array(price_histories)
        if arr.shape[0] < 2:
            return None, coins
        corr = np.corrcoef(arr)
        return corr, coins

    # --- Helper: calculate volatility for coins ---
    def calculate_volatility(coins):
        volatilities = []
        for coin in coins:
            prices = fetch_price_history(coin)
            if prices and len(prices) >= 7:
                returns = np.diff(prices[-7:]) / np.array(prices[-7:-1])
                vol = np.std(returns)
            else:
                vol = 0
            volatilities.append((coin, vol))
        return volatilities

    # --- In index(), render new widgets if enabled ---
    dashboard_widgets_html = ''
    if 'market_share' in widget_prefs:
        # This part of the code was not provided in the original file,
        # so I'm adding a placeholder for the market share widget.
        # In a real application, you would fetch market share data here.
        dashboard_widgets_html += '<div class="alert alert-info">Market Share Widget Placeholder</div>'
    if 'top_gainers' in widget_prefs:
        # This part of the code was not provided in the original file,
        # so I'm adding a placeholder for the top gainers widget.
        # In a real application, you would fetch top gainers data here.
        dashboard_widgets_html += '<div class="alert alert-success">Top Gainers Widget Placeholder</div>'
    if 'correlation' in widget_prefs and user_favorites and len(user_favorites) > 1:
        try:
            corr, coins_corr = calculate_correlation_matrix(user_favorites)
            if corr is not None:
                import plotly.figure_factory as ff
                heatmap = ff.create_annotated_heatmap(z=corr, x=coins_corr, y=coins_corr, colorscale='Viridis')
                heatmap.update_layout(title='Correlation Matrix (7-day returns)')
                dashboard_widgets_html += heatmap.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception:
            dashboard_widgets_html += '<div class="alert alert-warning">Failed to load correlation matrix.</div>'
    if 'volatility' in widget_prefs and user_favorites:
        try:
            vols = calculate_volatility(user_favorites)
            import plotly.graph_objs as go
            coins_vol, values_vol = zip(*vols)
            bar = go.Figure([go.Bar(x=coins_vol, y=values_vol)])
            bar.update_layout(title='Volatility (Std Dev of 7-day Returns)', xaxis_title='Coin', yaxis_title='Volatility')
            dashboard_widgets_html += bar.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception:
            dashboard_widgets_html += '<div class="alert alert-warning">Failed to load volatility data.</div>'

    # --- Helper: get/set user target allocations ---
    def get_target_allocations(user_id):
        row = query_db('SELECT target_allocations FROM users WHERE id = ?', [user_id], one=True)
        if row and row[0]:
            try:
                return json.loads(row[0])
            except Exception:
                pass
        return {}

    def set_target_allocations(user_id, allocations):
        db = get_db()
        db.execute('UPDATE users SET target_allocations = ? WHERE id = ?', (json.dumps(allocations), user_id))
        db.commit()

    # --- Helper: store historical portfolio value ---
    def store_portfolio_value(user_id, value):
        db = get_db()
        db.execute('INSERT INTO portfolio_history (user_id, value, timestamp) VALUES (?, ?, ?)', (user_id, value, datetime.utcnow()))
        db.commit()

    def get_portfolio_history(user_id):
        rows = query_db('SELECT value, timestamp FROM portfolio_history WHERE user_id = ? ORDER BY timestamp', [user_id])
        return [(float(v), ts) for v, ts in rows]

    # --- Add columns/tables if not present ---
    def add_target_allocations_column():
        with app.app_context():
            db = get_db()
            try:
                db.execute('ALTER TABLE users ADD COLUMN target_allocations TEXT')
                db.commit()
            except Exception:
                pass
    add_target_allocations_column()

    def add_portfolio_history_table():
        with app.app_context():
            db = get_db()
            try:
                db.execute('''CREATE TABLE IF NOT EXISTS portfolio_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    value REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
                db.commit()
            except Exception:
                pass
    add_portfolio_history_table()

    # --- Portfolio Analytics Functions ---
    def calculate_portfolio_metrics(portfolio_data):
        """Calculate advanced portfolio risk and performance metrics"""
        if not portfolio_data:
            return {}
        
        # Extract price data and weights
        prices = {}
        weights = {}
        total_value = sum(item['value'] for item in portfolio_data)
        
        for item in portfolio_data:
            symbol = item['symbol']
            weights[symbol] = item['value'] / total_value
            # Get historical prices (last 30 days)
            try:
                hist_data = fetch_volume.fetch_coin_historical_data_async(symbol, days=30)
                if hist_data:
                    prices[symbol] = [float(day['price']) for day in hist_data]
            except:
                continue
        
        if len(prices) < 2:
            return {}
        
        # Calculate returns
        returns = {}
        for symbol, price_series in prices.items():
            if len(price_series) > 1:
                returns[symbol] = [(price_series[i] - price_series[i-1]) / price_series[i-1] 
                                 for i in range(1, len(price_series))]
        
        # Portfolio return series
        portfolio_returns = []
        min_length = min(len(ret) for ret in returns.values()) if returns else 0
        
        for i in range(min_length):
            daily_return = sum(returns[symbol][i] * weights[symbol] 
                              for symbol in returns.keys())
            portfolio_returns.append(daily_return)
        
        if len(portfolio_returns) < 2:
            return {}
        
        # Calculate metrics
        avg_return = np.mean(portfolio_returns)
        volatility = np.std(portfolio_returns)
        sharpe_ratio = avg_return / volatility if volatility > 0 else 0
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + np.array(portfolio_returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # VaR (Value at Risk) - 95% confidence
        var_95 = np.percentile(portfolio_returns, 5)
        
        # Beta calculation (vs BTC)
        try:
            btc_returns = returns.get('BTC', [])
            if len(btc_returns) >= len(portfolio_returns):
                btc_returns = btc_returns[:len(portfolio_returns)]
                beta = np.cov(portfolio_returns, btc_returns)[0,1] / np.var(btc_returns)
            else:
                beta = 1.0
        except:
            beta = 1.0
        
        return {
            'avg_return': avg_return * 100,  # Convert to percentage
            'volatility': volatility * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown * 100,
            'var_95': var_95 * 100,
            'beta': beta,
            'total_assets': len(portfolio_data),
            'concentration': max(weights.values()) * 100 if weights else 0
        }

    def optimize_portfolio(portfolio_data, target_return=None, risk_free_rate=0.02):
        """Optimize portfolio using Modern Portfolio Theory"""
        if not portfolio_data:
            return {}
        
        # Get historical data for all assets
        symbols = [item['symbol'] for item in portfolio_data]
        returns_data = {}
        
        for symbol in symbols:
            try:
                hist_data = fetch_volume.fetch_coin_historical_data_async(symbol, days=90)
                if hist_data:
                    prices = [float(day['price']) for day in hist_data]
                    returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                              for i in range(1, len(prices))]
                    returns_data[symbol] = returns
            except:
                continue
        
        if len(returns_data) < 2:
            return {}
        
        # Calculate expected returns and covariance matrix
        expected_returns = {symbol: np.mean(returns) for symbol, returns in returns_data.items()}
        symbols_list = list(returns_data.keys())
        
        # Create covariance matrix
        min_length = min(len(returns) for returns in returns_data.values())
        returns_matrix = np.array([returns_data[symbol][:min_length] for symbol in symbols_list])
        cov_matrix = np.cov(returns_matrix)
        
        # Portfolio optimization
        n_assets = len(symbols_list)
        
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        def portfolio_return(weights):
            return np.sum([expected_returns[symbol] * weights[i] 
                          for i, symbol in enumerate(symbols_list)])
        
        def objective(weights):
            return portfolio_volatility(weights)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # weights sum to 1
        ]
        
        if target_return is not None:
            constraints.append({
                'type': 'eq', 
                'fun': lambda x: portfolio_return(x) - target_return
            })
        
        # Bounds: no short selling
        bounds = tuple((0, 1) for _ in range(n_assets))
        
        # Initial guess: equal weights
        initial_weights = np.array([1/n_assets] * n_assets)
        
        try:
            result = minimize(objective, initial_weights, 
                             method='SLSQP', bounds=bounds, constraints=constraints)
            
            if result.success:
                optimal_weights = result.x
                optimal_volatility = portfolio_volatility(optimal_weights)
                optimal_return = portfolio_return(optimal_weights)
                
                return {
                    'optimal_weights': dict(zip(symbols_list, optimal_weights)),
                    'optimal_volatility': optimal_volatility * 100,
                    'optimal_return': optimal_return * 100,
                    'sharpe_ratio': (optimal_return - risk_free_rate) / optimal_volatility
                }
        except:
            pass
        
        return {}

    # --- In index(), after portfolio processing ---
    # Store historical portfolio value
    if portfolio_results:
        store_portfolio_value(user_id, portfolio_results['total_value'])
    # Get portfolio history
    portfolio_history = get_portfolio_history(user_id)
    # Get target allocations
    target_allocs = get_target_allocations(user_id)
    # --- Portfolio Allocation Widget ---
    if 'portfolio_allocation' in widget_prefs and portfolio_results:
        try:
            import plotly.graph_objs as go
            coins = [d['coin'] for d in portfolio_results['details']]
            values = [d['value'] for d in portfolio_results['details']]
            pie = go.Figure(data=[go.Pie(labels=coins, values=values)])
            pie.update_layout(title='Portfolio Allocation by Coin')
            dashboard_widgets_html += pie.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception:
            dashboard_widgets_html += '<div class="alert alert-warning">Failed to load portfolio allocation.</div>'
    # --- Portfolio Performance Widget ---
    if 'portfolio_performance' in widget_prefs and portfolio_history:
        try:
            import plotly.graph_objs as go
            values, timestamps = zip(*portfolio_history)
            line = go.Figure([go.Scatter(x=list(timestamps), y=list(values), mode='lines+markers')])
            line.update_layout(title='Portfolio Value Over Time', xaxis_title='Time', yaxis_title='Value (USD)')
            dashboard_widgets_html += line.to_html(full_html=False, include_plotlyjs='cdn')
        except Exception:
            dashboard_widgets_html += '<div class="alert alert-warning">Failed to load portfolio performance.</div>'
    # --- Rebalancing Check (Demo) ---
    if target_allocs and portfolio_results:
        total = sum([d['value'] for d in portfolio_results['details']])
        for d in portfolio_results['details']:
            coin = d['coin']
            actual_pct = d['value'] / total if total else 0
            target_pct = target_allocs.get(coin, 0)
            if abs(actual_pct - target_pct) > 0.05:
                notify_major_alert_with_push(user_id, coin, 'portfolio', 'rebalance_needed', f'Rebalancing needed for {coin}: actual {actual_pct*100:.1f}%, target {target_pct*100:.1f}%')
    # --- UI for setting target allocations ---
    @app.route('/set_target_allocations', methods=['GET', 'POST'])
    @login_required
    def set_target_allocations_route():
        user_id = session.get('user_id')
        coins = [d['coin'] for d in get_portfolio_history(user_id)]
        current = get_target_allocations(user_id)
        if request.method == 'POST':
            allocs = {k: float(v) for k, v in request.form.items() if v}
            set_target_allocations(user_id, allocs)
            return redirect(url_for('index'))
        return render_template_string('''
        <html><head><title>Set Target Allocations</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        </head><body class="container py-5">
        <h2>Set Target Portfolio Allocations</h2>
        <form method="post">
            {% for coin in coins %}
            <div class="mb-3">
                <label class="form-label">{{ coin }} Target %:</label>
                <input class="form-control" type="number" step="0.01" name="{{ coin }}" value="{{ current.get(coin, 0)*100 }}">
            </div>
            {% endfor %}
            <button class="btn btn-primary" type="submit">Save</button>
        </form>
        <div class="mt-3"><a href="{{ url_for('index') }}">Back to Dashboard</a></div>
        </body></html>
        ''', coins=coins, current=current)

    @app.route('/portfolio_analytics')
    @login_required
    def portfolio_analytics():
        user_id = session['user_id']
        
        # Get current portfolio
        portfolio_data = get_user_portfolio(user_id)
        
        # Calculate metrics
        metrics = calculate_portfolio_metrics(portfolio_data)
        
        # Portfolio optimization
        optimization = optimize_portfolio(portfolio_data)
        
        # Performance attribution
        attribution = {}
        if portfolio_data:
            total_value = sum(item['value'] for item in portfolio_data)
            for item in portfolio_data:
                symbol = item['symbol']
                weight = item['value'] / total_value
                try:
                    # Get 24h change
                    current_data = fetch_volume.fetch_coin_data_async(symbol)
                    if current_data:
                        price_change_24h = current_data.get('price_change_percentage_24h', 0)
                        contribution = weight * price_change_24h
                        attribution[symbol] = {
                            'weight': weight * 100,
                            'return_24h': price_change_24h,
                            'contribution': contribution
                        }
                except:
                    continue
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Portfolio Analytics - Crypto Trading Volume</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        </head>
        <body>
            <div class="container mt-4">
                <h1>Portfolio Analytics</h1>
                <a href="/" class="btn btn-secondary mb-3">← Back to Dashboard</a>
                
                {% if metrics %}
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Risk Metrics</h5>
                            </div>
                            <div class="card-body">
                                <table class="table">
                                    <tr><td>Average Return (Daily)</td><td>{{ "%.2f"|format(metrics.avg_return) }}%</td></tr>
                                    <tr><td>Volatility</td><td>{{ "%.2f"|format(metrics.volatility) }}%</td></tr>
                                    <tr><td>Sharpe Ratio</td><td>{{ "%.2f"|format(metrics.sharpe_ratio) }}</td></tr>
                                    <tr><td>Maximum Drawdown</td><td>{{ "%.2f"|format(metrics.max_drawdown) }}%</td></tr>
                                    <tr><td>VaR (95%)</td><td>{{ "%.2f"|format(metrics.var_95) }}%</td></tr>
                                    <tr><td>Beta (vs BTC)</td><td>{{ "%.2f"|format(metrics.beta) }}</td></tr>
                                    <tr><td>Concentration</td><td>{{ "%.2f"|format(metrics.concentration) }}%</td></tr>
                                </table>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Portfolio Optimization</h5>
                            </div>
                            <div class="card-body">
                                {% if optimization %}
                                <p><strong>Optimal Portfolio:</strong></p>
                                <table class="table table-sm">
                                    {% for symbol, weight in optimization.optimal_weights.items() %}
                                    <tr><td>{{ symbol }}</td><td>{{ "%.1f"|format(weight * 100) }}%</td></tr>
                                    {% endfor %}
                                </table>
                                <p><strong>Expected Return:</strong> {{ "%.2f"|format(optimization.optimal_return) }}%</p>
                                <p><strong>Expected Volatility:</strong> {{ "%.2f"|format(optimization.optimal_volatility) }}%</p>
                                <p><strong>Sharpe Ratio:</strong> {{ "%.2f"|format(optimization.sharpe_ratio) }}</p>
                                {% else %}
                                <p class="text-muted">Insufficient data for optimization</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
                
                {% if attribution %}
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5>Performance Attribution (24h)</h5>
                            </div>
                            <div class="card-body">
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Asset</th>
                                            <th>Weight</th>
                                            <th>24h Return</th>
                                            <th>Contribution</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for symbol, data in attribution.items() %}
                                        <tr>
                                            <td>{{ symbol }}</td>
                                            <td>{{ "%.1f"|format(data.weight) }}%</td>
                                            <td class="{{ 'text-success' if data.return_24h > 0 else 'text-danger' }}">
                                                {{ "%.2f"|format(data.return_24h) }}%
                                            </td>
                                            <td class="{{ 'text-success' if data.contribution > 0 else 'text-danger' }}">
                                                {{ "%.2f"|format(data.contribution) }}%
                                            </td>
                                        </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                {% endif %}
                
                {% else %}
                <div class="alert alert-info">
                    No portfolio data available. Add some assets to your portfolio to see analytics.
                </div>
                {% endif %}
            </div>
        </body>
        </html>
        ''', metrics=metrics, optimization=optimization, attribution=attribution)

    @app.route('/analytics')
    @login_required
    def analytics_dashboard():
        """Enhanced analytics dashboard with real-time charts and advanced metrics"""
        user_id = session['user_id']
        user = query_db('SELECT username, favorites FROM users WHERE id = ?', [user_id], one=True)
        
        if not user:
            return redirect(url_for('login'))
        
        username, favorites = user
        favorite_coins = favorites.split(',') if favorites else []
        
        # Get market overview data
        try:
            from fetch_volume import fetch_market_dominance
            market_dominance = fetch_market_dominance()
        except:
            market_dominance = {}
        
        # Get trending coins for comparison
        try:
            trending = fetch_coingecko_trending()
        except:
            trending = []
        
        # Prepare chart data for favorite coins
        chart_data = {}
        for coin in favorite_coins[:5]:  # Limit to 5 coins for performance
            try:
                symbol = coin.upper()
                volumes = fetch_all_volumes(symbol)
                historical = fetch_all_historical(symbol, days=7)
                
                if volumes and historical:
                    chart_data[symbol] = {
                        'volumes': volumes,
                        'historical': historical,
                        'price_data': fetch_price_history(symbol, days=7)
                    }
            except Exception as e:
                print(f"Error fetching data for {coin}: {e}")
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analytics Dashboard - Crypto Volume Tracker</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1400px; margin: 0 auto; }
                .header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .metric-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .metric-value { font-size: 2em; font-weight: bold; color: #2c3e50; }
                .metric-label { color: #7f8c8d; margin-top: 5px; }
                .chart-container { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .chart-title { font-size: 1.5em; margin-bottom: 20px; color: #2c3e50; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Analytics Dashboard</h1>
                    <p>Welcome back, {{ username }}! Here's your comprehensive market analysis.</p>
                </div>
                
                <!-- Market Overview Metrics -->
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{{ market_dominance.get('bitcoin', 0) | round(2) }}%</div>
                        <div class="metric-label">Bitcoin Dominance</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ market_dominance.get('ethereum', 0) | round(2) }}%</div>
                        <div class="metric-label">Ethereum Dominance</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ trending | length }}</div>
                        <div class="metric-label">Trending Coins</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ favorite_coins | length }}</div>
                        <div class="metric-label">Your Watchlist</div>
                    </div>
                </div>
                
                <!-- Volume Chart -->
                <div class="chart-container">
                    <div class="chart-title">24h Trading Volume by Exchange</div>
                    <div id="volume-chart"></div>
                </div>
                
                <!-- Trend Chart -->
                <div class="chart-container">
                    <div class="chart-title">7-Day Volume Trends</div>
                    <div id="trend-chart"></div>
                </div>
            </div>
            
            <script>
                const chartData = {{ chart_data | tojson }};
                
                if (Object.keys(chartData).length > 0) {
                    const coins = Object.keys(chartData);
                    const exchanges = ['binance', 'coinbase', 'kraken', 'kucoin', 'okx', 'bybit'];
                    
                    const volumeData = exchanges.map(exchange => ({
                        x: coins,
                        y: coins.map(coin => chartData[coin]?.volumes?.[exchange] || 0),
                        name: exchange.charAt(0).toUpperCase() + exchange.slice(1),
                        type: 'bar'
                    }));
                    
                    Plotly.newPlot('volume-chart', volumeData, {
                        title: '24h Trading Volume by Exchange',
                        barmode: 'group',
                        xaxis: { title: 'Cryptocurrency' },
                        yaxis: { title: 'Volume (USD)' }
                    });
                    
                    const trendData = coins.map(coin => ({
                        x: Array.from({length: 7}, (_, i) => `Day ${i+1}`),
                        y: chartData[coin]?.historical?.binance || [],
                        name: coin,
                        type: 'scatter',
                        mode: 'lines+markers'
                    }));
                    
                    Plotly.newPlot('trend-chart', trendData, {
                        title: '7-Day Volume Trends',
                        xaxis: { title: 'Day' },
                        yaxis: { title: 'Volume (USD)' }
                    });
                }
                
                // Auto-refresh every 30 seconds
                setInterval(() => {
                    location.reload();
                }, 30000);
            </script>
        </body>
        </html>
        ''', username=username, chart_data=chart_data, market_dominance=market_dominance, 
             trending=trending, favorite_coins=favorite_coins)

@app.route('/sentiment')
@login_required
def sentiment_dashboard():
    """Real-time market sentiment analysis dashboard"""
    user_id = session['user_id']
    user = query_db('SELECT username, favorites FROM users WHERE id = ?', [user_id], one=True)
    
    if not user:
        return redirect(url_for('login'))
    
    username, favorites = user
    favorite_coins = favorites.split(',') if favorites else []
    
    # Get sentiment analysis for favorite coins
    sentiment_data = {}
    for coin in favorite_coins[:5]:  # Limit to 5 coins for performance
        try:
            from fetch_volume import fetch_market_sentiment_analysis
            sentiment = fetch_market_sentiment_analysis(coin)
            if sentiment:
                sentiment_data[coin.upper()] = sentiment
        except Exception as e:
            print(f"Error fetching sentiment for {coin}: {e}")
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Market Sentiment Analysis - Crypto Volume Tracker</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .sentiment-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .sentiment-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .sentiment-score { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
            .sentiment-bullish { color: #27ae60; }
            .sentiment-bearish { color: #e74c3c; }
            .sentiment-neutral { color: #7f8c8d; }
            .component-bar { background: #ecf0f1; height: 8px; border-radius: 4px; margin: 5px 0; }
            .component-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
            .component-fill-positive { background: #27ae60; }
            .component-fill-negative { background: #e74c3c; }
            .component-fill-neutral { background: #7f8c8d; }
            .chart-container { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .chart-title { font-size: 1.5em; margin-bottom: 20px; color: #2c3e50; }
            .nav-links { margin-bottom: 20px; }
            .nav-links a { display: inline-block; margin-right: 15px; padding: 8px 16px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }
            .nav-links a:hover { background: #2980b9; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Market Sentiment Analysis</h1>
                <p>Welcome back, {{ username }}! Real-time sentiment analysis for your favorite coins.</p>
                <div class="nav-links">
                    <a href="/">← Main Dashboard</a>
                    <a href="/analytics">📈 Analytics</a>
                    <a href="/settings">⚙️ Settings</a>
                </div>
            </div>
            
            <!-- Sentiment Cards -->
            <div class="sentiment-grid">
                {% for coin, sentiment in sentiment_data.items() %}
                <div class="sentiment-card">
                    <h3>{{ coin }}</h3>
                    <div class="sentiment-score sentiment-{{ sentiment.overall_sentiment }}">
                        {% if sentiment.composite_score > 0 %}
                            +{{ "%.2f"|format(sentiment.composite_score) }}
                        {% else %}
                            {{ "%.2f"|format(sentiment.composite_score) }}
                        {% endif %}
                    </div>
                    <p><strong>Overall Sentiment:</strong> 
                        <span class="sentiment-{{ sentiment.overall_sentiment }}">
                            {{ sentiment.overall_sentiment.upper() }}
                        </span>
                    </p>
                    
                    <h4>Sentiment Components:</h4>
                    <div>
                        <div>News Sentiment: {{ "%.2f"|format(sentiment.components.news_sentiment) }}</div>
                        <div class="component-bar">
                            <div class="component-fill {% if sentiment.components.news_sentiment > 0 %}component-fill-positive{% elif sentiment.components.news_sentiment < 0 %}component-fill-negative{% else %}component-fill-neutral{% endif %}" 
                                 style="width: {{ (sentiment.components.news_sentiment + 1) * 50 }}%"></div>
                        </div>
                    </div>
                    
                    <div>
                        <div>RSI Sentiment: {{ "%.2f"|format(sentiment.components.rsi_sentiment) }}</div>
                        <div class="component-bar">
                            <div class="component-fill {% if sentiment.components.rsi_sentiment > 0 %}component-fill-positive{% elif sentiment.components.rsi_sentiment < 0 %}component-fill-negative{% else %}component-fill-neutral{% endif %}" 
                                 style="width: {{ (sentiment.components.rsi_sentiment + 1) * 50 }}%"></div>
                        </div>
                    </div>
                    
                    <div>
                        <div>MACD Sentiment: {{ "%.2f"|format(sentiment.components.macd_sentiment) }}</div>
                        <div class="component-bar">
                            <div class="component-fill {% if sentiment.components.macd_sentiment > 0 %}component-fill-positive{% elif sentiment.components.macd_sentiment < 0 %}component-fill-negative{% else %}component-fill-neutral{% endif %}" 
                                 style="width: {{ (sentiment.components.macd_sentiment + 1) * 50 }}%"></div>
                        </div>
                    </div>
                    
                    <div>
                        <div>Volume Sentiment: {{ "%.2f"|format(sentiment.components.volume_sentiment) }}</div>
                        <div class="component-bar">
                            <div class="component-fill {% if sentiment.components.volume_sentiment > 0 %}component-fill-positive{% elif sentiment.components.volume_sentiment < 0 %}component-fill-negative{% else %}component-fill-neutral{% endif %}" 
                                 style="width: {{ (sentiment.components.volume_sentiment + 1) * 50 }}%"></div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px; font-size: 0.9em; color: #7f8c8d;">
                        <strong>News Breakdown:</strong><br>
                        Positive: {{ sentiment.news_breakdown.positive }} | 
                        Negative: {{ sentiment.news_breakdown.negative }} | 
                        Neutral: {{ sentiment.news_breakdown.neutral }}
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <!-- Sentiment Comparison Chart -->
            {% if sentiment_data %}
            <div class="chart-container">
                <div class="chart-title">Sentiment Comparison Across Coins</div>
                <div id="sentiment-chart"></div>
            </div>
            {% endif %}
        </div>
        
        <script>
            const sentimentData = {{ sentiment_data | tojson }};
            
            if (Object.keys(sentimentData).length > 0) {
                const coins = Object.keys(sentimentData);
                const scores = coins.map(coin => sentimentData[coin].composite_score);
                const colors = scores.map(score => 
                    score > 0.3 ? '#27ae60' : score < -0.3 ? '#e74c3c' : '#7f8c8d'
                );
                
                const trace = {
                    x: coins,
                    y: scores,
                    type: 'bar',
                    marker: {
                        color: colors
                    },
                    text: scores.map(score => score > 0 ? '+' + score.toFixed(2) : score.toFixed(2)),
                    textposition: 'auto'
                };
                
                const layout = {
                    title: 'Composite Sentiment Scores',
                    xaxis: { title: 'Cryptocurrency' },
                    yaxis: { 
                        title: 'Sentiment Score',
                        range: [-1, 1]
                    },
                    shapes: [
                        {
                            type: 'line',
                            x0: -0.5,
                            x1: coins.length - 0.5,
                            y0: 0.3,
                            y1: 0.3,
                            line: { color: '#27ae60', dash: 'dash' }
                        },
                        {
                            type: 'line',
                            x0: -0.5,
                            x1: coins.length - 0.5,
                            y0: -0.3,
                            y1: -0.3,
                            line: { color: '#e74c3c', dash: 'dash' }
                        }
                    ]
                };
                
                Plotly.newPlot('sentiment-chart', [trace], layout);
            }
            
            // Auto-refresh every 60 seconds
            setInterval(() => {
                location.reload();
            }, 60000);
        </script>
    </body>
    </html>
         ''', username=username, sentiment_data=sentiment_data)

@app.route('/api/sentiment/<coin>')
def api_sentiment(coin):
    """API endpoint for sentiment analysis"""
    try:
        from fetch_volume import fetch_market_sentiment_analysis
        sentiment = fetch_market_sentiment_analysis(coin)
        if sentiment:
            return jsonify(sentiment)
        else:
            return jsonify({'error': 'Could not analyze sentiment'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sentiment/batch', methods=['POST'])
def api_sentiment_batch():
    """API endpoint for batch sentiment analysis"""
    try:
        data = request.get_json()
        coins = data.get('coins', [])
        if not coins:
            return jsonify({'error': 'No coins provided'}), 400
        
        results = {}
        from fetch_volume import fetch_market_sentiment_analysis
        
        for coin in coins[:10]:  # Limit to 10 coins
            sentiment = fetch_market_sentiment_analysis(coin)
            if sentiment:
                results[coin.upper()] = sentiment
        
        return jsonify({
            'results': results,
            'total_analyzed': len(results),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/changelog')
@login_required
def changelog():
    # In a real application, this would load a changelog.txt or similar file
    # For now, it's a placeholder that creates a new entry if it doesn't exist
    user_id = session.get('user_id')
    if user_id:
        # Check if changelog.txt exists and has content
        changelog_file = 'changelog.txt'
        if not os.path.exists(changelog_file):
            with open(changelog_file, 'w') as f:
                f.write("=== Crypto Trading Volume Changelog ===\n\n")
                f.write("Version 1.0 (Initial Release)\n")
                f.write("* Basic dashboard with volume trends\n")
                f.write("* Favorite coins management\n")
                f.write("* Trading bot (demo mode)\n")
                f.write("* Backtesting functionality\n")
                f.write("* News aggregation and sentiment\n")
                f.write("* Whale alerts (mocked)\n")
                f.write("* On-chain stats (mocked)\n")
                f.write("* Alert settings\n")
                f.write("* User authentication\n")
                f.write("* Admin dashboard\n")
                f.write("* Push notifications (demo)\n")
                f.write("* Email notifications (demo)\n")
                f.write("* Daily summary emails (demo)\n")
                f.write("* Widget customization\n")
                f.write("* Language selection\n")
                f.write("* User profile management\n")
                f.write("* Feedback system\n")
                f.write("* Cache (Redis - demo)\n")
                f.write("* Event logging\n")
                f.write("* Technical indicators (RSI, MACD - demo)\n")
                f.write("* Arbitrage detection (demo)\n")
                f.write("* Social sentiment (demo)\n")
                f.write("* Correlation matrix (demo)\n")
                f.write("* Volatility heatmap (demo)\n")
                f.write("* Portfolio tracking\n")
                f.write("* Webhook alerts\n")
                f.write("* Browser notifications (demo)\n")
                f.write("* Push subscription handling\n")
                f.write("* File upload for portfolio\n")
                f.write("* Date filtering in admin logs\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* Password reset for deactivated users\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
                f.write("* News sentiment spike detection (demo)\n")
                f.write("* Arbitrage opportunity detection (demo)\n")
                f.write("* Technical indicator notifications (demo)\n")
                f.write("* Whale alert persistence\n")
                f.write("* On-chain stats persistence\n")
                f.write("* User deactivation/reactivation\n")
                f.write("* User password reset\n")
                f.write("* Admin feedback system\n")
                f.write("* Admin dashboard with audit logs\n")
                f.write("* API usage stats\n")
                f.write("* Error logging\n")
                f.write("* Alert event logging\n")
                f.write("* Webhook test functionality\n")
                f.write("* Daily summary emails for all users (demo)\n")
                f.write("* Push subscription endpoint\n")
                f.write("* Browser notification service worker\n")
                f.write("* User dashboard preferences\n")
                f.write("* Market share widget (placeholder)\n")
                f.write("* Top gainers widget (placeholder)\n")
                f.write("* Correlation matrix widget (demo)\n")
                f.write("* Volatility heatmap widget (demo)\n")
                f.write("* User favorites persistence\n")
@app.route('/ml-predictions')
@login_required
def ml_predictions_dashboard():
    """Machine Learning Predictions Dashboard"""
    try:
        from ml_predictions import CryptoPricePredictor
        
        predictor = CryptoPricePredictor()
        predictions = {}
        
        # Get user's favorite coins
        user_favorites = query_db('SELECT favorites FROM users WHERE id = ?', [session['user_id']], one=True)
        if user_favorites and user_favorites[0]:
            favorites = json.loads(user_favorites[0])
            
            for coin in favorites[:5]:  # Limit to 5 coins
                try:
                    # Try to load existing models
                    if predictor.load_models(coin):
                        prediction = predictor.predict_price(coin)
                        if prediction:
                            confidence = predictor.get_prediction_confidence(coin)
                            predictions[coin] = {
                                'current_price': prediction['current_price'],
                                'predicted_price': prediction['predicted_price'],
                                'predicted_change': prediction['predicted_change'],
                                'confidence': confidence,
                                'individual_predictions': prediction['individual_predictions']
                            }
                except Exception as e:
                    print(f"Error predicting {coin}: {e}")
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>ML Predictions Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                .prediction-card { border-left: 4px solid #007bff; }
                .prediction-positive { border-left-color: #28a745; }
                .prediction-negative { border-left-color: #dc3545; }
                .confidence-high { color: #28a745; }
                .confidence-medium { color: #ffc107; }
                .confidence-low { color: #dc3545; }
            </style>
        </head>
        <body>
            <div class="container-fluid mt-4">
                <div class="row">
                    <div class="col-12">
                        <h2><i class="fas fa-brain"></i> Machine Learning Predictions</h2>
                        <p class="text-muted">AI-powered price predictions using ensemble machine learning models</p>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5>Price Predictions</h5>
                            </div>
                            <div class="card-body">
                                {% if predictions %}
                                    <div class="row">
                                        {% for coin, pred in predictions.items() %}
                                        <div class="col-md-6 col-lg-4 mb-3">
                                            <div class="card prediction-card {% if pred.predicted_change > 0 %}prediction-positive{% else %}prediction-negative{% endif %}">
                                                <div class="card-body">
                                                    <h6 class="card-title">{{ coin.upper() }}</h6>
                                                    <div class="row">
                                                        <div class="col-6">
                                                            <small class="text-muted">Current Price</small>
                                                            <div class="h6">${{ "{:,.2f}".format(pred.current_price) }}</div>
                                                        </div>
                                                        <div class="col-6">
                                                            <small class="text-muted">Predicted Price</small>
                                                            <div class="h6">${{ "{:,.2f}".format(pred.predicted_price) }}</div>
                                                        </div>
                                                    </div>
                                                    <div class="mt-2">
                                                        <span class="badge {% if pred.predicted_change > 0 %}bg-success{% else %}bg-danger{% endif %}">
                                                            {{ "{:+.2%}".format(pred.predicted_change) }}
                                                        </span>
                                                        <small class="ms-2 confidence-{% if pred.confidence > 0.7 %}high{% elif pred.confidence > 0.4 %}medium{% else %}low{% endif %}">
                                                            Confidence: {{ "{:.1%}".format(pred.confidence) }}
                                                        </small>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <div class="text-center text-muted">
                                        <p>No predictions available. Add coins to your favorites to see ML predictions.</p>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5>Model Performance</h5>
                            </div>
                            <div class="card-body">
                                <p class="text-muted">Our ensemble model combines Random Forest, Gradient Boosting, and Linear Regression for optimal predictions.</p>
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="text-center">
                                            <h4 class="text-primary">Random Forest</h4>
                                            <p>Handles non-linear relationships and feature interactions</p>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="text-center">
                                            <h4 class="text-success">Gradient Boosting</h4>
                                            <p>Sequential learning for improved prediction accuracy</p>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="text-center">
                                            <h4 class="text-info">Linear Regression</h4>
                                            <p>Captures linear trends and provides interpretable results</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                // Auto-refresh every 5 minutes
                setTimeout(function() {
                    location.reload();
                }, 300000);
            </script>
        </body>
        </html>
        ''', predictions=predictions)
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/advanced-backtest')
@login_required
def advanced_backtest_dashboard():
    """Advanced Backtesting Dashboard"""
    try:
        from advanced_backtest import AdvancedBacktester
        
        backtester = AdvancedBacktester()
        
        # Get user's favorite coins
        user_favorites = query_db('SELECT favorites FROM users WHERE id = ?', [session['user_id']], one=True)
        favorites = []
        if user_favorites and user_favorites[0]:
            favorites = json.loads(user_favorites[0])
        
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Advanced Backtesting</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        </head>
        <body>
            <div class="container-fluid mt-4">
                <div class="row">
                    <div class="col-12">
                        <h2><i class="fas fa-chart-line"></i> Advanced Backtesting</h2>
                        <p class="text-muted">Test trading strategies with historical data and machine learning</p>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Run Backtest</h5>
                            </div>
                            <div class="card-body">
                                <form id="backtestForm">
                                    <div class="mb-3">
                                        <label for="coin" class="form-label">Coin</label>
                                        <select class="form-select" id="coin" name="coin" required>
                                            <option value="">Select a coin</option>
                                            {% for coin in favorites %}
                                            <option value="{{ coin }}">{{ coin.upper() }}</option>
                                            {% endfor %}
                                            <option value="bitcoin">Bitcoin</option>
                                            <option value="ethereum">Ethereum</option>
                                            <option value="cardano">Cardano</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label for="days" class="form-label">Days to Backtest</label>
                                        <select class="form-select" id="days" name="days">
                                            <option value="30">30 days</option>
                                            <option value="60">60 days</option>
                                            <option value="90" selected>90 days</option>
                                            <option value="180">180 days</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Strategies to Test</label>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="rsi" name="strategies" value="rsi" checked>
                                            <label class="form-check-label" for="rsi">RSI Strategy</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="macd" name="strategies" value="macd" checked>
                                            <label class="form-check-label" for="macd">MACD Strategy</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="volume" name="strategies" value="volume" checked>
                                            <label class="form-check-label" for="volume">Volume Spike Strategy</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="ma" name="strategies" value="ma" checked>
                                            <label class="form-check-label" for="ma">Moving Average Strategy</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="ml" name="strategies" value="ml" checked>
                                            <label class="form-check-label" for="ml">Machine Learning Strategy</label>
                                        </div>
                                    </div>
                                    <button type="submit" class="btn btn-primary">Run Backtest</button>
                                </form>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Strategy Descriptions</h5>
                            </div>
                            <div class="card-body">
                                <div class="mb-3">
                                    <h6>RSI Strategy</h6>
                                    <p class="text-muted">Buy when RSI < 30 (oversold), sell when RSI > 70 (overbought)</p>
                                </div>
                                <div class="mb-3">
                                    <h6>MACD Strategy</h6>
                                    <p class="text-muted">Buy on bullish crossover, sell on bearish crossover</p>
                                </div>
                                <div class="mb-3">
                                    <h6>Volume Spike Strategy</h6>
                                    <p class="text-muted">Buy when volume is 2x above average</p>
                                </div>
                                <div class="mb-3">
                                    <h6>Moving Average Strategy</h6>
                                    <p class="text-muted">Buy on golden cross (5MA > 20MA), sell on death cross</p>
                                </div>
                                <div class="mb-3">
                                    <h6>Machine Learning Strategy</h6>
                                    <p class="text-muted">Uses ensemble of ML models for price direction prediction</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-12">
                        <div id="backtestResults" style="display: none;">
                            <div class="card">
                                <div class="card-header">
                                    <h5>Backtest Results</h5>
                                </div>
                                <div class="card-body">
                                    <div id="resultsContent"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                document.getElementById('backtestForm').addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const formData = new FormData(e.target);
                    const data = {
                        coin: formData.get('coin'),
                        days: parseInt(formData.get('days')),
                        strategies: Array.from(formData.getAll('strategies'))
                    };
                    
                    // Show loading
                    document.getElementById('backtestResults').style.display = 'block';
                    document.getElementById('resultsContent').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Running backtest...</p></div>';
                    
                    fetch('/api/run-backtest', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data)
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            document.getElementById('resultsContent').innerHTML = '<div class="alert alert-danger">' + data.error + '</div>';
                        } else {
                            displayResults(data.results);
                        }
                    })
                    .catch(error => {
                        document.getElementById('resultsContent').innerHTML = '<div class="alert alert-danger">Error: ' + error.message + '</div>';
                    });
                });
                
                function displayResults(results) {
                    let html = '<div class="table-responsive"><table class="table table-striped">';
                    html += '<thead><tr><th>Strategy</th><th>Return</th><th>Final Value</th><th>Trades</th></tr></thead><tbody>';
                    
                    for (const [strategy, result] of Object.entries(results)) {
                        const returnClass = result.total_return > 0 ? 'text-success' : 'text-danger';
                        html += `<tr>
                            <td>${strategy}</td>
                            <td class="${returnClass}">${(result.total_return * 100).toFixed(2)}%</td>
                            <td>$${result.final_value.toFixed(2)}</td>
                            <td>${result.num_trades}</td>
                        </tr>`;
                    }
                    
                    html += '</tbody></table></div>';
                    document.getElementById('resultsContent').innerHTML = html;
                }
            </script>
        </body>
        </html>
        ''', favorites=favorites)
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/run-backtest', methods=['POST'])
@login_required
def api_run_backtest():
    """API endpoint to run backtest"""
    try:
        data = request.get_json()
        coin = data.get('coin')
        days = data.get('days', 90)
        
        if not coin:
            return jsonify({'error': 'No coin specified'}), 400
        
        from advanced_backtest import AdvancedBacktester
        backtester = AdvancedBacktester()
        results = backtester.run_comprehensive_backtest(coin, days)
        
        if results:
            return jsonify({'results': results})
        else:
            return jsonify({'error': 'Failed to run backtest'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db() # Initialize database on startup
    app.run(debug=True, port=5001) 