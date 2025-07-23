import asyncio
import json
import time
from datetime import datetime
from fetch_volume import fetch_all_volumes, detect_volume_spike, calculate_rsi
import websockets

class TradingBot:
    def __init__(self, strategy_config, demo_mode=True):
        self.strategy_config = strategy_config
        self.demo_mode = demo_mode
        self.portfolio = {'cash': 1000}  # Starting with $10
        self.trade_history = []
        self.is_running = False
        
    def log_trade(self, action, coin, amount, price, reason):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'coin': coin,
            'amount': amount,
            'price': price,
            'reason': reason,
            'portfolio_value': self.get_portfolio_value()
        }
        self.trade_history.append(trade)
        print(f"[{trade['timestamp']}][{trade['action']}]: {amount} {trade['coin']} @ ${price:0.2f} due to {trade['reason']}")
    
    def get_portfolio_value(self):
        total = self.portfolio['cash']
        for coin, amount in self.portfolio.items():
            if coin != 'cash':
                price = fetch_price(coin)
                if price:
                    total += amount * price
        return total
    
    def execute_buy(self, coin, amount, price, reason):
        cost = amount * price
        if self.portfolio['cash'] >= cost:
            self.portfolio['cash'] -= cost
            if coin not in self.portfolio:
                self.portfolio[coin] = 0
            self.portfolio[coin] += amount
            self.log_trade('BUY', coin, amount, price, reason)
            return True
        return False  
    def execute_sell(self, coin, amount, price, reason):
        if coin in self.portfolio and self.portfolio[coin] >= amount:
            self.portfolio[coin] -= amount
            self.portfolio['cash'] += amount * price
            self.log_trade('SELL', coin, amount, price, reason)
            return True
        return False
    
    async def run_strategy(self, coin):
        """Execute a trading strategy for a specific coin"""
        while self.is_running:
            try:
                # Get current market data
                volumes = fetch_all_volumes(coin.upper())
                current_price = fetch_price(coin)
                
                if not current_price:
                    await asyncio.sleep(60)
                    continue
                
                # Strategy 1: Volume Spike Detection
                if self.strategy_config.get('volume_spike_enabled', False):
                    for exchange, volume in volumes.items():
                        if volume:
                            # Get historical data for spike detection
                            from fetch_volume import fetch_all_historical
                            hist = fetch_all_historical(coin.upper())
                            if hist and hist.get(exchange):
                                is_spike, ratio = detect_volume_spike(hist[exchange])
                                if is_spike and ratio > self.strategy_config.get('spike_threshold', 2.0):
                                    # Buy on volume spike
                                    buy_amount = self.strategy_config.get('buy_amount', 100) / current_price
                                    if self.execute_buy(coin, buy_amount, current_price, f"Volume spike detected on {exchange} ({ratio:0.2f})"):
                                        print(f"Bought {buy_amount:0.4f} {coin} due to volume spike")
                
                # Strategy 2: RSI-based trading
                if self.strategy_config.get('rsi_enabled', False):
                    from fetch_volume import fetch_all_historical
                    hist = fetch_all_historical(coin.upper())
                    if hist and hist.get('binance'):
                        rsi = calculate_rsi(hist['binance'])
                        if rsi:
                            if rsi < 30:  # Oversold
                                buy_amount = self.strategy_config.get('buy_amount', 100) / current_price
                                if self.execute_buy(coin, buy_amount, current_price, f"RSI oversold ({rsi:.2f})"):
                                    print(f"Bought {buy_amount:0.4f} {coin} due to RSI oversold")
                            elif rsi > 70 and coin in self.portfolio and self.portfolio[coin] > 0:
                                sell_amount = self.portfolio[coin] * 0.5
                                if self.execute_sell(coin, sell_amount, current_price, f"RSI overbought ({rsi:.2f})"):
                                    print(f"Sold {sell_amount:0.4f} {coin} due to RSI overbought")
                
                # Strategy 3: Price-based stop loss/take profit
                if self.strategy_config.get('price_alerts_enabled', False):
                    if coin in self.portfolio and self.portfolio[coin] > 0:
                        # Check stop loss
                        stop_loss = self.strategy_config.get('stop_loss_percentage', 0.05)
                        take_profit = self.strategy_config.get('take_profit_percentage', 0.10)
                        
                        # Calculate average purchase price (simplified)
                        avg_price = self.strategy_config.get('avg_purchase_price', current_price)                 
                        if current_price <= avg_price * (1 - stop_loss):
                            # Stop loss triggered
                            sell_amount = self.portfolio[coin]
                            if self.execute_sell(coin, sell_amount, current_price, f"Stop loss triggered ({stop_loss*100}%)"):
                                print(f"Sold {sell_amount:0.4f} {coin} due to stop loss")
                        elif current_price >= avg_price * (1 + take_profit): # Take profit triggered
                            sell_amount = self.portfolio[coin] * 0.5
                            if self.execute_sell(coin, sell_amount, current_price, f"Take profit triggered ({take_profit*100}%)"):
                                print(f"Sold {sell_amount:0.4f} {coin} due to take profit")
                
                # Print portfolio status
                portfolio_value = self.get_portfolio_value()
                print(f"Portfolio Value: ${portfolio_value:.2f} | Cash: ${self.portfolio['cash']:.2f}")
                
                await asyncio.sleep(self.strategy_config.get('check_interval', 60)) # Check every minute
                
            except Exception as e:
                print(f"Error in trading strategy: {e}")
                await asyncio.sleep(60)
    
    def start(self, coin):
        """Start the trading bot"""
        self.is_running = True
        print(f"Starting trading bot for {coin} in {'DEMO' if self.demo_mode else 'LIVE'} mode")
        print(f"Initial portfolio value: ${self.get_portfolio_value():.2f}")
        asyncio.run(self.run_strategy(coin))
    
    def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        print("Trading bot stopped")
        print(f"Final portfolio value: ${self.get_portfolio_value():.2f}")
        print(f"Total trades: {len(self.trade_history)}")

def create_strategy_config():
    """Create a default strategy configuration"""
    return {
        'volume_spike_enabled': True,
        'spike_threshold': 2.0,
        'rsi_enabled': True,
        'price_alerts_enabled': True,
        'stop_loss_percentage': 0.05, # 5%
        'take_profit_percentage': 0.10,  # 10%
        'buy_amount': 100,  # $100 per trade
        'check_interval': 60,  # Check every 60 seconds
        'avg_purchase_price': None  # Will be set dynamically
    }

if __name__ == "__main__":
    # Example usage
    config = create_strategy_config()
    bot = TradingBot(config, demo_mode=True)
    
    try:
        bot.start('bitcoin')
    except KeyboardInterrupt:
        bot.stop() 