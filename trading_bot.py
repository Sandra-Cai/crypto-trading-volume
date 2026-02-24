import asyncio
import json
import time
import requests
import numpy as np
from datetime import datetime, timedelta
from fetch_volume import (
    fetch_all_volumes, detect_volume_spike, calculate_rsi, 
    fetch_market_sentiment_analysis, fetch_price_history,
    fetch_all_historical, calculate_macd
)
import websockets
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import os

def fetch_price(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    return data.get(symbol.lower(), {}).get('usd')

class AdvancedTradingBot:
    def __init__(self, strategy_config, demo_mode=True):
        self.strategy_config = strategy_config
        self.demo_mode = demo_mode
        self.portfolio = {'cash': 10000}  # Starting with $10,000
        self.trade_history = []
        self.is_running = False
        self.ml_model = None
        self.scaler = StandardScaler()
        self.risk_metrics = {
            'max_position_size': 0.1,  # Max 10% of portfolio in single position
            'stop_loss': 0.05,  # 5% stop loss
            'take_profit': 0.15,  # 15% take profit
            'max_daily_loss': 0.02,  # Max 2% daily loss
            'max_open_positions': 5
        }
        self.daily_pnl = 0
        self.last_reset = datetime.now().date()
        
    def log_trade(self, action, coin, amount, price, reason, confidence=None):
        trade = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'coin': coin,
            'amount': amount,
            'price': price,
            'reason': reason,
            'confidence': confidence,
            'portfolio_value': self.get_portfolio_value(),
            'daily_pnl': self.daily_pnl
        }
        self.trade_history.append(trade)
        print(f"[{trade['timestamp']}][{trade['action']}]: {amount} {trade['coin']} @ ${price:0.2f} due to {trade['reason']} (confidence: {confidence:.2f})")
    
    def get_portfolio_value(self):
        total = self.portfolio['cash']
        for coin, amount in self.portfolio.items():
            if coin != 'cash':
                price = fetch_price(coin)
                if price:
                    total += amount * price
        return total
    
    def calculate_position_size(self, coin, confidence):
        """Calculate position size based on risk management rules"""
        portfolio_value = self.get_portfolio_value()
        
        # Base position size (2% of portfolio)
        base_size = portfolio_value * 0.02
        
        # Adjust based on confidence
        confidence_multiplier = min(confidence, 0.8) / 0.5  # Scale 0.5-0.8 confidence to 1.0-1.6
        
        # Apply risk limits
        max_size = portfolio_value * self.risk_metrics['max_position_size']
        position_size = min(base_size * confidence_multiplier, max_size)
        
        return position_size
    
    def check_risk_limits(self):
        """Check if we should stop trading due to risk limits"""
        # Reset daily PnL if it's a new day
        if datetime.now().date() > self.last_reset:
            self.daily_pnl = 0
            self.last_reset = datetime.now().date()
        
        # Check daily loss limit
        if self.daily_pnl < -self.get_portfolio_value() * self.risk_metrics['max_daily_loss']:
            return False, "Daily loss limit exceeded"
        
        # Check number of open positions
        open_positions = len([k for k in self.portfolio.keys() if k != 'cash' and self.portfolio[k] > 0])
        if open_positions >= self.risk_metrics['max_open_positions']:
            return False, "Maximum open positions reached"
        
        return True, "OK"
    
    def execute_buy(self, coin, amount, price, reason, confidence=None):
        cost = amount * price
        if self.portfolio['cash'] >= cost:
            self.portfolio['cash'] -= cost
            if coin not in self.portfolio:
                self.portfolio[coin] = 0
            self.portfolio[coin] += amount
            self.log_trade('BUY', coin, amount, price, reason, confidence)
            return True
        return False
    
    def execute_sell(self, coin, amount, price, reason, confidence=None):
        if coin in self.portfolio and self.portfolio[coin] >= amount:
            self.portfolio[coin] -= amount
            self.portfolio['cash'] += amount * price
            self.log_trade('SELL', coin, amount, price, reason, confidence)
            return True
        return False
    
    def train_ml_model(self, coin, days=30):
        """Train a machine learning model for price prediction"""
        try:
            # Get historical data
            hist_data = fetch_all_historical(coin.upper(), days=days)
            if not hist_data or not hist_data.get('binance'):
                return False
            
            prices = hist_data['binance']
            if len(prices) < 20:
                return False
            
            # Create features
            features = []
            targets = []
            
            for i in range(20, len(prices) - 1):
                # Price features
                price_window = prices[i-20:i]
                features.append([
                    np.mean(price_window),  # Average price
                    np.std(price_window),   # Price volatility
                    prices[i] / prices[i-1] - 1,  # Price change
                    prices[i] / prices[i-5] - 1,  # 5-day change
                    prices[i] / prices[i-10] - 1, # 10-day change
                    prices[i] / prices[i-20] - 1, # 20-day change
                    np.max(price_window) / prices[i] - 1,  # Distance from high
                    prices[i] / np.min(price_window) - 1,  # Distance from low
                ])
                targets.append(1 if prices[i+1] > prices[i] else 0)
            
            if len(features) < 10:
                return False
            
            # Train model
            X = np.array(features)
            y = np.array(targets)
            
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            
            self.ml_model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.ml_model.fit(X_scaled, y)
            
            print(f"ML model trained for {coin} with {len(features)} samples")
            return True
            
        except Exception as e:
            print(f"Error training ML model for {coin}: {e}")
            return False
    
    def predict_price_direction(self, coin):
        """Predict price direction using ML model"""
        if not self.ml_model:
            return None
        
        try:
            # Get recent price data
            hist_data = fetch_all_historical(coin.upper(), days=30)
            if not hist_data or not hist_data.get('binance'):
                return None
            
            prices = hist_data['binance']
            if len(prices) < 20:
                return None
            
            # Create features for prediction
            price_window = prices[-20:]
            features = [[
                np.mean(price_window),
                np.std(price_window),
                prices[-1] / prices[-2] - 1,
                prices[-1] / prices[-6] - 1,
                prices[-1] / prices[-11] - 1,
                prices[-1] / prices[-20] - 1,
                np.max(price_window) / prices[-1] - 1,
                prices[-1] / np.min(price_window) - 1,
            ]]
            
            X_scaled = self.scaler.transform(features)
            prediction = self.ml_model.predict(X_scaled)[0]
            
            return prediction
            
        except Exception as e:
            print(f"Error predicting price direction for {coin}: {e}")
            return None
    
    async def run_advanced_strategy(self, coin):
        """Execute advanced trading strategy with ML and sentiment analysis"""
        while self.is_running:
            try:
                # Check risk limits
                can_trade, reason = self.check_risk_limits()
                if not can_trade:
                    print(f"Risk limit check failed: {reason}")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue
                
                # Get current market data
                volumes = fetch_all_volumes(coin.upper())
                current_price = fetch_price(coin)
                
                if not current_price:
                    await asyncio.sleep(60)
                    continue
                
                # Strategy 1: ML-based prediction
                if self.strategy_config.get('ml_enabled', False):
                    if not self.ml_model:
                        self.train_ml_model(coin)
                    
                    if self.ml_model:
                        prediction = self.predict_price_direction(coin)
                        if prediction is not None:
                            confidence = abs(prediction - 0.5) * 2  # Convert to 0-1 scale
                            
                            if prediction > 0.6:  # Strong buy signal
                                position_size = self.calculate_position_size(coin, confidence)
                                buy_amount = position_size / current_price
                                if self.execute_buy(coin, buy_amount, current_price, f"ML prediction: {prediction:.3f}", confidence):
                                    print(f"ML BUY: {buy_amount:.4f} {coin} (confidence: {confidence:.2f})")
                            
                            elif prediction < 0.4:  # Strong sell signal
                                if coin in self.portfolio and self.portfolio[coin] > 0:
                                    sell_amount = self.portfolio[coin] * 0.5  # Sell half position
                                    if self.execute_sell(coin, sell_amount, current_price, f"ML prediction: {prediction:.3f}", confidence):
                                        print(f"ML SELL: {sell_amount:.4f} {coin} (confidence: {confidence:.2f})")
                
                # Strategy 2: Sentiment-based trading
                if self.strategy_config.get('sentiment_enabled', False):
                    sentiment = fetch_market_sentiment_analysis(coin)
                    if sentiment:
                        sentiment_score = sentiment['composite_score']
                        confidence = abs(sentiment_score)
                        
                        if sentiment_score > 0.4:  # Strong bullish sentiment
                            position_size = self.calculate_position_size(coin, confidence)
                            buy_amount = position_size / current_price
                            if self.execute_buy(coin, buy_amount, current_price, f"Bullish sentiment: {sentiment_score:.3f}", confidence):
                                print(f"SENTIMENT BUY: {buy_amount:.4f} {coin} (sentiment: {sentiment_score:.3f})")
                        
                        elif sentiment_score < -0.4:  # Strong bearish sentiment
                            if coin in self.portfolio and self.portfolio[coin] > 0:
                                sell_amount = self.portfolio[coin] * 0.5
                                if self.execute_sell(coin, sell_amount, current_price, f"Bearish sentiment: {sentiment_score:.3f}", confidence):
                                    print(f"SENTIMENT SELL: {sell_amount:.4f} {coin} (sentiment: {sentiment_score:.3f})")
                
                # Strategy 3: Volume spike detection
                if self.strategy_config.get('volume_spike_enabled', False):
                    for exchange, volume in volumes.items():
                        if volume:
                            hist = fetch_all_historical(coin.upper())
                            if hist and hist.get(exchange):
                                is_spike, ratio = detect_volume_spike(hist[exchange])
                                if is_spike and ratio > self.strategy_config.get('spike_threshold', 2.0):
                                    position_size = self.calculate_position_size(coin, min(ratio / 10, 0.8))
                                    buy_amount = position_size / current_price
                                    if self.execute_buy(coin, buy_amount, current_price, f"Volume spike on {exchange} ({ratio:.2f}x)", ratio / 10):
                                        print(f"VOLUME BUY: {buy_amount:.4f} {coin} (spike: {ratio:.2f}x)")
                
                # Strategy 4: RSI-based trading
                if self.strategy_config.get('rsi_enabled', False):
                    hist = fetch_all_historical(coin.upper())
                    if hist and hist.get('binance'):
                        rsi = calculate_rsi(hist['binance'])
                        if rsi:
                            if rsi < 30:  # Oversold
                                position_size = self.calculate_position_size(coin, 0.7)
                                buy_amount = position_size / current_price
                                if self.execute_buy(coin, buy_amount, current_price, f"RSI oversold: {rsi:.1f}", 0.7):
                                    print(f"RSI BUY: {buy_amount:.4f} {coin} (RSI: {rsi:.1f})")
                            
                            elif rsi > 70:  # Overbought
                                if coin in self.portfolio and self.portfolio[coin] > 0:
                                    sell_amount = self.portfolio[coin] * 0.5
                                    if self.execute_sell(coin, sell_amount, current_price, f"RSI overbought: {rsi:.1f}", 0.7):
                                        print(f"RSI SELL: {sell_amount:.4f} {coin} (RSI: {rsi:.1f})")
                
                # Strategy 5: MACD-based trading
                if self.strategy_config.get('macd_enabled', False):
                    hist = fetch_all_historical(coin.upper())
                    if hist and hist.get('binance'):
                        macd, signal, hist_macd = calculate_macd(hist['binance'])
                        if macd and signal:
                            if macd > signal and macd > 0:  # Bullish crossover
                                position_size = self.calculate_position_size(coin, 0.6)
                                buy_amount = position_size / current_price
                                if self.execute_buy(coin, buy_amount, current_price, f"MACD bullish: {macd:.3f}", 0.6):
                                    print(f"MACD BUY: {buy_amount:.4f} {coin} (MACD: {macd:.3f})")
                            
                            elif macd < signal and macd < 0:  # Bearish crossover
                                if coin in self.portfolio and self.portfolio[coin] > 0:
                                    sell_amount = self.portfolio[coin] * 0.5
                                    if self.execute_sell(coin, sell_amount, current_price, f"MACD bearish: {macd:.3f}", 0.6):
                                        print(f"MACD SELL: {sell_amount:.4f} {coin} (MACD: {macd:.3f})")
                
                # Update daily PnL
                self.update_daily_pnl()
                
                # Wait before next iteration
                await asyncio.sleep(self.strategy_config.get('check_interval', 300))  # 5 minutes default
                
            except Exception as e:
                print(f"Error in trading strategy: {e}")
                await asyncio.sleep(60)
    
    def update_daily_pnl(self):
        """Update daily profit/loss"""
        current_value = self.get_portfolio_value()
        if hasattr(self, 'last_portfolio_value'):
            self.daily_pnl += current_value - self.last_portfolio_value
        self.last_portfolio_value = current_value
    
    def get_performance_metrics(self):
        """Get trading performance metrics"""
        if not self.trade_history:
            return {}
        
        total_trades = len(self.trade_history)
        winning_trades = len([t for t in self.trade_history if t['action'] == 'SELL'])
        total_pnl = self.get_portfolio_value() - 10000  # Starting value
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': total_pnl,
            'total_return': (total_pnl / 10000) * 100,
            'daily_pnl': self.daily_pnl,
            'portfolio_value': self.get_portfolio_value()
        }
    
    def start(self, coin):
        """Start the trading bot"""
        self.is_running = True
        print(f"Starting advanced trading bot for {coin.upper()}")
        print(f"Initial portfolio value: ${self.get_portfolio_value():.2f}")
        asyncio.create_task(self.run_advanced_strategy(coin))
    
    def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        print("Trading bot stopped")
        
        # Print final performance
        metrics = self.get_performance_metrics()
        print(f"Final portfolio value: ${metrics['portfolio_value']:.2f}")
        print(f"Total return: {metrics['total_return']:.2f}%")
        print(f"Total trades: {metrics['total_trades']}")

def create_advanced_strategy_config():
    """Create configuration for advanced trading strategies"""
    return {
        'ml_enabled': True,
        'sentiment_enabled': True,
        'volume_spike_enabled': True,
        'rsi_enabled': True,
        'macd_enabled': True,
        'spike_threshold': 2.0,
        'check_interval': 300,  # 5 minutes
        'risk_management': {
            'max_position_size': 0.1,
            'stop_loss': 0.05,
            'take_profit': 0.15,
            'max_daily_loss': 0.02,
            'max_open_positions': 5
        }
    }


# Backward-compatible alias
create_strategy_config = create_advanced_strategy_config


# Legacy TradingBot class for backward compatibility
class TradingBot(AdvancedTradingBot):
    def __init__(self, strategy_config, demo_mode=True):
        super().__init__(strategy_config, demo_mode)
    
    async def run_strategy(self, coin):
        """Legacy method - redirects to advanced strategy"""
        await self.run_advanced_strategy(coin)

if __name__ == "__main__":
    # Example usage
    config = create_advanced_strategy_config()
    bot = TradingBot(config, demo_mode=True)
    
    try:
        bot.start('bitcoin')
    except KeyboardInterrupt:
        bot.stop() 