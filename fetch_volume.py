import requests
from datetime import datetime, timedelta

# --- Trending coins from CoinGecko ---
def fetch_coingecko_trending():
    url = 'https://api.coingecko.com/api/v3/search/trending'
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    trending = [item['item']['id'] for item in data['coins']]
    return trending

# --- Binance ---
def fetch_binance_volume(symbol):
    url = f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}USDT'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return float(data.get('quoteVolume', 0))

def fetch_binance_historical(symbol, days=7):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol.upper()}USDT&interval=1d&limit={days}'
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    # Each kline: [open_time, open, high, low, close, volume, ...]
    return [float(day[7]) for day in data]  # quote asset volume

# --- Coinbase ---
def fetch_coinbase_volume(symbol):
    url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/stats'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return float(data.get('volume', 0))

def fetch_coinbase_historical(symbol, days=7):
    url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/candles?granularity=86400&limit={days}'
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    # Each candle: [time, low, high, open, close, volume]
    return [float(day[5]) for day in data]

# --- Kraken ---
def fetch_kraken_volume(symbol):
    # Kraken uses different symbols, e.g., XBT for BTC
    kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
    kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
    url = f'https://api.kraken.com/0/public/Ticker?pair={kraken_symbol}'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    try:
        pair = list(data['result'].keys())[0]
        return float(data['result'][pair]['v'][1])  # 24h volume
    except Exception:
        return None

def fetch_kraken_historical(symbol, days=7):
    kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
    kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
    url = f'https://api.kraken.com/0/public/OHLC?pair={kraken_symbol}&interval=1440'
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    try:
        pair = list(data['result'].keys())[0]
        ohlc = data['result'][pair][-days:]
        return [float(day[6]) for day in ohlc]  # volume
    except Exception:
        return []

# --- Aggregated fetch ---
def fetch_all_volumes(symbol):
    return {
        'binance': fetch_binance_volume(symbol),
        'coinbase': fetch_coinbase_volume(symbol),
        'kraken': fetch_kraken_volume(symbol)
    }

def fetch_all_historical(symbol, days=7):
    return {
        'binance': fetch_binance_historical(symbol, days),
        'coinbase': fetch_coinbase_historical(symbol, days),
        'kraken': fetch_kraken_historical(symbol, days)
    }

# --- Main for testing ---
def main():
    print('Fetching trending coins from CoinGecko...')
    trending = fetch_coingecko_trending()
    print('Trending coins:', trending)
    print('\nFetching 24h trading volume from all exchanges:')
    for coin in trending:
        symbol = coin.upper()
        volumes = fetch_all_volumes(symbol)
        print(f'{symbol}:')
        for ex, vol in volumes.items():
            if vol:
                print(f'  {ex}: {vol:,.2f}')
            else:
                print(f'  {ex}: Not found')
    print('\nFetching 7-day historical volume for first trending coin:')
    if trending:
        symbol = trending[0].upper()
        hist = fetch_all_historical(symbol)
        for ex, vols in hist.items():
            print(f'{ex}: {vols}')

if __name__ == '__main__':
    main() 