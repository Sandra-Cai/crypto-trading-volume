from flask import Flask, render_template_string, request
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical
import plotly.graph_objs as go
import plotly.offline as pyo
import requests

def fetch_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get(symbol.lower(), {}).get('usd')

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    trending = fetch_coingecko_trending()
    selected_coin = request.form.get('coin', trending[0])
    selected_exchange = request.form.get('exchange', 'all')
    show_trend = request.form.get('trend', 'off') == 'on'
    coins = trending
    volumes = fetch_all_volumes(selected_coin.upper())
    price = fetch_price(selected_coin)
    hist = fetch_all_historical(selected_coin.upper()) if show_trend else None
    # Bar chart for current volumes
    exchanges = ['binance', 'coinbase', 'kraken'] if selected_exchange == 'all' else [selected_exchange]
    bar = go.Bar(x=exchanges, y=[volumes[ex] if volumes[ex] else 0 for ex in exchanges])
    layout = go.Layout(title=f'{selected_coin.upper()} 24h Trading Volume', xaxis=dict(title='Exchange'), yaxis=dict(title='Volume'))
    fig = go.Figure(data=[bar], layout=layout)
    plot_div = pyo.plot(fig, output_type='div', include_plotlyjs=False)
    # Historical trend chart
    trend_div = ''
    if show_trend and hist:
        for ex in exchanges:
            vols = hist[ex]
            if vols:
                trend_fig = go.Figure()
                trend_fig.add_trace(go.Scatter(x=list(range(len(vols))), y=vols, mode='lines+markers', name=f'{ex} volume'))
                # Moving average
                if len(vols) >= 3:
                    ma = [sum(vols[max(0,i-2):i+1])/min(i+1,3) for i in range(len(vols))]
                    trend_fig.add_trace(go.Scatter(x=list(range(len(ma))), y=ma, mode='lines', name=f'{ex} 3-day MA'))
                trend_fig.update_layout(title=f'{selected_coin.upper()} 7-Day Volume Trend ({ex})', xaxis_title='Days Ago', yaxis_title='Volume')
                trend_div += pyo.plot(trend_fig, output_type='div', include_plotlyjs=False)
    return render_template_string('''
    <html>
    <head>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <title>Crypto Trading Volume Dashboard</title>
    </head>
    <body>
        <h1>Crypto Trading Volume Dashboard</h1>
        <form method="post">
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
            <input type="submit" value="Update">
        </form>
        <h2>{{ selected_coin.upper() }} (Price: {{ price if price else 'N/A' }} USD)</h2>
        {{ plot_div|safe }}
        {{ trend_div|safe }}
    </body>
    </html>
    ''', coins=coins, selected_coin=selected_coin, selected_exchange=selected_exchange, show_trend=show_trend, plot_div=plot_div, trend_div=trend_div, price=price)

if __name__ == '__main__':
    app.run(debug=True) 