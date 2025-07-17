from flask import Flask, render_template_string, request, redirect, url_for, session, g
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

# --- Settings page for alerts ---
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session.get('user_id')
    db = get_db()
    error = None
    if request.method == 'POST':
        telegram_id = request.form.get('telegram_id', '')
        discord_webhook = request.form.get('discord_webhook', '')
        db.execute('UPDATE users SET telegram_id = ?, discord_webhook = ? WHERE id = ?', (telegram_id, discord_webhook, user_id))
        db.commit()
        return redirect(url_for('settings'))
    row = query_db('SELECT telegram_id, discord_webhook FROM users WHERE id = ?', [user_id], one=True)
    telegram_id = row[0] if row else ''
    discord_webhook = row[1] if row else ''
    return render_template_string('''
    <html><head><title>Alert Settings</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head><body class="container py-5">
    <h2>Alert Settings</h2>
    <form method="post" class="w-100 w-md-50 mx-auto">
        <div class="mb-3"><label class="form-label">Telegram Chat ID:</label><input class="form-control" type="text" name="telegram_id" value="{{ telegram_id }}"></div>
        <div class="mb-3"><label class="form-label">Discord Webhook URL:</label><input class="form-control" type="text" name="discord_webhook" value="{{ discord_webhook }}"></div>
        <button class="btn btn-primary" type="submit">Save</button>
    </form>
    <div class="mt-3"><a href="{{ url_for('index') }}">Back to Dashboard</a></div>
    </body></html>
    ''', telegram_id=telegram_id, discord_webhook=discord_webhook)

# --- Advanced Analytics: Whale Alerts & On-chain Metrics ---
def fetch_whale_alerts(coin):
    # For demo, use Whale Alert public API (mock if no API key)
    # https://docs.whale-alert.io/
    # We'll mock with a static example for now
    if coin.lower() == 'bitcoin':
        return [
            {'amount': 1200, 'from': 'ExchangeA', 'to': 'Wallet', 'timestamp': '2024-05-01 12:00', 'txid': 'abc123'},
            {'amount': 800, 'from': 'Wallet', 'to': 'ExchangeB', 'timestamp': '2024-05-01 10:30', 'txid': 'def456'},
        ]
    return []

def fetch_onchain_stats(coin):
    # For demo, mock some stats
    if coin.lower() == 'bitcoin':
        return {'active_addresses': 950000, 'large_transfers': 120, 'total_volume': 3500000}
    return {'active_addresses': 0, 'large_transfers': 0, 'total_volume': 0}

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
        <div class="d-flex justify-content-end mb-2"><a href="{{ url_for('logout') }}" class="btn btn-outline-secondary">{{ t('logout') }}</a></div>
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
        <div class="mb-4" id="live-chart">{{ plot_div|safe }}</div>
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
        <div class="mb-4">{{ trend_div|safe }}</div>
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
        <h2>Advanced Analytics</h2>
        <div class="mb-3">
            <b>On-chain Stats:</b><br>
            Active Addresses: {{ onchain_stats.active_addresses }}<br>
            Large Transfers: {{ onchain_stats.large_transfers }}<br>
            Total Volume: {{ onchain_stats.total_volume }}
        </div>
        <div class="mb-3">
            <b>Recent Whale Transactions:</b>
            <ul class="list-group">
                {% for tx in whale_alerts %}
                <li class="list-group-item">
                    <b>{{ tx.amount }}</b> {{ selected_coin.upper() }} from {{ tx.from }} to {{ tx.to }} at {{ tx.timestamp }}<br>
                    TxID: {{ tx.txid }}
                </li>
                {% endfor %}
                {% if not whale_alerts %}
                <li class="list-group-item">No recent whale transactions found.</li>
                {% endif %}
            </ul>
        </div>
    </body>
    </html>
    ''', t=t, lang=lang, coins=coins, selected_coin=selected_coin, selected_exchange=selected_exchange, show_trend=show_trend, plot_div=plot_div, trend_div=trend_div, price=price, alert_msgs=alert_msgs, request=request, portfolio_results=portfolio_results, spike_alerts=spike_alerts, correlation_results=correlation_results, detect_spikes=detect_spikes, show_correlation=show_correlation, live=live, bot_running=bot_running, bot_coin=bot_coin, bot_strategy=bot_strategy, bot_portfolio=bot_portfolio, bot_trades=bot_trades, backtest_result=backtest_result, backtest_coin=backtest_coin, backtest_strategy=backtest_strategy, backtest_days=backtest_days, user_favorites=user_favorites, news_with_sentiment=news_with_sentiment, whale_alerts=whale_alerts, onchain_stats=onchain_stats)

if __name__ == '__main__':
    init_db() # Initialize database on startup
    app.run(debug=True) 