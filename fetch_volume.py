import requests

def fetch_coingecko_trending():
    url = 'https://api.coingecko.com/api/v3/search/trending'
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    trending = [item['item']['id'] for item in data['coins']]
    return trending

def fetch_binance_volume(symbol):
    url = f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}USDT'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return float(data.get('quoteVolume', 0))

def main():
    print('Fetching trending coins from CoinGecko...')
    trending = fetch_coingecko_trending()
    print('Trending coins:', trending)
    print('\nFetching 24h trading volume from Binance:')
    for coin in trending:
        symbol = coin.upper()
        volume = fetch_binance_volume(symbol)
        if volume:
            print(f'{symbol}: {volume:,.2f} USDT')
        else:
            print(f'{symbol}: Not found on Binance')

if __name__ == '__main__':
    main() 