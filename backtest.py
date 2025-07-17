from fetch_volume import fetch_all_historical, fetch_price_history, calculate_rsi

def backtest_volume_spike(coin, days=30, spike_threshold=2.0, buy_amount=100):
    hist = fetch_all_historical(coin.upper(), days)
    price_hist = fetch_price_history(coin, days)
    if not hist or not price_hist:
        print('Not enough data for backtest.')
        return
    cash = 1000
    position = 0
    trades = []
    for i in range(2, len(price_hist)):
        vols = [h[i] for h in hist.values() if len(h) > i]
        if not vols:
            continue
        avg_vol = sum(vols[:-1]) / len(vols[:-1]) if len(vols) > 1 else 0
        if avg_vol == 0:
            continue
        spike = vols[-1] / avg_vol
        price = price_hist[i]
        if spike > spike_threshold and cash >= buy_amount:
            qty = buy_amount / price
            position += qty
            cash -= buy_amount
            trades.append(('BUY', i, price, qty))
        elif position > 0 and spike < 1.0:
            cash += position * price
            trades.append(('SELL', i, price, position))
            position = 0
    final_value = cash + position * price_hist[-1]
    returns = (final_value - 1000) / 1000 * 100
    print(f'Backtest (Volume Spike): {coin.upper()}')
    print(f'Trades: {len(trades)}, Final Value: ${final_value:.2f}, Return: {returns:.2f}%')
    for t in trades:
        print(f'{t[0]} at day {t[1]}: price={t[2]:.2f}, qty={t[3]:.4f}')

def backtest_rsi(coin, days=30, buy_amount=100):
    price_hist = fetch_price_history(coin, days)
    if not price_hist or len(price_hist) < 15:
        print('Not enough data for backtest.')
        return
    cash = 1000
    position = 0
    trades = []
    for i in range(15, len(price_hist)):
        rsi = calculate_rsi(price_hist[max(0, i-14):i+1])
        price = price_hist[i]
        if rsi and rsi < 30 and cash >= buy_amount:
            qty = buy_amount / price
            position += qty
            cash -= buy_amount
            trades.append(('BUY', i, price, qty))
        elif rsi and rsi > 70 and position > 0:
            cash += position * price
            trades.append(('SELL', i, price, position))
            position = 0
    final_value = cash + position * price_hist[-1]
    returns = (final_value - 1000) / 1000 * 100
    print(f'Backtest (RSI): {coin.upper()}')
    print(f'Trades: {len(trades)}, Final Value: ${final_value:.2f}, Return: {returns:.2f}%')
    for t in trades:
        print(f'{t[0]} at day {t[1]}: price={t[2]:.2f}, qty={t[3]:.4f}') 