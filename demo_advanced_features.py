#!/usr/bin/env python3
"""
Advanced Crypto Trading Features Demo
Showcases all the new AI, ML, and advanced trading capabilities
"""

import asyncio
import time
import json
from datetime import datetime
import requests

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"🚀 {title}")
    print("="*60)

def print_section(title):
    """Print a formatted section"""
    print(f"\n📋 {title}")
    print("-" * 40)

def demo_ml_predictions():
    """Demo machine learning predictions"""
    print_header("Machine Learning Price Predictions")
    
    try:
        from ml_predictions import CryptoPricePredictor
        
        print("🧠 Training ensemble ML models...")
        predictor = CryptoPricePredictor()
        
        # Train models for multiple coins
        coins = ['bitcoin', 'ethereum']
        for coin in coins:
            print(f"\n📊 Training models for {coin.upper()}...")
            success = predictor.train_models(coin, days=90)
            
            if success:
                print(f"✅ Models trained successfully for {coin.upper()}")
                
                # Make prediction
                prediction = predictor.predict_price(coin)
                if prediction:
                    print(f"💰 Current Price: ${prediction['current_price']:,.2f}")
                    print(f"🔮 Predicted Price: ${prediction['predicted_price']:,.2f}")
                    print(f"📈 Predicted Change: {prediction['predicted_change']:+.2%}")
                    
                    confidence = predictor.get_prediction_confidence(coin)
                    print(f"🎯 Confidence: {confidence:.1%}")
                    
                    # Show individual model predictions
                    print("\nIndividual Model Predictions:")
                    for model, price in prediction['individual_predictions'].items():
                        change = (price - prediction['current_price']) / prediction['current_price']
                        print(f"  {model:15}: ${price:10,.2f} ({change:+.2%})")
                
                # Save models
                predictor.save_models(coin)
                print(f"💾 Models saved for {coin.upper()}")
            else:
                print(f"❌ Failed to train models for {coin.upper()}")
                
    except Exception as e:
        print(f"❌ Error in ML predictions demo: {e}")

def demo_advanced_backtesting():
    """Demo advanced backtesting"""
    print_header("Advanced Backtesting System")
    
    try:
        from advanced_backtest import AdvancedBacktester
        
        print("📊 Running comprehensive backtest...")
        backtester = AdvancedBacktester(initial_capital=10000)
        
        # Run backtest for Bitcoin
        results = backtester.run_comprehensive_backtest('bitcoin', days=60)
        
        if results:
            print("✅ Backtest completed successfully!")
            
            print("\n📈 Strategy Performance Summary:")
            print("-" * 60)
            print(f"{'Strategy':<25} {'Return':<10} {'Final Value':<12} {'Trades':<8}")
            print("-" * 60)
            
            for strategy_name, result in results.items():
                return_pct = result['total_return'] * 100
                final_value = result['final_value']
                trades = result['num_trades']
                
                print(f"{strategy_name:<25} {return_pct:>8.2f}% ${final_value:>10,.0f} {trades:>6}")
            
            # Find best and worst strategies
            best_strategy = max(results.items(), key=lambda x: x[1]['total_return'])
            worst_strategy = min(results.items(), key=lambda x: x[1]['total_return'])
            
            print("-" * 60)
            print(f"🏆 Best Strategy: {best_strategy[0]} ({best_strategy[1]['total_return']:.2%})")
            print(f"📉 Worst Strategy: {worst_strategy[0]} ({worst_strategy[1]['total_return']:.2%})")
            
            # Show detailed results for best strategy
            print(f"\n📊 Detailed Results for {best_strategy[0]}:")
            best_result = best_strategy[1]
            print(f"  Total Return: {best_result['total_return']:.2%}")
            print(f"  Final Portfolio Value: ${best_result['final_value']:,.2f}")
            print(f"  Total Trades: {best_result['num_trades']}")
            print(f"  Buy Trades: {best_result['buy_trades']}")
            print(f"  Sell Trades: {best_result['sell_trades']}")
            
        else:
            print("❌ Backtest failed")
            
    except Exception as e:
        print(f"❌ Error in backtesting demo: {e}")

def demo_enhanced_trading_bot():
    """Demo enhanced trading bot"""
    print_header("Enhanced AI Trading Bot")
    
    try:
        from trading_bot import AdvancedTradingBot, create_advanced_strategy_config
        
        print("🤖 Initializing advanced trading bot...")
        
        # Create advanced configuration
        config = create_advanced_strategy_config()
        print("⚙️  Advanced Configuration:")
        for key, value in config.items():
            if key != 'risk_management':
                print(f"  {key}: {value}")
        
        print("🛡️  Risk Management Settings:")
        for key, value in config['risk_management'].items():
            print(f"  {key}: {value}")
        
        # Create bot instance
        bot = AdvancedTradingBot(config, demo_mode=True)
        print(f"\n💰 Initial Portfolio Value: ${bot.get_portfolio_value():,.2f}")
        
        # Test risk management
        can_trade, reason = bot.check_risk_limits()
        print(f"🛡️  Risk Check: {reason}")
        
        # Test ML model training
        print("\n🧠 Training ML model for Bitcoin...")
        success = bot.train_ml_model('bitcoin')
        if success:
            print("✅ ML model trained successfully")
            
            # Test prediction
            prediction = bot.predict_price_direction('bitcoin')
            if prediction is not None:
                print(f"🔮 Price Direction Prediction: {prediction:.3f}")
                confidence = abs(prediction - 0.5) * 2
                print(f"🎯 Confidence: {confidence:.1%}")
                
                # Simulate a trade
                if prediction > 0.6:  # Strong buy signal
                    position_size = bot.calculate_position_size('bitcoin', confidence)
                    current_price = 45000  # Mock price
                    buy_amount = position_size / current_price
                    print(f"📈 BUY Signal: {buy_amount:.4f} BTC (${position_size:,.2f})")
                elif prediction < 0.4:  # Strong sell signal
                    print("📉 SELL Signal detected")
                else:
                    print("⏸️  HOLD Signal - no clear direction")
        else:
            print("❌ ML model training failed")
        
        # Test position sizing
        print("\n📏 Position Sizing Examples:")
        for confidence in [0.3, 0.5, 0.7, 0.9]:
            position_size = bot.calculate_position_size('bitcoin', confidence)
            print(f"  {confidence*100:3.0f}% confidence: ${position_size:,.2f}")
        
        # Test performance metrics
        metrics = bot.get_performance_metrics()
        print(f"\n📊 Performance Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error in trading bot demo: {e}")

def demo_sentiment_analysis():
    """Demo enhanced sentiment analysis"""
    print_header("Comprehensive Sentiment Analysis")
    
    try:
        from fetch_volume import fetch_market_sentiment_analysis
        
        # Test with multiple coins
        coins = ['bitcoin', 'ethereum', 'cardano', 'solana']
        
        print("😊 Analyzing market sentiment for multiple coins...")
        
        for coin in coins:
            print(f"\n📊 {coin.upper()} Sentiment Analysis:")
            sentiment = fetch_market_sentiment_analysis(coin)
            
            if sentiment:
                composite_score = sentiment['composite_score']
                
                # Determine sentiment category
                if composite_score > 0.3:
                    category = "🟢 Bullish"
                    emoji = "📈"
                elif composite_score < -0.3:
                    category = "🔴 Bearish"
                    emoji = "📉"
                else:
                    category = "🟡 Neutral"
                    emoji = "➡️"
                
                print(f"  {emoji} Overall Sentiment: {category}")
                print(f"  📊 Composite Score: {composite_score:.3f}")
                print(f"  📰 News Sentiment: {sentiment['news_sentiment']:.3f}")
                print(f"  📈 RSI Sentiment: {sentiment['rsi_sentiment']:.3f}")
                print(f"  📊 MACD Sentiment: {sentiment['macd_sentiment']:.3f}")
                print(f"  📊 Volume Sentiment: {sentiment['volume_sentiment']:.3f}")
                
                # Show news breakdown
                if 'news_breakdown' in sentiment:
                    news = sentiment['news_breakdown']
                    print(f"  📰 News: {news['positive']} positive, {news['negative']} negative, {news['neutral']} neutral")
            else:
                print(f"  ❌ Failed to get sentiment for {coin}")
                
    except Exception as e:
        print(f"❌ Error in sentiment analysis demo: {e}")

def demo_web_dashboard():
    """Demo web dashboard features"""
    print_header("Web Dashboard Features")
    
    base_url = "http://localhost:5001"
    
    print("🌐 Testing web dashboard features...")
    
    # Test if server is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Main dashboard is running")
        else:
            print(f"⚠️  Main dashboard returned status {response.status_code}")
    except requests.exceptions.RequestException:
        print("❌ Web dashboard is not running")
        print("💡 Start the dashboard with: python web_dashboard.py")
        return
    
    # Test sentiment API
    try:
        response = requests.get(f"{base_url}/api/sentiment/bitcoin", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Sentiment API working")
            print(f"  Bitcoin sentiment score: {data.get('composite_score', 'N/A')}")
        else:
            print(f"⚠️  Sentiment API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Sentiment API error: {e}")
    
    # Test batch sentiment API
    try:
        data = {"coins": ["bitcoin", "ethereum", "cardano"]}
        response = requests.post(f"{base_url}/api/sentiment/batch", 
                               json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print("✅ Batch sentiment API working")
            print(f"  Analyzed {len(result.get('results', {}))} coins")
        else:
            print(f"⚠️  Batch sentiment API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Batch sentiment API error: {e}")
    
    print("\n🌐 Available Dashboard URLs:")
    print(f"  📊 Main Dashboard: {base_url}/")
    print(f"  📈 Analytics: {base_url}/analytics")
    print(f"  😊 Sentiment Analysis: {base_url}/sentiment")
    print(f"  🧠 ML Predictions: {base_url}/ml-predictions")
    print(f"  📊 Advanced Backtesting: {base_url}/advanced-backtest")

def demo_cli_features():
    """Demo CLI features"""
    print_header("Command Line Interface Features")
    
    print("💻 Testing CLI enhancements...")
    
    try:
        import subprocess
        
        # Test sentiment analysis CLI
        print("\n📊 Testing sentiment analysis CLI...")
        result = subprocess.run([
            'python', 'cli.py', '--coin', 'bitcoin', '--sentiment'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Sentiment CLI working")
            print("Output preview:")
            lines = result.stdout.split('\n')[:8]
            for line in lines:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"❌ Sentiment CLI failed: {result.stderr}")
        
        # Test combined analysis CLI
        print("\n🔄 Testing combined analysis CLI...")
        result = subprocess.run([
            'python', 'cli.py', '--coin', 'ethereum', '--trend', '--sentiment'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Combined analysis CLI working")
        else:
            print(f"❌ Combined analysis CLI failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error testing CLI: {e}")

def demo_data_analysis():
    """Demo data analysis features"""
    print_header("Data Analysis & Technical Indicators")
    
    try:
        from fetch_volume import (
            fetch_all_historical, fetch_all_volumes,
            calculate_rsi, calculate_macd, detect_volume_spike
        )
        
        print("📊 Loading and analyzing market data...")
        
        # Test historical data
        print("\n📈 Historical Data Analysis:")
        hist_data = fetch_all_historical('bitcoin', days=30)
        if hist_data and hist_data.get('binance'):
            prices = hist_data['binance']
            print(f"  ✅ Loaded {len(prices)} price data points")
            
            # Calculate technical indicators
            rsi = calculate_rsi(prices)
            macd, signal, hist_macd = calculate_macd(prices)
            
            print(f"  📊 RSI: {rsi:.2f}")
            print(f"  📈 MACD: {macd:.3f}")
            print(f"  📉 Signal: {signal:.3f}")
            
            # Test volume spike detection
            is_spike, ratio = detect_volume_spike(prices)
            print(f"  📊 Volume Spike: {'Yes' if is_spike else 'No'} (ratio: {ratio:.2f}x)")
        else:
            print("  ❌ Failed to load historical data")
        
        # Test volume data
        print("\n📊 Volume Data Analysis:")
        volumes = fetch_all_volumes('bitcoin')
        if volumes:
            print("  ✅ Volume data loaded successfully")
            total_volume = sum(v for v in volumes.values() if v)
            print(f"  📊 Total Volume: {total_volume:,.0f}")
            
            for exchange, volume in volumes.items():
                if volume:
                    percentage = (volume / total_volume) * 100
                    print(f"    {exchange}: {volume:,.0f} ({percentage:.1f}%)")
        else:
            print("  ❌ Failed to load volume data")
            
    except Exception as e:
        print(f"❌ Error in data analysis demo: {e}")

def main():
    """Run the complete advanced features demo"""
    print("🚀 Advanced Crypto Trading Features Demo")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis demo showcases all the advanced AI, ML, and trading features!")
    
    # Run all demos
    demo_data_analysis()
    demo_sentiment_analysis()
    demo_ml_predictions()
    demo_advanced_backtesting()
    demo_enhanced_trading_bot()
    demo_cli_features()
    demo_web_dashboard()
    
    print_header("Demo Complete!")
    print("🎉 All advanced features have been demonstrated!")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n📋 Summary of Advanced Features Demonstrated:")
    print("✅ Machine Learning Price Predictions with Ensemble Models")
    print("✅ Advanced Backtesting with Multiple Trading Strategies")
    print("✅ Enhanced AI Trading Bot with Risk Management")
    print("✅ Comprehensive Sentiment Analysis")
    print("✅ Technical Indicators (RSI, MACD, Volume Analysis)")
    print("✅ Real-time Data Processing and Analysis")
    print("✅ Web Dashboard with Multiple Advanced Views")
    print("✅ Enhanced CLI with AI Features")
    print("✅ API Endpoints for Programmatic Access")
    
    print("\n🚀 Next Steps:")
    print("1. Start the web dashboard: python web_dashboard.py")
    print("2. Visit http://localhost:5001 for the main dashboard")
    print("3. Explore the advanced features:")
    print("   - /ml-predictions for AI price predictions")
    print("   - /advanced-backtest for strategy testing")
    print("   - /sentiment for real-time sentiment analysis")
    print("   - /analytics for enhanced analytics")
    print("4. Run tests: python test_advanced_features.py")
    print("5. Use CLI: python cli.py --coin bitcoin --sentiment --ml-predict")

if __name__ == "__main__":
    main() 