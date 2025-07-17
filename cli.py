import argparse
from fetch_volume import (
    fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical, 
    detect_volume_spike, calculate_price_volume_correlation, fetch_market_data,
    fetch_social_sentiment, calculate_rsi, calculate_macd, detect_arbitrage_opportunities,
    fetch_market_dominance
)
from trading_bot import TradingBot, create_strategy_config
import requests
import csv
import asyncio
import websockets
import json

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

def load_portfolio(filename):
    portfolio = []
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            portfolio.append({'coin': row['coin'], 'amount': float(row['amount'])})
    return portfolio

async def binance_live_stream(symbol):
    ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}usdt@ticker"
    async with websockets.connect(ws_url) as websocket:
        print(f"Streaming live price/volume for {symbol.upper()}USDT on Binance. Press Ctrl+C to stop.")
        try:
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                price = data.get('c')
                volume = data.get('v')
                print(f"Price: {price} USDT | 24h Volume: {volume}", flush=True)
        except KeyboardInterrupt:
            print("\nLive stream stopped.")


def main():
    parser = argparse.ArgumentParser(description='Crypto Trading Volume CLI')
    parser.add_argument('--top', type=int, default=7, help='Number of trending coins to display')
    parser.add_argument('--coin', type=str, help='Specify a coin (e.g., bitcoin)')
    parser.add_argument('--exchange', type=str, choices=['binance', 'coinbase', 'kraken', 'kucoin', 'okx', 'bybit', 'all'], default='all', help='Exchange to query')
    parser.add_argument('--trend', action='store_true', help='Show 7-day historical volume trend')
    parser.add_argument('--export-csv', type=str, help='Export results to CSV file')
    parser.add_argument('--alert-volume', type=float, help='Alert if volume exceeds this value')
    parser.add_argument('--alert-price', type=float, help='Alert if price exceeds this value')
    parser.add_argument('--portfolio', type=str, help='Path to portfolio CSV file (columns: coin,amount)')
    parser.add_argument('--detect-spikes', action='store_true', help='Detect volume spikes (20rage)')
    parser.add_argument('--correlation', action='store_true', help='Calculate price-volume correlation')
    parser.add_argument('--market-data', action='store_true', help='Show market data (cap, rank, etc.)')
    parser.add_argument('--sentiment', action='store_true', help='Show social sentiment analysis')
    parser.add_argument('--technical', action='store_true', help='Show technical indicators (RSI, MACD)')
    parser.add_argument('--arbitrage', action='store_true', help='Detect arbitrage opportunities')
    parser.add_argument('--dominance', action='store_true', help='Show market dominance data')
    parser.add_argument('--live', action='store_true', help='Stream real-time price/volume updates (Binance only)')
    parser.add_argument('--bot', action='store_true', help='Start automated trading bot (DEMO MODE)')
    parser.add_argument('--bot-strategy', type=str, choices=['volume_spike', 'rsi', 'price_alerts', 'all'], default='all', help='Trading strategy to use')
    args = parser.parse_args()

    if args.bot:
        if not args.coin:
            print("Error: --coin is required when using --bot")
            return
        
        print(f"Starting trading bot for {args.coin} in DEMO MODE")
        print("WARNING: This is for educational purposes only. No real money will be traded.")
        
        config = create_strategy_config()
        
        # Customize strategy based on user preference
        if args.bot_strategy == 'volume_spike':
            config['rsi_enabled'] = False
            config['price_alerts_enabled'] = False
        elif args.bot_strategy == 'rsi':
            config['volume_spike_enabled'] = False
            config['price_alerts_enabled'] = False
        elif args.bot_strategy == 'price_alerts':
            config['volume_spike_enabled'] = False
            config['rsi_enabled'] = False
        
        bot = TradingBot(config, demo_mode=True)
        
        try:
            bot.start(args.coin)
        except KeyboardInterrupt:
            bot.stop()
        return

    if args.live:
        symbol = args.coin if args.coin else 'BTC'
        asyncio.run(binance_live_stream(symbol))
        return

    if args.dominance:
        print('Market Dominance Analysis:')
        dominance = fetch_market_dominance()
        if dominance:
            print('Top 10 cryptocurrencies by market dominance:')
            for i, (coin, percentage) in enumerate(list(dominance.items())[:10]):
                print(f'  {i+1}. {coin}: {percentage:.2f}%')
        return

    if args.portfolio:
        portfolio = load_portfolio(args.portfolio)
        print('Portfolio Tracking:')
        total_value = 0
        total_volumes = {'binance': 0, 'coinbase': 0, 'kraken': 0, 'kucoin': 0, 'okx': 0, 'bybit': 0}
        for entry in portfolio:
            coin = entry['coin']
            amount = entry['amount']
            symbol = coin.upper()
            price = fetch_price(coin)
            volumes = fetch_all_volumes(symbol)
            value = price * amount if price else 0
            print(f'{symbol}: {amount} coins, Price: {price if price else "N/A"} USD, Value: {value:,.2f} USD')
            for ex in total_volumes:
                vol = volumes[ex]
                if vol:
                    total_volumes[ex] += vol * amount
            total_value += value
        print(f'Total Portfolio Value: {total_value:,.2f} USD')
        print('Total Portfolio Volume (amount-weighted):')
        for ex, vol in total_volumes.items():
            print(f'  {ex}: {vol:,.2f}')
        return

    if args.coin:
        coins = [args.coin]
    else:
        coins = fetch_coingecko_trending()[:args.top]

    rows = []
    for coin in coins:
        symbol = coin.upper()
        volumes = fetch_all_volumes(symbol)
        price = fetch_price(coin)
        print(f'{symbol} (Price: {price if price else "N/A"} USD):')
        
        if args.exchange == 'all':
            for ex, vol in volumes.items():
                print(f'  {ex}: {vol if vol else "Not found"}')
                row = {'coin': symbol, 'exchange': ex, 'price_usd': price, 'volume': vol}
                if args.trend:
                    hist = fetch_all_historical(symbol)
                    row['trend'] = hist[ex]
                rows.append(row)
                # Alert logic
                if args.alert_volume and vol and vol > args.alert_volume:
                    print(f'  ALERT: {symbol} on {ex} volume {vol:,.2f} exceeds {args.alert_volume}')
                if args.alert_price and price and price > args.alert_price:
                    print(f'  ALERT: {symbol} price {price:,.2f} exceeds {args.alert_price}')
        else:
            vol = volumes.get(args.exchange)
            print(f'  {args.exchange}: {vol if vol else "Not found"}')
            row = {'coin': symbol, 'exchange': args.exchange, 'price_usd': price, 'volume': vol}
            if args.trend:
                hist = fetch_all_historical(symbol)
                row['trend'] = hist.get(args.exchange)
            rows.append(row)
            # Alert logic
            if args.alert_volume and vol and vol > args.alert_volume:
                print(f'  ALERT: {symbol} on {args.exchange} volume {vol:,.2f} exceeds {args.alert_volume}')
            if args.alert_price and price and price > args.alert_price:
                print(f'  ALERT: {symbol} price {price:,.2f} exceeds {args.alert_price}')
        
        # Market data
        if args.market_data:
            market_data = fetch_market_data(coin)
            if market_data:
                print(f'  Market Cap: ${market_data["market_cap"]:,.2f}')
                print(f'  24h Change: {market_data["price_change_24h"]:.2f}%')
                print(f'  Market Rank: #{market_data["market_cap_rank"]}')
                print(f'  Circulating Supply: {market_data["circulating_supply"]:,.0f}')
                print(f'  ATH: ${market_data["ath"]:,.2f} ({market_data["ath_change_percentage"]:.2f}% ATH)')
        
        # Sentiment analysis
        if args.sentiment:
            sentiment = fetch_social_sentiment(coin)
            print(f'  Sentiment Score: {sentiment:0.3f}')
            if sentiment > 0.5:
                print('  Sentiment: Very Positive')
            elif sentiment > 0:
                print('  Sentiment: Positive')
            elif sentiment > -0.5:
                print('  Sentiment: Negative')
            else:
                print('  Sentiment: Very Negative')
        
        # Arbitrage detection
        if args.arbitrage:
            arbitrage = detect_arbitrage_opportunities(symbol)
            if arbitrage:
                for opp in arbitrage:
                    print(f'  ARBITRAGE: Buy on {opp["buy_exchange"]} at ${opp["buy_price"]:.2f}, sell on {opp["sell_exchange"]} at ${opp["sell_price"]:.2f} ({opp["spread_percentage"]:.2f}% spread)')
            else:
                print('  No significant arbitrage opportunities detected')
        
        if args.trend:
            hist = fetch_all_historical(symbol)
            print('  7-day volume trend:')
            if args.exchange == 'all':
                for ex, vols in hist.items():
                    print(f'    {ex}: {vols}')
                    if args.detect_spikes and vols:
                        is_spike, ratio = detect_volume_spike(vols)
                        if is_spike:
                            print(f'      SPIKE DETECTED! Current volume is {ratio:.2f}x average')
                    
                    # Technical indicators
                    if args.technical and vols:
                        rsi = calculate_rsi(vols)
                        if rsi:
                            print(f'      RSI: {rsi:.2f}')
                        
                        macd, signal, hist_macd = calculate_macd(vols)
                        if macd:
                            print(f'      MACD: {macd:.2f}, Signal: {signal:.2f}, Histogram: {hist_macd:.2f}')
            else:
                vols = hist.get(args.exchange)
                print(f'    {args.exchange}: {vols}')
                if args.detect_spikes and vols:
                    is_spike, ratio = detect_volume_spike(vols)
                    if is_spike:
                        print(f'      SPIKE DETECTED! Current volume is {ratio:.2f}x average')
                
                # Technical indicators
                if args.technical and vols:
                    rsi = calculate_rsi(vols)
                    if rsi:
                        print(f'      RSI: {rsi:.2f}')
                    
                    macd, signal, hist_macd = calculate_macd(vols)
                    if macd:
                        print(f'      MACD: {macd:.2f}, Signal: {signal:.2f}, Histogram: {hist_macd:.2f}')
        
        if args.correlation:
            price_history = fetch_price_history(coin)
            hist = fetch_all_historical(symbol)
            if args.exchange == 'all':
                for ex, vols in hist.items():
                    if price_history and vols and len(price_history) == len(vols):
                        correlation = calculate_price_volume_correlation(price_history, vols)
                        print(f'    {ex} price-volume correlation: {correlation:0.3f}')
            else:
                vols = hist.get(args.exchange)
                if price_history and vols and len(price_history) == len(vols):
                    correlation = calculate_price_volume_correlation(price_history, vols)
                    print(f'    {args.exchange} price-volume correlation: {correlation:.3f}')
    
    # Export to CSV
    if args.export_csv:
        with open(args.export_csv, 'w', newline='') as csvfile:
            fieldnames = ['coin', 'exchange', 'price_usd', 'volume', 'trend'] if args.trend else ['coin', 'exchange', 'price_usd', 'volume']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f'Exported results to {args.export_csv}')

if __name__ == '__main__':
    main() 