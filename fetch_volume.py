import requests
from datetime import datetime, timedelta
import time
import statistics
import json
import asyncio
import aiohttp
import logging
import os
import redis

# Set up a default logger
logger = logging.getLogger("fetch_volume")
logging.basicConfig(level=logging.INFO)

# --- Simple in-memory cache ---
_cache = {}
_cache_expiry = 60  # seconds

# --- Redis cache setup ---
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
REDIS_CACHE_EXPIRY = int(os.environ.get('REDIS_CACHE_EXPIRY', '60'))  # seconds
redis_client = None
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    # Test the connection
    redis_client.ping()
except Exception:
    redis_client = None

# --- Enhanced cache_get and cache_set ---
def cache_get(key):
    # Try in-memory cache first
    entry = _cache.get(key)
    if entry and (time.time() - entry['time'] < _cache_expiry):
        return entry['value']
    # Try Redis cache
    if redis_client:
        value = redis_client.get(key)
        if value is not None:
            try:
                return json.loads(value)
            except Exception:
                return value
    return None

def cache_set(key, value):
    _cache[key] = {'value': value, 'time': time.time()}
    if redis_client:
        try:
            redis_client.setex(key, REDIS_CACHE_EXPIRY, json.dumps(value))
        except Exception:
            pass

# --- Async HTTP Session Context ---
class AiohttpSession:
    def __init__(self):
        self.session = None
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self.session
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

# --- Async Market Data from CoinGecko ---
async def fetch_market_data_async(symbol, session):
    key = f'market_data_{symbol}'
    cached = cache_get(key)
    if cached:
        return cached
    url = f'https://api.coingecko.com/api/v3/coins/{symbol.lower()}'
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[CoinGecko] Failed to fetch market data for {symbol}: HTTP {response.status}")
                cache_set(key, None)
                return None
            data = await response.json()
        market_data = {
            'market_cap': data['market_data']['market_cap']['usd'],
            'price_change_24h': data['market_data']['price_change_percentage_24h'],
            'market_cap_rank': data['market_cap_rank'],
            'circulating_supply': data['market_data']['circulating_supply'],
            'total_supply': data['market_data']['total_supply'],
            'ath': data['market_data']['ath']['usd'],
            'ath_change_percentage': data['market_data']['ath_change_percentage']['usd']
        }
        cache_set(key, market_data)
        return market_data
    except Exception as e:
        logger.error(f"[CoinGecko] Exception fetching market data for {symbol}: {e}")
        cache_set(key, None)
        return None

def fetch_market_data(symbol):
    """Synchronous wrapper for async fetch_market_data_async"""
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_market_data_async(symbol, session)
    return asyncio.run(wrapper())

# --- Async Market Dominance ---
async def fetch_market_dominance_async(session):
    key = 'market_dominance'
    cached = cache_get(key)
    if cached:
        return cached
    url = 'https://api.coingecko.com/api/v3/global'
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[CoinGecko] Failed to fetch market dominance: HTTP {response.status}")
                cache_set(key, None)
                return None
            data = await response.json()
        dominance = data['data']['market_cap_percentage']
        cache_set(key, dominance)
        return dominance
    except Exception as e:
        logger.error(f"[CoinGecko] Exception fetching market dominance: {e}")
        cache_set(key, None)
        return None

def fetch_market_dominance():
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_market_dominance_async(session)
    return asyncio.run(wrapper())

# --- Async Trending coins from CoinGecko ---
async def fetch_coingecko_trending_async(session):
    key = 'coingecko_trending'
    cached = cache_get(key)
    if cached:
        return cached
    url = 'https://api.coingecko.com/api/v3/search/trending'
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
        trending = [item['item']['id'] for item in data['coins']]
        cache_set(key, trending)
        return trending
    except Exception as e:
        logger.error(f"[CoinGecko] Exception fetching trending coins: {e}")
        cache_set(key, None)
        return None

def fetch_coingecko_trending():
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_coingecko_trending_async(session)
    return asyncio.run(wrapper())

# --- Social Sentiment Analysis (Mock) ---
def fetch_social_sentiment(symbol):
    """Mock social sentiment analysis - in production, integrate with Twitter/Reddit APIs"""
    key = f'sentiment_{symbol}'
    cached = cache_get(key)
    if cached:
        return cached
    
    # Mock sentiment score (-1 to 1 is very positive)
    import random
    sentiment = random.uniform(-0.8, 0.8)
    cache_set(key, sentiment)
    return sentiment

# --- Technical Indicators ---
def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = statistics.mean(gains[-period:])
    avg_loss = statistics.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 * (1 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    if len(prices) < slow:
        return None, None, None
    
    # Calculate EMAs
    def ema(data, period):
        multiplier = 2 / (period + 1)
        ema_values = [data[0]]
        for price in data[1:]:
            ema_values.append((price * multiplier) + (ema_values[-1] * (1 - multiplier)))
        return ema_values
    
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    
    # MACD line
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
    
    # Signal line
    signal_line = ema(macd_line, signal)
    
    # Histogram
    histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]
    
    return macd_line[-1], signal_line[-1], histogram[-1]

# --- Arbitrage Detection ---
def detect_arbitrage_opportunities(symbol):
    """Detect price differences across exchanges for arbitrage opportunities"""
    volumes = fetch_all_volumes(symbol)
    prices = {}
    
    # Fetch prices from different exchanges
    for exchange in volumes.keys():
        price = fetch_price_from_exchange(symbol, exchange)
        if price:
            prices[exchange] = price
    
    if len(prices) < 2:
        return []
    # Find min and max prices
    min_price = min(prices.values())
    max_price = max(prices.values())
    min_exchange = min(prices, key=prices.get)
    max_exchange = max(prices, key=prices.get)
    
    # Calculate arbitrage opportunity
    spread = ((max_price - min_price) / min_price) * 100
    
    if spread > 0.5:  # 0.5% threshold
        return [{
            'buy_exchange': min_exchange,
            'sell_exchange': max_exchange,
            'buy_price': min_price,
            'sell_price': max_price,
            'spread_percentage': spread
        }]
    
    return []

# --- Async Price from Exchange ---
async def fetch_price_from_exchange_async(symbol, exchange, session):
    try:
        if exchange == 'binance':
            url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}USDT'
        elif exchange == 'coinbase':
            url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/ticker'
        elif exchange == 'kraken':
            kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
            kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
            url = f'https://api.kraken.com/0/public/Ticker?pair={kraken_symbol}'
        else:
            return None
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[{exchange}] Failed to fetch price for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        if exchange == 'binance':
            return float(data['price'])
        elif exchange == 'coinbase':
            return float(data['price'])
        elif exchange == 'kraken':
            pair = list(data['result'].keys())[0]
            return float(data['result'][pair]['c'][0])
    except Exception as e:
        logger.error(f"[{exchange}] Exception fetching price for {symbol}: {e}")
        return None

def fetch_price_from_exchange(symbol, exchange):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_price_from_exchange_async(symbol, exchange, session)
    return asyncio.run(wrapper())

# --- Async Volume/Historical for Each Exchange ---
async def fetch_binance_volume_async(symbol, session):
    try:
        url = f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}USDT'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Binance] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        return float(data['quoteVolume'])
    except Exception as e:
        logger.error(f"[Binance] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_binance_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_binance_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_binance_historical_async(symbol, days, session):
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol.upper()}USDT&interval=1d&limit={days}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Binance] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        return [float(day[7]) for day in data]
    except Exception as e:
        logger.error(f"[Binance] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_binance_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_binance_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

async def fetch_coinbase_volume_async(symbol, session):
    try:
        url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/stats'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Coinbase] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        return float(data.get('volume', 0))
    except Exception as e:
        logger.error(f"[Coinbase] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_coinbase_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_coinbase_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_coinbase_historical_async(symbol, days, session):
    try:
        url = f'https://api.pro.coinbase.com/products/{symbol.upper()}-USD/candles?granularity=86400&limit={days}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Coinbase] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        return [float(day[5]) for day in data]
    except Exception as e:
        logger.error(f"[Coinbase] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_coinbase_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_coinbase_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

async def fetch_kraken_volume_async(symbol, session):
    try:
        kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
        kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
        url = f'https://api.kraken.com/0/public/Ticker?pair={kraken_symbol}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Kraken] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        pair = list(data['result'].keys())[0]
        return float(data['result'][pair]['v'][1])
    except Exception as e:
        logger.error(f"[Kraken] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_kraken_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_kraken_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_kraken_historical_async(symbol, days, session):
    try:
        kraken_map = {'BTC': 'XBT', 'ETH': 'ETH', 'SOL': 'SOL', 'DOGE': 'DOGE', 'ADA': 'ADA', 'XRP': 'XRP'}
        kraken_symbol = kraken_map.get(symbol.upper(), symbol.upper()) + 'USD'
        url = f'https://api.kraken.com/0/public/OHLC?pair={kraken_symbol}&interval=1440'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Kraken] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        pair = list(data['result'].keys())[0]
        ohlc = data['result'][pair][-days:]
        return [float(day[6]) for day in ohlc]
    except Exception as e:
        logger.error(f"[Kraken] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_kraken_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_kraken_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

async def fetch_kucoin_volume_async(symbol, session):
    try:
        url = f'https://api.kucoin.com/api/v1/market/stats?symbol={symbol.upper()}-USDT'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[KuCoin] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        return float(data['data']['volValue'])
    except Exception as e:
        logger.error(f"[KuCoin] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_kucoin_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_kucoin_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_kucoin_historical_async(symbol, days, session):
    try:
        url = f'https://api.kucoin.com/api/v1/market/candles?type=1day&symbol={symbol.upper()}-USDT&limit={days}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[KuCoin] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        return [float(day[6]) for day in data['data']]
    except Exception as e:
        logger.error(f"[KuCoin] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_kucoin_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_kucoin_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

# --- OKX ---
async def fetch_okx_volume_async(symbol, session):
    try:
        url = f'https://www.okx.com/api/v5/market/ticker?instId={symbol.upper()}-USDT'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[OKX] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        return float(data['data'][0]['volCcy24h'])
    except Exception as e:
        logger.error(f"[OKX] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_okx_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_okx_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_okx_historical_async(symbol, days, session):
    try:
        url = f'https://www.okx.com/api/v5/market/history-candles?instId={symbol.upper()}-USDT&bar=1D&limit={days}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[OKX] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        return [float(day[5]) for day in data['data']]
    except Exception as e:
        logger.error(f"[OKX] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_okx_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_okx_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

# --- Bybit ---
async def fetch_bybit_volume_async(symbol, session):
    try:
        url = f'https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol.upper()}USDT'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Bybit] Failed to fetch volume for {symbol}: HTTP {response.status}")
                return None
            data = await response.json()
        return float(data['result']['list'][0]['quoteVolume24h'])
    except Exception as e:
        logger.error(f"[Bybit] Exception fetching volume for {symbol}: {e}")
        return None

def fetch_bybit_volume(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_bybit_volume_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_bybit_historical_async(symbol, days, session):
    try:
        url = f'https://api.bybit.com/v5/market/history-candles?category=spot&symbol={symbol.upper()}USDT&interval=1D&limit={days}'
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"[Bybit] Failed to fetch historical for {symbol}: HTTP {response.status}")
                return []
            data = await response.json()
        return [float(day[5]) for day in data['result']['list']]
    except Exception as e:
        logger.error(f"[Bybit] Exception fetching historical for {symbol}: {e}")
        return []

def fetch_bybit_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_bybit_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

# --- Enhanced Aggregated fetch ---
async def fetch_all_volumes_async(symbol, session):
    results = await asyncio.gather(
        fetch_binance_volume_async(symbol, session),
        fetch_coinbase_volume_async(symbol, session),
        fetch_kraken_volume_async(symbol, session),
        fetch_kucoin_volume_async(symbol, session),
        fetch_okx_volume_async(symbol, session),
        fetch_bybit_volume_async(symbol, session)
    )
    return {
        'binance': results[0],
        'coinbase': results[1],
        'kraken': results[2],
        'kucoin': results[3],
        'okx': results[4],
        'bybit': results[5]
    }

def fetch_all_volumes(symbol):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_all_volumes_async(symbol, session)
    return asyncio.run(wrapper())

async def fetch_all_historical_async(symbol, days, session):
    results = await asyncio.gather(
        fetch_binance_historical_async(symbol, days, session),
        fetch_coinbase_historical_async(symbol, days, session),
        fetch_kraken_historical_async(symbol, days, session),
        fetch_kucoin_historical_async(symbol, days, session),
        fetch_okx_historical_async(symbol, days, session),
        fetch_bybit_historical_async(symbol, days, session)
    )
    return {
        'binance': results[0],
        'coinbase': results[1],
        'kraken': results[2],
        'kucoin': results[3],
        'okx': results[4],
        'bybit': results[5]
    }

def fetch_all_historical(symbol, days=7):
    async def wrapper():
        async with AiohttpSession() as session:
            return await fetch_all_historical_async(symbol, days, session)
    return asyncio.run(wrapper())

# --- Volume Spike Detection ---
def detect_volume_spike(historical_volumes, threshold=20):
    """Detect if current volume is significantly higher than average"""
    if not historical_volumes or len(historical_volumes) < 3:
        return False, 0.0
    
    current_volume = historical_volumes[-1]
    avg_volume = statistics.mean(historical_volumes[:-1])
    
    if avg_volume == 0:
        return False, 0.0
    spike_ratio = current_volume / avg_volume
    return spike_ratio > threshold, spike_ratio

# --- Price-Volume Correlation ---
def calculate_price_volume_correlation(prices, volumes):
    """Calculate correlation between price and volume changes"""
    if len(prices) != len(volumes) or len(prices) < 2:
        return 0
    
    # Calculate percentage changes
    price_changes = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, len(prices))]
    volume_changes = [(volumes[i] - volumes[i-1])/volumes[i-1] for i in range(1, len(volumes))]
    
    if len(price_changes) < 2:
        return 0
    
    try:
        correlation = statistics.correlation(price_changes, volume_changes)
        return correlation
    except:
        return 0

# --- Main for testing ---
def main():
    print('Fetching trending coins from CoinGecko...')
    trending = fetch_coingecko_trending()
    print('Trending coins:', trending)
    
    print('\nFetching market dominance...')
    dominance = fetch_market_dominance()
    if dominance:
        print('Top 5 by market dominance:')
        for i, (coin, percentage) in enumerate(list(dominance.items())[:5]):
            print(f'  {i+1}. {coin}: {percentage:.2f}%')
    
    print('\nFetching 24h trading volume from all exchanges:')
    for coin in trending:
        symbol = coin.upper()
        volumes = fetch_all_volumes(symbol)
        market_data = fetch_market_data(coin)
        sentiment = fetch_social_sentiment(coin)
        
        print(f'{symbol}:')
        for ex, vol in volumes.items():
            if vol:
                print(f'  {ex}: {vol:,.2f}')
            else:
                print(f'  {ex}: Not found')
        
        if market_data:
            print(f'  Market Cap: ${market_data["market_cap"]:,.2f}')
            print(f'  24h Change: {market_data["price_change_24h"]:.2f}%')
            print(f'  Market Rank: #{market_data["market_cap_rank"]}')
        
        print(f'  Sentiment Score: {sentiment:.3f}')
        
        # Arbitrage detection
        arbitrage = detect_arbitrage_opportunities(symbol)
        if arbitrage:
            print(f'  ARBITRAGE OPPORTUNITY: {arbitrage[0]["spread_percentage"]:.2f}% spread')
    
    print('\nFetching 7-day historical volume for first trending coin:')
    if trending:
        symbol = trending[0].upper()
        hist = fetch_all_historical(symbol)
        for ex, vols in hist.items():
            print(f'{ex}: {vols}')
            if vols:
                is_spike, ratio = detect_volume_spike(vols)
                if is_spike:
                    print(f'  VOLUME SPIKE DETECTED! Current volume is {ratio:.2f}x average')
                
                # Technical indicators
                rsi = calculate_rsi(vols)
                if rsi:
                    print(f'  RSI: {rsi:.2f}')
                
                macd, signal, hist_macd = calculate_macd(vols)
                if macd:
                    print(f'  MACD: [macd: {macd:.2f}, Signal: {signal:.2f}, Histogram: {hist_macd:.2f}]')

if __name__ == '__main__':
    main() 

def fetch_market_sentiment_analysis(symbol):
    """Fetch comprehensive market sentiment analysis from multiple sources"""
    try:
        # Get social sentiment
        social_sentiment = fetch_social_sentiment(symbol)
        
        # Get news sentiment
        news_headlines = fetch_news(symbol)
        news_sentiment = {
            'positive': len([h for h in news_headlines if simple_sentiment(h) == 'positive']),
            'negative': len([h for h in news_headlines if simple_sentiment(h) == 'negative']),
            'neutral': len([h for h in news_headlines if simple_sentiment(h) == 'neutral']),
            'total': len(news_headlines)
        }
        
        # Calculate overall sentiment score
        if news_sentiment['total'] > 0:
            news_score = (news_sentiment['positive'] - news_sentiment['negative']) / news_sentiment['total']
        else:
            news_score = 0
            
        # Get technical indicators sentiment
        try:
            hist_data = fetch_all_historical(symbol.upper(), days=14)
            if hist_data and hist_data.get('binance'):
                rsi = calculate_rsi(hist_data['binance'])
                macd, signal, hist_macd = calculate_macd(hist_data['binance'])
                
                # RSI sentiment
                if rsi:
                    if rsi > 70:
                        rsi_sentiment = -0.5  # Overbought
                    elif rsi < 30:
                        rsi_sentiment = 0.5   # Oversold
                    else:
                        rsi_sentiment = 0     # Neutral
                else:
                    rsi_sentiment = 0
                
                # MACD sentiment
                if macd and signal:
                    if macd > signal:
                        macd_sentiment = 0.3  # Bullish
                    else:
                        macd_sentiment = -0.3 # Bearish
                else:
                    macd_sentiment = 0
            else:
                rsi_sentiment = 0
                macd_sentiment = 0
        except:
            rsi_sentiment = 0
            macd_sentiment = 0
        
        # Volume sentiment (based on recent volume trends)
        try:
            volumes = fetch_all_volumes(symbol.upper())
            if volumes and volumes.get('binance'):
                current_volume = volumes['binance']
                hist_volumes = hist_data.get('binance', []) if hist_data else []
                if hist_volumes and len(hist_volumes) >= 3:
                    avg_volume = sum(hist_volumes[-3:]) / 3
                    if current_volume > avg_volume * 1.5:
                        volume_sentiment = 0.4  # High volume
                    elif current_volume < avg_volume * 0.5:
                        volume_sentiment = -0.2 # Low volume
                    else:
                        volume_sentiment = 0    # Normal volume
                else:
                    volume_sentiment = 0
            else:
                volume_sentiment = 0
        except:
            volume_sentiment = 0
        
        # Calculate composite sentiment score
        composite_score = (
            news_score * 0.3 +
            rsi_sentiment * 0.2 +
            macd_sentiment * 0.2 +
            volume_sentiment * 0.3
        )
        
        # Determine overall sentiment
        if composite_score > 0.3:
            overall_sentiment = 'bullish'
        elif composite_score < -0.3:
            overall_sentiment = 'bearish'
        else:
            overall_sentiment = 'neutral'
        
        return {
            'symbol': symbol.upper(),
            'composite_score': composite_score,
            'overall_sentiment': overall_sentiment,
            'components': {
                'news_sentiment': news_score,
                'rsi_sentiment': rsi_sentiment,
                'macd_sentiment': macd_sentiment,
                'volume_sentiment': volume_sentiment
            },
            'news_breakdown': news_sentiment,
            'social_sentiment': social_sentiment,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error fetching sentiment analysis for {symbol}: {e}")
        return None 