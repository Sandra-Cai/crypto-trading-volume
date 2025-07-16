import requests
from datetime import datetime, timedelta
import time

# --- Simple in-memory cache ---
_cache = {}
_cache_expiry = 60  # seconds

def cache_get(key):
    entry = _cache.get(key)
    if entry and (time.time() - entry['time'] < _cache_expiry):
        return entry['value']
    return None

def cache_set(key, value):
    _cache[key] = {'value': value, 'time': time.time()}

# --- Trending coins from CoinGecko ---
def fetch_coingecko_trending():
    key = 'coingecko_trending'
    cached = cache_get(key)
    if cached:
        return cached
    url = 'https://api.coingecko.com/api/v3/search/trending'
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    trending = [item['item']['id'] for item in data['coins']]
    cache_set(key, trending)
    return trending

# --- Binance ---
def fetch_binance_volume(symbol):
    key = f'binance_volume_{symbol}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    url = f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}USDT'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, None)
        return None
    data = response.json()
    volume = float(data.get('quoteVolume', 0))
    cache_set(key, volume)
    return volume

def fetch_binance_historical(symbol, days=7):
    key = f'binance_hist_{symbol}_{days}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol.upper()}USDT&interval=1d&limit={days}'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, [])
        return []
    data = response.json()
    result = [float(day[7]) for day in data]
    cache_set(key, result)
    return result

# --- Coinbase ---
def fetch_coinbase_volume(symbol):
    key = f'coinbase_volume_{symbol}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/stats'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, None)
        return None
    data = response.json()
    volume = float(data.get('volume', 0))
    cache_set(key, volume)
    return volume

def fetch_coinbase_historical(symbol, days=7):
    key = f'coinbase_hist_{symbol}_{days}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/candles?granularity=86400&limit={days}'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, [])
        return []
    data = response.json()
    result = [float(day[5]) for day in data]
    cache_set(key, result)
    return result

# --- Kraken ---
def fetch_kraken_volume(symbol):
    key = f'kraken_volume_{symbol}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
    kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
    url = f'https://api.kraken.com/0/public/Ticker?pair={kraken_symbol}'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, None)
        return None
    data = response.json()
    try:
        pair = list(data['result'].keys())[0]
        volume = float(data['result'][pair]['v'][1])
        cache_set(key, volume)
        return volume
    except Exception:
        cache_set(key, None)
        return None

def fetch_kraken_historical(symbol, days=7):
    key = f'kraken_hist_{symbol}_{days}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
    kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
    url = f'https://api.kraken.com/0/public/OHLC?pair={kraken_symbol}&interval=1440'
    response = requests.get(url)
    if response.status_code != 200:
        cache_set(key, [])
        return []
    data = response.json()
    try:
        pair = list(data['result'].keys())[0]
        ohlc = data['result'][pair][-days:]
        result = [float(day[6]) for day in ohlc]
        cache_set(key, result)
        return result
    except Exception:
        cache_set(key, [])
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