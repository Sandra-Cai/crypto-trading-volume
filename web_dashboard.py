from flask import Flask, render_template_string, request, redirect, url_for, session, g, jsonify
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical, detect_volume_spike, calculate_price_volume_correlation
from trading_bot import TradingBot, create_strategy_config
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

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production
DATABASE = 'users.db'

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

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
    widget_prefs = {'show_onchain': True, 'show_whale': True, 'show_trend': True, 'show_correlation': True, 'show_news': True}
    if row and row[0]:
        try:
            widget_prefs.update(json.loads(row[0]))
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
                    notify_major_alert(user_id, coin, 'whale', 'whale_alert', msg)
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
                notify_major_alert(user_id, coin, 'technical', 'rsi_overbought', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if rsi and rsi < 30:
                msg = f'RSI for {coin.upper()} is oversold ({rsi:.1f})'
                notify_major_alert(user_id, coin, 'technical', 'rsi_oversold', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if macd and signal and macd > signal:
                msg = f'MACD bullish crossover detected for {coin.upper()} (MACD: {macd:.2f}, Signal: {signal:.2f})'
                notify_major_alert(user_id, coin, 'technical', 'macd_bullish', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)
            if macd and signal and macd < signal:
                msg = f'MACD bearish crossover detected for {coin.upper()} (MACD: {macd:.2f}, Signal: {signal:.2f})'
                notify_major_alert(user_id, coin, 'technical', 'macd_bearish', msg)
                if email:
                    send_email_notification(email, f'Technical Alert for {coin.upper()}', msg)

    # --- Arbitrage opportunity notifications ---
    if 'arbitrage' in alert_types:
        for coin in user_favorites:
            arb = detect_arbitrage_opportunities(coin)
            if arb:
                msg = f'Arbitrage opportunity for {coin.upper()}: Buy on {arb["buy_exchange"]} at {arb["buy_price"]}, sell on {arb["sell_exchange"]} at {arb["sell_price"]} (spread: {arb["spread"]:.2f}%)'
                notify_major_alert(user_id, coin, 'arbitrage', 'arbitrage_opportunity', msg)
                if email:
                    send_email_notification(email, f'Arbitrage Alert for {coin.upper()}', msg)

    # --- News sentiment spike notifications ---
    if 'news' in alert_types:
        for coin in user_favorites:
            sentiment = fetch_social_sentiment(coin)
            if sentiment and abs(sentiment['change']) > 0.5:
                direction = 'positive' if sentiment['change'] > 0 else 'negative'
                msg = f'News sentiment spike for {coin.upper()}: {direction} ({sentiment["score"]:.2f}, change: {sentiment["change"]:+.2f})'
                notify_major_alert(user_id, coin, 'news', f'news_sentiment_{direction}', msg)
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
    ... existing code ...
    ''', msg=msg, feedbacks=feedbacks)

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
    notify_major_alert(user_id, None, 'summary', 'daily_summary', f"Daily summary for your portfolio:\n{summary}")
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
# ... replace notify_major_alert calls with notify_major_alert_with_push ...

if __name__ == '__main__':
    init_db() # Initialize database on startup
    app.run(debug=True) 