from flask import Flask, render_template_string, request, redirect, url_for, session
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical
import plotly.graph_objs as go
import plotly.offline as pyo
import requests
import csv
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production

USERNAME = 'user'
PASSWORD = 'pass'

def fetch_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get(symbol.lower(), {}).get('usd')

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
    <html><head><title>Login</title></head><body>
    <h2>Login</h2>
    {% if error %}<div style="color:red">{{ error }}</div>{% endif %}
    <form method="post">
        <label>Username:</label><input type="text" name="username"><br>
        <label>Password:</label><input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    </body></html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    trending = fetch_coingecko_trending()
    selected_coin = request.form.get('coin', trending[0])
    selected_exchange = request.form.get('exchange', 'all')
    show_trend = request.form.get('trend', 'off') == 'on'
    alert_volume = request.form.get('alert_volume', type=float)
    alert_price = request.form.get('alert_price', type=float)
    coins = trending
    volumes = fetch_all_volumes(selected_coin.upper())
    price = fetch_price(selected_coin)
    hist = fetch_all_historical(selected_coin.upper()) if show_trend else None
    exchanges = ['binance', 'coinbase', 'kraken'] if selected_exchange == 'all' else [selected_exchange]
    bar = go.Bar(x=exchanges, y=[volumes[ex] if volumes[ex] else 0 for ex in exchanges])
    layout = go.Layout(title=f'{selected_coin.upper()} 24h Trading Volume', xaxis=dict(title='Exchange'), yaxis=dict(title='Volume'))
    fig = go.Figure(data=[bar], layout=layout)
    plot_div = pyo.plot(fig, output_type='div', include_plotlyjs=False)
    trend_div = ''
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
        total_volumes = {'binance': 0, 'coinbase': 0, 'kraken': 0}
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
    return render_template_string('''
    <html>
    <head>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <title>Crypto Trading Volume Dashboard</title>
    </head>
    <body>
        <div style="float:right"><a href="{{ url_for('logout') }}">Logout</a></div>
        <h1>Crypto Trading Volume Dashboard</h1>
        <form method="post" enctype="multipart/form-data">
            <label for="coin">Coin:</label>
            <select name="coin">
                {% for coin in coins %}
                <option value="{{ coin }}" {% if coin == selected_coin %}selected{% endif %}>{{ coin.upper() }}</option>
                {% endfor %}
            </select>
            <label for="exchange">Exchange:</label>
            <select name="exchange">
                <option value="all" {% if selected_exchange == 'all' %}selected{% endif %}>All</option>
                <option value="binance" {% if selected_exchange == 'binance' %}selected{% endif %}>Binance</option>
                <option value="coinbase" {% if selected_exchange == 'coinbase' %}selected{% endif %}>Coinbase</option>
                <option value="kraken" {% if selected_exchange == 'kraken' %}selected{% endif %}>Kraken</option>
            </select>
            <label for="trend">Show 7-day trend</label>
            <input type="checkbox" name="trend" {% if show_trend %}checked{% endif %}>
            <label for="alert_volume">Alert if volume exceeds:</label>
            <input type="number" step="any" name="alert_volume" value="{{ request.form.get('alert_volume', '') }}">
            <label for="alert_price">Alert if price exceeds:</label>
            <input type="number" step="any" name="alert_price" value="{{ request.form.get('alert_price', '') }}">
            <label for="portfolio">Upload Portfolio CSV (coin,amount):</label>
            <input type="file" name="portfolio">
            <input type="submit" value="Update">
        </form>
        <h2>{{ selected_coin.upper() }} (Price: {{ price if price else 'N/A' }} USD)</h2>
        {% if alert_msgs %}
        <div style="color: red; font-weight: bold;">
            {% for msg in alert_msgs %}
            <div>{{ msg }}</div>
            {% endfor %}
        </div>
        {% endif %}
        {{ plot_div|safe }}
        {{ trend_div|safe }}
        {% if portfolio_results %}
        <h2>Portfolio Tracking</h2>
        <p>Total Portfolio Value: {{ portfolio_results.total_value | round(2) }} USD</p>
        <p>Total Portfolio Volume (amount-weighted):</p>
        <ul>
            {% for ex, vol in portfolio_results.total_volumes.items() %}
            <li>{{ ex }}: {{ vol | round(2) }}</li>
            {% endfor %}
        </ul>
        <table border="1" cellpadding="5">
            <tr><th>Coin</th><th>Amount</th><th>Price (USD)</th><th>Value (USD)</th></tr>
            {% for d in portfolio_results.details %}
            <tr><td>{{ d.coin }}</td><td>{{ d.amount }}</td><td>{{ d.price if d.price else 'N/A' }}</td><td>{{ d.value | round(2) }}</td></tr>
            {% endfor %}
        </table>
        {% endif %}
    </body>
    </html>
    ''', coins=coins, selected_coin=selected_coin, selected_exchange=selected_exchange, show_trend=show_trend, plot_div=plot_div, trend_div=trend_div, price=price, alert_msgs=alert_msgs, request=request, portfolio_results=portfolio_results)

if __name__ == '__main__':
    app.run(debug=True) 