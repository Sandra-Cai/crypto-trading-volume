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

def main():
    parser = argparse.ArgumentParser(description='Crypto Trading Volume CLI')
    parser.add_argument('--top', type=int, default=7, help='Number of trending coins to display')
    parser.add_argument('--coin', type=str, help='Specify a coin (e.g., bitcoin)')
    parser.add_argument('--exchange', type=str, choices=['binance', 'coinbase', 'kraken', 'all'], default='all', help='Exchange to query')
    parser.add_argument('--trend', action='store_true', help='Show 7-day historical volume trend')
    parser.add_argument('--export-csv', type=str, help='Export results to CSV file')
    args = parser.parse_args()

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
        else:
            vol = volumes.get(args.exchange)
            print(f'  {args.exchange}: {vol if vol else "Not found"}')
            row = {'coin': symbol, 'exchange': args.exchange, 'price_usd': price, 'volume': vol}
            if args.trend:
                hist = fetch_all_historical(symbol)
                row['trend'] = hist.get(args.exchange)
            rows.append(row)
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