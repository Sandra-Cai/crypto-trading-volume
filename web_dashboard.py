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
            db.execute('UPDATE users SET telegram_id = ?, discord_webhook = ?, webhook_url = ?, webhook_alert_types = ? WHERE id = ?',
                       (telegram_id, discord_webhook, webhook_url, webhook_alert_types, user_id))
            db.commit()
            return redirect(url_for('settings'))
    row = query_db('SELECT telegram_id, discord_webhook, webhook_url, webhook_alert_types FROM users WHERE id = ?', [user_id], one=True)
    telegram_id = row[0] if row else ''
    discord_webhook = row[1] if row else ''
    webhook_url = row[2] if row and len(row) > 2 else ''
    webhook_alert_types = row[3].split(',') if row and row[3] else []
    alert_type_options = ['volume_spike', 'price_spike', 'whale_alert']
    return render_template_string('''
    <html><head><title>Alert Settings</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Alert Settings</h2>
    {% if test_result %}
    <div class="alert alert-{{ test_result[0] }}">{{ test_result[1] }}</div>
    {% endif %}
    <form method="post" class="w-100 w-md-50 mx-auto">
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
        <button class="btn btn-primary" type="submit">Save</button>
        <button class="btn btn-secondary ms-2" name="test_webhook" value="1" type="submit">Test Webhook</button>
    </form>
    <div class="mt-3"><a href="{{ url_for('index') }}">Back to Dashboard</a></div>
    </body></html>
    ''', telegram_id=telegram_id, discord_webhook=discord_webhook, webhook_url=webhook_url, webhook_alert_types=webhook_alert_types, alert_type_options=alert_type_options, test_result=test_result)

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

    return render_template_string('''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <title>Crypto Trading Volume Dashboard</title>
    </head>
    <body class="container py-3">
        <form method="post" action="/setlang" class="mb-3">
            <label for="lang">{{ t('select_language') }}:</label>
            <select name="lang" class="form-select d-inline w-auto">
                <option value="en" {% if lang == 'en' %}selected{% endif %}>{{ t('english') }}</option>
                <option value="es" {% if lang == 'es' %}selected{% endif %}>{{ t('spanish') }}</option>
            </select>
            <button class="btn btn-secondary btn-sm" type="submit">{{ t('update') }}</button>
        </form>
        <div class="d-flex justify-content-end mb-2">
            <a href="{{ url_for('customize_dashboard') }}" class="btn btn-outline-primary me-2">{{ t('customize_dashboard') }}</a>
            <a href="{{ url_for('logout') }}" class="btn btn-outline-secondary">{{ t('logout') }}</a>
        </div>
        <h1 class="mb-4">{{ t('crypto_trading_volume_dashboard') }}</h1>
        <form method="post" enctype="multipart/form-data" class="row g-3 mb-4">
            <div class="col-12 col-md-2">
                <label for="coin" class="form-label">{{ t('coin') }}:</label>
                <select name="coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == selected_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-2">
                <label for="exchange" class="form-label">{{ t('exchange') }}:</label>
                <select name="exchange" class="form-select">
                    <option value="all" {% if selected_exchange == 'all' %}selected{% endif %}>{{ t('all') }}</option>
                    <option value="binance" {% if selected_exchange == 'binance' %}selected{% endif %}>Binance</option>
                    <option value="coinbase" {% if selected_exchange == 'coinbase' %}selected{% endif %}>Coinbase</option>
                    <option value="kraken" {% if selected_exchange == 'kraken' %}selected{% endif %}>Kraken</option>
                    <option value="kucoin" {% if selected_exchange == 'kucoin' %}selected{% endif %}>KuCoin</option>
                    <option value="okx" {% if selected_exchange == 'okx' %}selected{% endif %}>OKX</option>
                    <option value="bybit" {% if selected_exchange == 'bybit' %}selected{% endif %}>Bybit</option>
                </select>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="trend" {% if show_trend %}checked{% endif %}>
                    <label class="form-check-label" for="trend">{{ t('show_7_day_trend') }}</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="detect_spikes" {% if detect_spikes %}checked{% endif %}>
                    <label class="form-check-label" for="detect_spikes">{{ t('detect_spikes') }}</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="correlation" {% if show_correlation %}checked{% endif %}>
                    <label class="form-check-label" for="correlation">{{ t('price_volume_correlation') }}</label>
                </div>
            </div>
            <div class="col-12 col-md-2">
                <label for="alert_volume" class="form-label">{{ t('alert_if_volume_exceeds') }}:</label>
                <input class="form-control" type="number" step="any" name="alert_volume" value="{{ request.form.get('alert_volume', '') }}">
            </div>
            <div class="col-12 col-md-2">
                <label for="alert_price" class="form-label">{{ t('alert_if_price_exceeds') }}:</label>
                <input class="form-control" type="number" step="any" name="alert_price" value="{{ request.form.get('alert_price', '') }}">
            </div>
            <div class="col-12 col-md-4">
                <label for="portfolio" class="form-label">{{ t('upload_portfolio_csv') }}:</label>
                <input class="form-control" type="file" name="portfolio">
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="live" {% if live %}checked{% endif %}>
                    <label class="form-check-label" for="live">{{ t('live_binance') }}</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <button class="btn btn-primary w-100" type="submit">{{ t('update') }}</button>
            </div>
        </form>
        {% if failed_exchanges %}
        <div class="alert alert-warning">
            <b>Some exchanges failed to return data:</b> {{ failed_exchanges|join(', ') }}. This may be due to API downtime or rate limits.
        </div>
        {% endif %}
        <h2 class="mb-3">{{ selected_coin.upper() }} ({{ t('price') }}: {{ price if price else 'N/A' }} USD)</h2>
        {% if alert_msgs %}
        <div class="alert alert-danger">
            {% for msg in alert_msgs %}
            <div>{{ msg }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {% if spike_alerts %}
        <div class="alert alert-warning">
            <h5>{{ t('volume_spikes_detected') }}:</h5>
            {% for msg in spike_alerts %}
            <div>{{ msg }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {% if correlation_results %}
        <div class="alert alert-info">
            <h5>{{ t('price_volume_correlation') }}:</h5>
            {% for ex, corr in correlation_results.items() %}
            <div>{{ ex }}: {{ "%.3f"|format(corr) }}</div>
            {% endfor %}
        </div>
        {% endif %}
        <div class="mb-4" id="live-chart">
            {{ plot_div|safe }}
            <ul class="list-group mt-2">
            {% for ex in exchanges %}
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    {{ ex }}
                    {% if volumes[ex] is none %}
                        <span class="badge bg-danger">Unavailable (API error)</span>
                    {% else %}
                        <span class="badge bg-primary">{{ volumes[ex]|round(2) }}</span>
                    {% endif %}
                </li>
            {% endfor %}
            </ul>
        </div>
        {% if show_trend and hist %}
        <div class="mb-4">
            {% for ex in exchanges %}
                <div class="mb-2">
                    <b>{{ ex }} 7-day trend:</b>
                    {% if hist[ex] and hist[ex]|length > 0 %}
                        <!-- Trend chart is already in trend_div -->
                    {% else %}
                        <span class="badge bg-danger">Unavailable (API error)</span>
                    {% endif %}
                </div>
            {% endfor %}
            {{ trend_div|safe }}
        </div>
        {% endif %}
        {% if live and selected_exchange == 'binance' %}
        <script>
        const ws = new WebSocket('wss://stream.binance.com:9443/ws/{{ selected_coin.lower() }}usdt@ticker');
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const price = data.c;
            const volume = data.v;
            document.getElementById('live-chart').innerHTML = `<div class='alert alert-info'>{{ t('live_price') }}: <b>${price}</b> USDT | {{ t('24h_volume') }}: <b>${volume}</b></div>`;
        };
        </script>
        {% endif %}
        {% if portfolio_results %}
        <h2>{{ t('portfolio_tracking') }}</h2>
        <p>{{ t('total_portfolio_value') }}: <strong>{{ portfolio_results.total_value | round(2) }} USD</strong></p>
        <p>{{ t('total_portfolio_volume_amount_weighted') }}:</p>
        <ul>
            {% for ex, vol in portfolio_results.total_volumes.items() %}
            <li>{{ ex }}: {{ vol | round(2) }}</li>
            {% endfor %}
        </ul>
        <div class="table-responsive">
        <table class="table table-bordered table-striped">
            <thead><tr><th>{{ t('coin') }}</th><th>{{ t('amount') }}</th><th>{{ t('price_usd') }}</th><th>{{ t('value_usd') }}</th></tr></thead>
            <tbody>
            {% for d in portfolio_results.details %}
            <tr><td>{{ d.coin }}</td><td>{{ d.amount }}</td><td>{{ d.price if d.price else 'N/A' }}</td><td>{{ d.value | round(2) }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
        </div>
        {% endif %}
        <h2>{{ t('trading_bot') }}</h2>
        <form method="post" action="/bot" class="row g-3 mb-4">
            <div class="col-12 col-md-3">
                <label for="bot_coin" class="form-label">{{ t('coin') }}:</label>
                <select name="bot_coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == bot_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-3">
                <label for="bot_strategy" class="form-label">{{ t('strategy') }}:</label>
                <select name="bot_strategy" class="form-select">
                    <option value="all" {% if bot_strategy == 'all' %}selected{% endif %}>{{ t('all') }}</option>
                    <option value="volume_spike" {% if bot_strategy == 'volume_spike' %}selected{% endif %}>{{ t('volume_spike') }}</option>
                    <option value="rsi" {% if bot_strategy == 'rsi' %}selected{% endif %}>{{ t('rsi') }}</option>
                    <option value="price_alerts" {% if bot_strategy == 'price_alerts' %}selected{% endif %}>{{ t('price_alerts') }}</option>
                </select>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                {% if bot_running %}
                <button class="btn btn-danger w-100" name="bot_action" value="stop" type="submit">{{ t('stop_bot') }}</button>
                {% else %}
                <button class="btn btn-success w-100" name="bot_action" value="start" type="submit">{{ t('start_bot') }}</button>
                {% endif %}
            </div>
        </form>
        {% if bot_running %}
        <div class="alert alert-info">
            {{ t('bot_running_for') }} <b>{{ bot_coin.upper() }}</b> ({{ t('strategy') }}: <b>{{ bot_strategy }}</b>)<br>{{ t('portfolio_value') }}: <b>${{ bot_portfolio|round(2) }}</b></div>
        <h5>{{ t('trade_log') }}</h5>
        <div class="table-responsive">
        <table class="table table-bordered table-striped">
            <thead><tr><th>{{ t('time') }}</th><th>{{ t('action') }}</th><th>{{ t('coin') }}</th><th>{{ t('amount') }}</th><th>{{ t('price') }}</th><th>{{ t('reason') }}</th><th>{{ t('portfolio_value') }}</th></tr></thead>
            <tbody>
            {% for trade in bot_trades %}
            <tr><td>{{ trade.timestamp }}</td><td>{{ trade.action }}</td><td>{{ trade.coin }}</td><td>{{ trade.amount }}</td><td>{{ trade.price }}</td><td>{{ trade.reason }}</td><td>{{ trade.portfolio_value|round(2) }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
        </div>
        {% endif %}
        <h2>{{ t('backtesting') }}</h2>
        <form method="post" action="/backtest" class="row g-3 mb-4">
            <div class="col-12 col-md-3">
                <label for="backtest_coin" class="form-label">{{ t('coin') }}:</label>
                <select name="backtest_coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == backtest_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-3">
                <label for="backtest_strategy" class="form-label">{{ t('strategy') }}:</label>
                <select name="backtest_strategy" class="form-select">
                    <option value="volume_spike" {% if backtest_strategy == 'volume_spike' %}selected{% endif %}>{{ t('volume_spike') }}</option>
                    <option value="rsi" {% if backtest_strategy == 'rsi' %}selected{% endif %}>{{ t('rsi') }}</option>
                </select>
            </div>
            <div class="col-12 col-md-2">
                <label for="backtest_days" class="form-label">{{ t('days') }}:</label>
                <input class="form-control" type="number" name="backtest_days" value="{{ backtest_days }}" min="7" max="180">
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <button class="btn btn-primary w-100" type="submit">{{ t('run_backtest') }}</button>
            </div>
        </form>
        {% if backtest_result %}
        <div class="alert alert-secondary" style="white-space: pre-wrap;">{{ backtest_result }}</div>
        {% endif %}
        <h2>{{ t('user_profile') }}</h2>
        <form method="post" action="/favorites" class="mb-4">
            <label for="favorites">{{ t('favorites') }}:</label>
            <select name="favorites" multiple class="form-select" style="max-width: 400px;">
                {% for coin in coins %}
                <option value="{{ coin }}" {% if coin in user_favorites %}selected{% endif %}>{{ coin.upper() }}</option>
                {% endfor %}
            </select>
            <button class="btn btn-primary mt-2" type="submit">{{ t('save_favorites') }}</button>
        </form>
        {% if widget_prefs.show_onchain %}
        <h2>Advanced Analytics</h2>
        <div class="mb-3 card p-3 shadow-sm">
            <b>On-chain Stats:</b><br>
            <ul class="list-group list-group-flush mb-2">
                <li class="list-group-item">Active Addresses: <b>{{ onchain_stats.active_addresses }}</b></li>
                <li class="list-group-item">Large Transfers: <b>{{ onchain_stats.large_transfers }}</b></li>
                <li class="list-group-item">Total Volume: <b>{{ onchain_stats.total_volume }}</b></li>
            </ul>
        </div>
        {% endif %}
        {% if widget_prefs.show_whale %}
        <div class="mb-3 card p-3 shadow-sm">
            <b>Recent Whale Transactions:</b>
            <ul class="list-group">
                {% for tx in whale_alerts %}
                <li class="list-group-item">
                    <b>{{ tx.amount }}</b> {{ selected_coin.upper() }} from <b>{{ tx.from }}</b> to <b>{{ tx.to }}</b> at <b>{{ tx.timestamp }}</b><br>
                    TxID: <code>{{ tx.txid }}</code>
                </li>
                {% endfor %}
                {% if not whale_alerts %}
                <li class="list-group-item">No recent whale transactions found.</li>
                {% endif %}
            </ul>
        </div>
        {% endif %}
        {% if widget_prefs.show_correlation and correlation_results %}
        <div class="alert alert-info">
            <h5>{{ t('price_volume_correlation') }}:</h5>
            {% for ex, corr in correlation_results.items() %}
            <div>{{ ex }}: {{ "%.3f"|format(corr) }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {% if widget_prefs.show_news %}
        <h2>News & Sentiment</h2>
        <ul class="list-group mb-4">
            {% for headline, sentiment in news_with_sentiment %}
            <li class="list-group-item d-flex justify-content-between align-items-center">
                {{ headline }}
                {% if sentiment == 'positive' %}<span class="badge bg-success">Positive</span>{% endif %}
                {% if sentiment == 'negative' %}<span class="badge bg-danger">Negative</span>{% endif %}
                {% if sentiment == 'neutral' %}<span class="badge bg-secondary">Neutral</span>{% endif %}
            </li>
            {% endfor %}
            {% if not news_with_sentiment %}
            <li class="list-group-item">No news found for this coin.</li>
            {% endif %}
        </ul>
        {% endif %}
    </body>
    </html>
    ''', t=t, lang=lang, coins=coins, selected_coin=selected_coin, selected_exchange=selected_exchange, show_trend=show_trend, plot_div=plot_div, trend_div=trend_div, price=price, alert_msgs=alert_msgs, request=request, portfolio_results=portfolio_results, spike_alerts=spike_alerts, correlation_results=correlation_results, detect_spikes=detect_spikes, show_correlation=show_correlation, live=live, bot_running=bot_running, bot_coin=bot_coin, bot_strategy=bot_strategy, bot_portfolio=bot_portfolio, bot_trades=bot_trades, backtest_result=backtest_result, backtest_coin=backtest_coin, backtest_strategy=backtest_strategy, backtest_days=backtest_days, user_favorites=user_favorites, news_with_sentiment=news_with_sentiment, whale_alerts=whale_alerts, onchain_stats=onchain_stats, failed_exchanges=failed_exchanges, widget_prefs=widget_prefs)

# --- Public API endpoints ---
@app.route('/api/trending')
def api_trending():
    trending = fetch_coingecko_trending()
    return jsonify({'trending': trending})

@app.route('/api/volumes/<coin>')
def api_volumes(coin):
    volumes = fetch_all_volumes(coin.upper())
    return jsonify({'coin': coin, 'volumes': volumes})

@app.route('/api/historical/<coin>')
def api_historical(coin):
    hist = fetch_all_historical(coin.upper())
    return jsonify({'coin': coin, 'historical': hist})

@app.route('/api/market_data/<coin>')
def api_market_data(coin):
    data = fetch_market_data(coin)
    return jsonify({'coin': coin, 'market_data': data})

@app.route('/api/onchain/<coin>')
def api_onchain(coin):
    stats = fetch_onchain_stats(coin)
    return jsonify({'coin': coin, 'onchain_stats': stats})

@app.route('/api/whale_alerts/<coin>')
def api_whale_alerts(coin):
    alerts = fetch_whale_alerts(coin)
    return jsonify({'coin': coin, 'whale_alerts': alerts})

# --- API key authentication for user-specific endpoints with rate limiting and revocation ---
def require_api_key(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        user = query_db('SELECT id, username FROM users WHERE password = ?', [api_key], one=True)
        if not user or api_key in ('', 'REVOKED'):
            return jsonify({'error': 'Invalid or revoked API key'}), 403
        # Rate limiting (60 requests/minute)
        if redis_client:
            key = f'api_rate_{api_key}'
            try:
                count = redis_client.incr(key)
                if count == 1:
                    redis_client.expire(key, 60)
                if count > 60:
                    ttl = redis_client.ttl(key)
                    return jsonify({'error': 'Rate limit exceeded', 'retry_after': ttl}), 429
            except Exception:
                pass
        g.api_user = user
        return f(*args, **kwargs)
    return decorated

@app.route('/api/portfolio')
@require_api_key
def api_portfolio():
    user_id, username = g.api_user
    # For demo, just return favorites
    row = query_db('SELECT favorites FROM users WHERE id = ?', [user_id], one=True)
    favorites = row[0].split(',') if row and row[0] else []
    return jsonify({'user': username, 'favorites': favorites})

@app.route('/developer', methods=['GET', 'POST'])
@login_required
def developer_portal():
    user_id = session.get('user_id')
    username = session.get('username')
    db = get_db()
    # API key management
    if request.method == 'POST':
        if 'regenerate_api_key' in request.form:
            new_key = secrets.token_hex(24)
            db.execute('UPDATE users SET password = ? WHERE id = ?', (new_key, user_id))
            db.commit()
        elif 'revoke_api_key' in request.form:
            db.execute('UPDATE users SET password = ? WHERE id = ?', ('REVOKED', user_id))
            db.commit()
    # Get current API key
    row = query_db('SELECT password, webhook_url, webhook_alert_types FROM users WHERE id = ?', [user_id], one=True)
    api_key = row[0] if row else ''
    webhook_url = row[1] if row and len(row) > 1 else ''
    webhook_alert_types = row[2].split(',') if row and row[2] else []
    # Rate limit status (using Redis)
    rate_limit = 60
    rate_used = 0
    rate_reset = 0
    if redis_client and api_key and api_key not in ('', 'REVOKED'):
        key = f'api_rate_{api_key}'
        try:
            rate_used = int(redis_client.get(key) or 0)
            ttl = redis_client.ttl(key)
            rate_reset = max(ttl, 0)
        except Exception:
            pass
    # Recent API usage
    api_events = query_db('SELECT event_type, details, timestamp FROM event_log WHERE user_id = ? AND event_type LIKE "api_%" ORDER BY timestamp DESC LIMIT 20', [user_id])
    # Recent webhook deliveries
    webhook_events = query_db('SELECT details, timestamp FROM event_log WHERE user_id = ? AND event_type = "webhook_alert" ORDER BY timestamp DESC LIMIT 20', [user_id])
    alert_type_options = ['volume_spike', 'price_spike', 'whale_alert']
    return render_template_string('''
    <html><head><title>Developer Portal</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Developer Portal</h2>
    <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">Back to Dashboard</a>
    <div class="mb-4 card p-3 shadow-sm">
        <h4>API Key</h4>
        <div class="input-group mb-2">
            <input type="text" class="form-control" value="{{ api_key }}" readonly>
            <form method="post" style="display:inline-block">
                <button class="btn btn-warning" name="regenerate_api_key" value="1" type="submit">Regenerate</button>
            </form>
            <form method="post" style="display:inline-block">
                <button class="btn btn-danger ms-2" name="revoke_api_key" value="1" type="submit">Revoke</button>
            </form>
        </div>
        <small class="text-muted">Use this key in the <code>X-API-KEY</code> header for authenticated API endpoints.</small>
        {% if api_key == 'REVOKED' %}
        <div class="alert alert-danger mt-2">Your API key is revoked. No API access is allowed until you regenerate a new key.</div>
        {% endif %}
    </div>
    <div class="mb-4 card p-3 shadow-sm">
        <h4>API Rate Limit</h4>
        <div>Limit: <b>{{ rate_limit }}</b> requests/minute</div>
        <div>Used: <b>{{ rate_used }}</b></div>
        <div>Resets in: <b>{{ rate_reset }}</b> seconds</div>
    </div>
    <div class="mb-4 card p-3 shadow-sm">
        <h4>Webhook Settings</h4>
        <div><b>Webhook URL:</b> {{ webhook_url or 'Not set' }}</div>
        <div><b>Alert Types:</b> {% for t in alert_type_options %}{% if t in webhook_alert_types %}<span class="badge bg-primary me-1">{{ t.replace('_', ' ').title() }}</span>{% endif %}{% endfor %}</div>
        <a href="{{ url_for('settings') }}" class="btn btn-sm btn-outline-primary mt-2">Edit Webhook Settings</a>
    </div>
    <div class="mb-4 card p-3 shadow-sm">
        <h4>Recent API Usage</h4>
        <table class="table table-bordered table-striped">
            <thead><tr><th>Type</th><th>Details</th><th>Time</th></tr></thead>
            <tbody>
            {% for e in api_events %}
            <tr><td>{{ e[0] }}</td><td>{{ e[1] }}</td><td>{{ e[2] }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="mb-4 card p-3 shadow-sm">
        <h4>Recent Webhook Deliveries</h4>
        <table class="table table-bordered table-striped">
            <thead><tr><th>Details</th><th>Time</th></tr></thead>
            <tbody>
            {% for e in webhook_events %}
            <tr><td>{{ e[0] }}</td><td>{{ e[1] }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    </body></html>
    ''', api_key=api_key, webhook_url=webhook_url, webhook_alert_types=webhook_alert_types, alert_type_options=alert_type_options, api_events=api_events, webhook_events=webhook_events, rate_limit=rate_limit, rate_used=rate_used, rate_reset=rate_reset)

@app.route('/api-explorer', methods=['GET', 'POST'])
@login_required
def api_explorer():
    api_base = request.host_url.rstrip('/')
    endpoints = [
        {
            'name': 'Trending Coins',
            'path': '/api/trending',
            'method': 'GET',
            'params': [],
            'auth': False,
            'desc': 'Get trending coins (from CoinGecko)'
        },
        {
            'name': 'Volumes',
            'path': '/api/volumes/<coin>',
            'method': 'GET',
            'params': ['coin'],
            'auth': False,
            'desc': 'Get 24h trading volumes for a coin across all exchanges'
        },
        {
            'name': 'Historical',
            'path': '/api/historical/<coin>',
            'method': 'GET',
            'params': ['coin'],
            'auth': False,
            'desc': 'Get historical volume data for a coin'
        },
        {
            'name': 'Market Data',
            'path': '/api/market_data/<coin>',
            'method': 'GET',
            'params': ['coin'],
            'auth': False,
            'desc': 'Get market data for a coin (market cap, price change, etc.)'
        },
        {
            'name': 'On-chain Stats',
            'path': '/api/onchain/<coin>',
            'method': 'GET',
            'params': ['coin'],
            'auth': False,
            'desc': 'Get on-chain stats for a coin'
        },
        {
            'name': 'Whale Alerts',
            'path': '/api/whale_alerts/<coin>',
            'method': 'GET',
            'params': ['coin'],
            'auth': False,
            'desc': 'Get recent whale transactions for a coin'
        },
        {
            'name': 'Portfolio',
            'path': '/api/portfolio',
            'method': 'GET',
            'params': [],
            'auth': True,
            'desc': 'Get user portfolio (favorites); requires API key'
        },
    ]
    result = None
    curl_cmd = None
    selected = None
    if request.method == 'POST':
        idx = int(request.form['endpoint_idx'])
        selected = endpoints[idx]
        url = api_base + selected['path']
        # Replace path params
        for p in selected['params']:
            val = request.form.get(p, '')
            url = url.replace(f'<{p}>', val)
        headers = {}
        if selected['auth']:
            api_key = request.form.get('api_key', '')
            if api_key:
                headers['X-API-KEY'] = api_key
        try:
            resp = ext_requests.get(url, headers=headers, timeout=10)
            result = resp.text
        except Exception as e:
            result = f'Error: {e}'
        # Build curl command
        curl_cmd = f"curl -X GET '{url}'"
        if headers:
            for k, v in headers.items():
                curl_cmd += f" -H '{k}: {v}'"
    return render_template_string('''
    <html><head><title>API Explorer</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>pre { background: #f8f9fa; padding: 1em; border-radius: 4px; }</style>
    </head><body class="container py-5">
    <h2>API Explorer</h2>
    <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">Back to Dashboard</a>
    <div class="mb-4">
        <form method="post">
            <div class="mb-3">
                <label for="endpoint_idx" class="form-label">Select Endpoint:</label>
                <select class="form-select" name="endpoint_idx" id="endpoint_idx" onchange="this.form.submit()">
                    <option value="" disabled selected>Choose an endpoint...</option>
                    {% for i, ep in enumerate(endpoints) %}
                    <option value="{{ i }}" {% if selected and endpoints[i]['name'] == selected['name'] %}selected{% endif %}>{{ ep['name'] }} - {{ ep['desc'] }}</option>
                    {% endfor %}
                </select>
            </div>
            {% if selected %}
            <div class="mb-3">
                <label class="form-label">Endpoint: <code>{{ selected['path'] }}</code></label><br>
                <small>{{ selected['desc'] }}</small>
            </div>
            {% for p in selected['params'] %}
            <div class="mb-3">
                <label class="form-label">{{ p|capitalize }}:</label>
                <input class="form-control" type="text" name="{{ p }}" required>
            </div>
            {% endfor %}
            {% if selected['auth'] %}
            <div class="mb-3">
                <label class="form-label">API Key:</label>
                <input class="form-control" type="text" name="api_key" required>
            </div>
            {% endif %}
            <button class="btn btn-primary" type="submit">Try It!</button>
            {% endif %}
        </form>
    </div>
    {% if curl_cmd %}
    <div class="mb-3">
        <b>cURL Command:</b>
        <pre>{{ curl_cmd }}</pre>
    </div>
    {% endif %}
    {% if result %}
    <div class="mb-3">
        <b>Response:</b>
        <pre>{{ result }}</pre>
    </div>
    {% endif %}
    </body></html>
    ''', endpoints=endpoints, selected=selected, result=result, curl_cmd=curl_cmd)

@app.route('/openapi.json')
def openapi_spec():
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Crypto Trading Volume API",
            "version": "1.0.0",
            "description": "OpenAPI spec for all public API endpoints."
        },
        "servers": [{"url": request.host_url.rstrip('/')}],
        "paths": {
            "/api/trending": {
                "get": {
                    "summary": "Get trending coins",
                    "responses": {"200": {"description": "Trending coins", "content": {"application/json": {}}}}
                }
            },
            "/api/volumes/{coin}": {
                "get": {
                    "summary": "Get 24h trading volumes for a coin",
                    "parameters": [{"name": "coin", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Volumes", "content": {"application/json": {}}}}
                }
            },
            "/api/historical/{coin}": {
                "get": {
                    "summary": "Get historical volume data for a coin",
                    "parameters": [{"name": "coin", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Historical data", "content": {"application/json": {}}}}
                }
            },
            "/api/market_data/{coin}": {
                "get": {
                    "summary": "Get market data for a coin",
                    "parameters": [{"name": "coin", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Market data", "content": {"application/json": {}}}}
                }
            },
            "/api/onchain/{coin}": {
                "get": {
                    "summary": "Get on-chain stats for a coin",
                    "parameters": [{"name": "coin", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "On-chain stats", "content": {"application/json": {}}}}
                }
            },
            "/api/whale_alerts/{coin}": {
                "get": {
                    "summary": "Get recent whale transactions for a coin",
                    "parameters": [{"name": "coin", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Whale alerts", "content": {"application/json": {}}}}
                }
            },
            "/api/portfolio": {
                "get": {
                    "summary": "Get user portfolio (favorites)",
                    "security": [{"ApiKeyAuth": []}],
                    "responses": {"200": {"description": "Portfolio", "content": {"application/json": {}}},
                                   "401": {"description": "API key required"},
                                   "403": {"description": "Invalid or revoked API key"}}
                }
            }
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-KEY"
                }
            }
        }
    }
    from flask import jsonify
    return jsonify(spec)

@app.route('/swagger')
def swagger_ui():
    return render_template_string('''
    <html><head><title>Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    </head><body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
    window.onload = function() {
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    };
    </script>
    </body></html>
    ''')

# Add links to Swagger UI in API Explorer and Developer Portal
# ... existing code ...

if __name__ == '__main__':
    init_db() # Initialize database on startup
    app.run(debug=True) 