import argparse
from fetch_volume import fetch_coingecko_trending, fetch_all_volumes, fetch_all_historical
import requests
import csv

def fetch_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get(symbol.lower(), {}).get('usd')

def load_portfolio(filename):
    portfolio = []
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            portfolio.append({'coin': row['coin'], 'amount': float(row['amount'])})
    return portfolio

def main():
    parser = argparse.ArgumentParser(description='Crypto Trading Volume CLI')
    parser.add_argument('--top', type=int, default=7, help='Number of trending coins to display')
    parser.add_argument('--coin', type=str, help='Specify a coin (e.g., bitcoin)')
    parser.add_argument('--exchange', type=str, choices=['binance', 'coinbase', 'kraken', 'all'], default='all', help='Exchange to query')
    parser.add_argument('--trend', action='store_true', help='Show 7-day historical volume trend')
    parser.add_argument('--export-csv', type=str, help='Export results to CSV file')
    parser.add_argument('--alert-volume', type=float, help='Alert if volume exceeds this value')
    parser.add_argument('--alert-price', type=float, help='Alert if price exceeds this value')
    parser.add_argument('--portfolio', type=str, help='Path to portfolio CSV file (columns: coin,amount)')
    args = parser.parse_args()

    if args.portfolio:
        portfolio = load_portfolio(args.portfolio)
        print('Portfolio Tracking:')
        total_value = 0
        total_volumes = {'binance': 0, 'coinbase': 0, 'kraken': 0}
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
        if args.trend:
            hist = fetch_all_historical(symbol)
            print('  7-day volume trend:')
            if args.exchange == 'all':
                for ex, vols in hist.items():
                    print(f'    {ex}: {vols}')
            else:
                print(f'    {args.exchange}: {hist.get(args.exchange)}')
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