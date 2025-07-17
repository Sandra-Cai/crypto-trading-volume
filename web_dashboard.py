from flask import Flask, render_template_string, request, redirect, url_for, session
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical, detect_volume_spike, calculate_price_volume_correlation
from trading_bot import TradingBot, create_strategy_config
import plotly.graph_objs as go
import plotly.offline as pyo
import requests
import csv
import io
import threading
from backtest import backtest_volume_spike, backtest_rsi

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production

USERNAME = 'user'
PASSWORD = 'pass'

# Store bot instance in global dict (for demo, not production)
bot_instances = {}

def fetch_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get(symbol.lower(), {}).get('usd')

def fetch_price_history(symbol, days=7):
    url = f'https://api.coingecko.com/api/v3/coins/{symbol.lower()}/market_chart?vs_currency=usd&days={days}'
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    return [price[1] for price in data['prices']]

def parse_portfolio(file_storage):
    portfolio = []
    stream = io.StringIO(file_storage.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    for row in reader:
        portfolio.append({'coin': row['coin'], 'amount': float(row['amount'])})
    return portfolio

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['logged_in'] = True
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
    </body></html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

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

    return render_template_string('''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <title>Crypto Trading Volume Dashboard</title>
    </head>
    <body class="container py-3">
        <div class="d-flex justify-content-end mb-2"><a href="{{ url_for('logout') }}" class="btn btn-outline-secondary">Logout</a></div>
        <h1 class="mb-4">Crypto Trading Volume Dashboard</h1>
        <form method="post" enctype="multipart/form-data" class="row g-3 mb-4">
            <div class="col-12 col-md-2">
                <label for="coin" class="form-label">Coin:</label>
                <select name="coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == selected_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-2">
                <label for="exchange" class="form-label">Exchange:</label>
                <select name="exchange" class="form-select">
                    <option value="all" {% if selected_exchange == 'all' %}selected{% endif %}>All</option>
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
                    <label class="form-check-label" for="trend">Show 7-day trend</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="detect_spikes" {% if detect_spikes %}checked{% endif %}>
                    <label class="form-check-label" for="detect_spikes">Detect spikes</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="correlation" {% if show_correlation %}checked{% endif %}>
                    <label class="form-check-label" for="correlation">Price-volume correlation</label>
                </div>
            </div>
            <div class="col-12 col-md-2">
                <label for="alert_volume" class="form-label">Alert if volume exceeds:</label>
                <input class="form-control" type="number" step="any" name="alert_volume" value="{{ request.form.get('alert_volume', '') }}">
            </div>
            <div class="col-12 col-md-2">
                <label for="alert_price" class="form-label">Alert if price exceeds:</label>
                <input class="form-control" type="number" step="any" name="alert_price" value="{{ request.form.get('alert_price', '') }}">
            </div>
            <div class="col-12 col-md-4">
                <label for="portfolio" class="form-label">Upload Portfolio CSV (coin,amount):</label>
                <input class="form-control" type="file" name="portfolio">
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="live" {% if live %}checked{% endif %}>
                    <label class="form-check-label" for="live">Live (Binance)</label>
                </div>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <button class="btn btn-primary w-100" type="submit">Update</button>
            </div>
        </form>
        <h2 class="mb-3">{{ selected_coin.upper() }} (Price: {{ price if price else 'N/A' }} USD)</h2>
        {% if alert_msgs %}
        <div class="alert alert-danger">
            {% for msg in alert_msgs %}
            <div>{{ msg }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {% if spike_alerts %}
        <div class="alert alert-warning">
            <h5>Volume Spikes Detected:</h5>
            {% for msg in spike_alerts %}
            <div>{{ msg }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {% if correlation_results %}
        <div class="alert alert-info">
            <h5>Price-Volume Correlation:</h5>
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
            document.getElementById('live-chart').innerHTML = `<div class='alert alert-info'>Live Price: <b>${price}</b> USDT | 24h Volume: <b>${volume}</b></div>`;
        };
        </script>
        {% endif %}
        <div class="mb-4">{{ trend_div|safe }}</div>
        {% if portfolio_results %}
        <h2>Portfolio Tracking</h2>
        <p>Total Portfolio Value: <strong>{{ portfolio_results.total_value | round(2) }} USD</strong></p>
        <p>Total Portfolio Volume (amount-weighted):</p>
        <ul>
            {% for ex, vol in portfolio_results.total_volumes.items() %}
            <li>{{ ex }}: {{ vol | round(2) }}</li>
            {% endfor %}
        </ul>
        <div class="table-responsive">
        <table class="table table-bordered table-striped">
            <thead><tr><th>Coin</th><th>Amount</th><th>Price (USD)</th><th>Value (USD)</th></tr></thead>
            <tbody>
            {% for d in portfolio_results.details %}
            <tr><td>{{ d.coin }}</td><td>{{ d.amount }}</td><td>{{ d.price if d.price else 'N/A' }}</td><td>{{ d.value | round(2) }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
        </div>
        {% endif %}
        <h2>Trading Bot (Demo Mode)</h2>
        <form method="post" action="/bot" class="row g-3 mb-4">
            <div class="col-12 col-md-3">
                <label for="bot_coin" class="form-label">Coin:</label>
                <select name="bot_coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == bot_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-3">
                <label for="bot_strategy" class="form-label">Strategy:</label>
                <select name="bot_strategy" class="form-select">
                    <option value="all" {% if bot_strategy == 'all' %}selected{% endif %}>All</option>
                    <option value="volume_spike" {% if bot_strategy == 'volume_spike' %}selected{% endif %}>Volume Spike</option>
                    <option value="rsi" {% if bot_strategy == 'rsi' %}selected{% endif %}>RSI</option>
                    <option value="price_alerts" {% if bot_strategy == 'price_alerts' %}selected{% endif %}>Price Alerts</option>
                </select>
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                {% if bot_running %}
                <button class="btn btn-danger w-100" name="bot_action" value="stop" type="submit">Stop Bot</button>
                {% else %}
                <button class="btn btn-success w-100" name="bot_action" value="start" type="submit">Start Bot</button>
                {% endif %}
            </div>
        </form>
        {% if bot_running %}
        <div class="alert alert-info">Bot running for <b>{{ bot_coin.upper() }}</b> (Strategy: <b>{{ bot_strategy }}</b>)<br>Portfolio Value: <b>${{ bot_portfolio|round(2) }}</b></div>
        <h5>Trade Log</h5>
        <div class="table-responsive">
        <table class="table table-bordered table-striped">
            <thead><tr><th>Time</th><th>Action</th><th>Coin</th><th>Amount</th><th>Price</th><th>Reason</th><th>Portfolio Value</th></tr></thead>
            <tbody>
            {% for trade in bot_trades %}
            <tr><td>{{ trade.timestamp }}</td><td>{{ trade.action }}</td><td>{{ trade.coin }}</td><td>{{ trade.amount }}</td><td>{{ trade.price }}</td><td>{{ trade.reason }}</td><td>{{ trade.portfolio_value|round(2) }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
        </div>
        {% endif %}
        <h2>Backtesting</h2>
        <form method="post" action="/backtest" class="row g-3 mb-4">
            <div class="col-12 col-md-3">
                <label for="backtest_coin" class="form-label">Coin:</label>
                <select name="backtest_coin" class="form-select">
                    {% for coin in coins %}
                    <option value="{{ coin }}" {% if coin == backtest_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-12 col-md-3">
                <label for="backtest_strategy" class="form-label">Strategy:</label>
                <select name="backtest_strategy" class="form-select">
                    <option value="volume_spike" {% if backtest_strategy == 'volume_spike' %}selected{% endif %}>Volume Spike</option>
                    <option value="rsi" {% if backtest_strategy == 'rsi' %}selected{% endif %}>RSI</option>
                </select>
            </div>
            <div class="col-12 col-md-2">
                <label for="backtest_days" class="form-label">Days:</label>
                <input class="form-control" type="number" name="backtest_days" value="{{ backtest_days }}" min="7" max="180">
            </div>
            <div class="col-12 col-md-2 d-flex align-items-end">
                <button class="btn btn-primary w-100" type="submit">Run Backtest</button>
            </div>
        </form>
        {% if backtest_result %}
        <div class="alert alert-secondary" style="white-space: pre-wrap;">{{ backtest_result }}</div>
        {% endif %}
    </body>
    </html>
    ''', coins=coins, selected_coin=selected_coin, selected_exchange=selected_exchange, show_trend=show_trend, plot_div=plot_div, trend_div=trend_div, price=price, alert_msgs=alert_msgs, request=request, portfolio_results=portfolio_results, spike_alerts=spike_alerts, correlation_results=correlation_results, detect_spikes=detect_spikes, show_correlation=show_correlation, live=live, bot_running=bot_running, bot_coin=bot_coin, bot_strategy=bot_strategy, bot_portfolio=bot_portfolio, bot_trades=bot_trades, backtest_result=backtest_result, backtest_coin=backtest_coin, backtest_strategy=backtest_strategy, backtest_days=backtest_days)

if __name__ == '__main__':
    app.run(debug=True) 