from flask import Flask, render_template_string
from fetch_volume import fetch_coingecko_trending, fetch_binance_volume
import plotly.graph_objs as go
import plotly.offline as pyo

app = Flask(__name__)

@app.route('/')
def index():
    trending = fetch_coingecko_trending()
    volumes = []
    coins = []
    for coin in trending:
        symbol = coin.upper()
        volume = fetch_binance_volume(symbol)
        if volume:
            coins.append(symbol)
            volumes.append(volume)
    bar = go.Bar(x=coins, y=volumes)
    layout = go.Layout(title='Trending Crypto 24h Trading Volume (Binance)', xaxis=dict(title='Coin'), yaxis=dict(title='Volume (USDT)'))
    fig = go.Figure(data=[bar], layout=layout)
    plot_div = pyo.plot(fig, output_type='div', include_plotlyjs=False)
    return render_template_string('''
    <html>
    <head>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <title>Crypto Trading Volume Dashboard</title>
    </head>
    <body>
        <h1>Trending Crypto 24h Trading Volume (Binance)</h1>
        {{ plot_div|safe }}
    </body>
    </html>
    ''', plot_div=plot_div)

if __name__ == '__main__':
    app.run(debug=True) 