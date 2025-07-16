import argparse
from fetch_volume import fetch_coingecko_trending, fetch_binance_volume

def main():
    parser = argparse.ArgumentParser(description='Crypto Trading Volume CLI')
    parser.add_argument('--top', type=int, default=7, help='Number of trending coins to display')
    args = parser.parse_args()

    trending = fetch_coingecko_trending()[:args.top]
    print(f'Top {args.top} trending coins:')
    for coin in trending:
        symbol = coin.upper()
        volume = fetch_binance_volume(symbol)
        if volume:
            print(f'{symbol}: {volume:,.2f} USDT')
        else:
            print(f'{symbol}: Not found on Binance')

if __name__ == '__main__':
    main() 