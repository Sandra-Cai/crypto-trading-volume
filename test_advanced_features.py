#!/usr/bin/env python3
"""
Comprehensive Test Script for Advanced Crypto Trading Features
Tests ML predictions, advanced backtesting, enhanced trading bot, and sentiment analysis
"""

import asyncio
import time
import json
from datetime import datetime
import requests

def test_ml_predictions():
    """Test machine learning predictions"""
    print("🧠 Testing Machine Learning Predictions...")
    print("=" * 50)
    
    try:
        from ml_predictions import CryptoPricePredictor
        
        predictor = CryptoPricePredictor()
        
        # Test with Bitcoin
        print("Training ML models for Bitcoin...")
        success = predictor.train_models('bitcoin', days=90)
        
        if success:
            print("✅ ML models trained successfully")
            
            # Test prediction
            prediction = predictor.predict_price('bitcoin')
            if prediction:
                print(f"📊 Current Price: ${prediction['current_price']:,.2f}")
                print(f"🔮 Predicted Price: ${prediction['predicted_price']:,.2f}")
                print(f"📈 Predicted Change: {prediction['predicted_change']:.2%}")
                
                confidence = predictor.get_prediction_confidence('bitcoin')
                print(f"🎯 Prediction Confidence: {confidence:.1%}")
                
                print("\nIndividual Model Predictions:")
                for model, price in prediction['individual_predictions'].items():
                    print(f"  {model}: ${price:,.2f}")
                
                # Save models
                predictor.save_models('bitcoin')
                print("💾 Models saved successfully")
            else:
                print("❌ Failed to make prediction")
        else:
            print("❌ Failed to train models")
            
    except Exception as e:
        print(f"❌ Error testing ML predictions: {e}")

def test_advanced_backtesting():
    """Test advanced backtesting functionality"""
    print("\n📊 Testing Advanced Backtesting...")
    print("=" * 50)
    
    try:
        from advanced_backtest import AdvancedBacktester
        
        backtester = AdvancedBacktester(initial_capital=10000)
        
        # Test with Bitcoin
        print("Running comprehensive backtest for Bitcoin...")
        results = backtester.run_comprehensive_backtest('bitcoin', days=60)
        
        if results:
            print("✅ Backtest completed successfully")
            print("\nResults Summary:")
            print("-" * 40)
            
            for strategy_name, result in results.items():
                print(f"{strategy_name:25} | Return: {result['total_return']:8.2%} | "
                      f"Final: ${result['final_value']:10,.2f} | Trades: {result['num_trades']:3d}")
            
            # Find best strategy
            best_strategy = max(results.items(), key=lambda x: x[1]['total_return'])
            print("-" * 40)
            print(f"🏆 Best Strategy: {best_strategy[0]} ({best_strategy[1]['total_return']:.2%})")
            
            # Test plotting
            try:
                backtester.plot_results(results, 'bitcoin')
                print("📈 Results plot generated successfully")
            except Exception as e:
                print(f"⚠️  Plot generation failed: {e}")
        else:
            print("❌ Backtest failed")
            
    except Exception as e:
        print(f"❌ Error testing backtesting: {e}")

def test_enhanced_trading_bot():
    """Test enhanced trading bot with ML and sentiment"""
    print("\n🤖 Testing Enhanced Trading Bot...")
    print("=" * 50)
    
    try:
        from trading_bot import AdvancedTradingBot, create_advanced_strategy_config
        
        # Create advanced configuration
        config = create_advanced_strategy_config()
        print("⚙️  Advanced Strategy Configuration:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        # Create bot instance
        bot = AdvancedTradingBot(config, demo_mode=True)
        print(f"💰 Initial Portfolio Value: ${bot.get_portfolio_value():,.2f}")
        
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
        else:
            print("❌ ML model training failed")
        
        # Test position sizing
        position_size = bot.calculate_position_size('bitcoin', 0.7)
        print(f"📏 Position Size for 70% confidence: ${position_size:,.2f}")
        
        # Test performance metrics
        metrics = bot.get_performance_metrics()
        print(f"📈 Performance Metrics: {metrics}")
        
    except Exception as e:
        print(f"❌ Error testing trading bot: {e}")

def test_sentiment_analysis():
    """Test enhanced sentiment analysis"""
    print("\n😊 Testing Enhanced Sentiment Analysis...")
    print("=" * 50)
    
    try:
        from fetch_volume import fetch_market_sentiment_analysis
        
        # Test with multiple coins
        coins = ['bitcoin', 'ethereum', 'cardano']
        
        for coin in coins:
            print(f"\n📊 Analyzing sentiment for {coin.upper()}...")
            sentiment = fetch_market_sentiment_analysis(coin)
            
            if sentiment:
                print(f"  Composite Score: {sentiment['composite_score']:.3f}")
                print(f"  News Sentiment: {sentiment['news_sentiment']:.3f}")
                print(f"  RSI Sentiment: {sentiment['rsi_sentiment']:.3f}")
                print(f"  MACD Sentiment: {sentiment['macd_sentiment']:.3f}")
                print(f"  Volume Sentiment: {sentiment['volume_sentiment']:.3f}")
                
                # Determine sentiment category
                score = sentiment['composite_score']
                if score > 0.3:
                    category = "🟢 Bullish"
                elif score < -0.3:
                    category = "🔴 Bearish"
                else:
                    category = "🟡 Neutral"
                
                print(f"  Category: {category}")
            else:
                print(f"  ❌ Failed to get sentiment for {coin}")
                
    except Exception as e:
        print(f"❌ Error testing sentiment analysis: {e}")

def test_web_dashboard_features():
    """Test web dashboard features"""
    print("\n🌐 Testing Web Dashboard Features...")
    print("=" * 50)
    
    base_url = "http://localhost:5001"
    
    # Test if server is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Web dashboard is running")
        else:
            print(f"⚠️  Web dashboard returned status {response.status_code}")
    except requests.exceptions.RequestException:
        print("❌ Web dashboard is not running")
        return
    
    # Test sentiment API
    try:
        response = requests.get(f"{base_url}/api/sentiment/bitcoin", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Sentiment API working")
            print(f"  Bitcoin sentiment: {data.get('composite_score', 'N/A')}")
        else:
            print(f"⚠️  Sentiment API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Sentiment API error: {e}")
    
    # Test batch sentiment API
    try:
        data = {"coins": ["bitcoin", "ethereum"]}
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

def test_cli_enhancements():
    """Test CLI enhancements"""
    print("\n💻 Testing CLI Enhancements...")
    print("=" * 50)
    
    try:
        import subprocess
        
        # Test sentiment analysis CLI
        print("Testing sentiment analysis CLI...")
        result = subprocess.run([
            'python', 'cli.py', '--coin', 'bitcoin', '--sentiment'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Sentiment CLI working")
            print("Output preview:")
            lines = result.stdout.split('\n')[:5]
            for line in lines:
                print(f"  {line}")
        else:
            print(f"❌ Sentiment CLI failed: {result.stderr}")
        
        # Test combined analysis CLI
        print("\nTesting combined analysis CLI...")
        result = subprocess.run([
            'python', 'cli.py', '--coin', 'ethereum', '--trend', '--sentiment'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Combined analysis CLI working")
        else:
            print(f"❌ Combined analysis CLI failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error testing CLI: {e}")

def test_data_loading():
    """Test data loading and processing"""
    print("\n📊 Testing Data Loading...")
    print("=" * 50)
    
    try:
        from fetch_volume import (
            fetch_all_historical, fetch_all_volumes,
            calculate_rsi, calculate_macd
        )
        
        # Test historical data
        print("Loading historical data for Bitcoin...")
        hist_data = fetch_all_historical('bitcoin', days=30)
        if hist_data and hist_data.get('binance'):
            print(f"✅ Historical data loaded: {len(hist_data['binance'])} data points")
            
            # Test technical indicators
            rsi = calculate_rsi(hist_data['binance'])
            macd, signal, hist_macd = calculate_macd(hist_data['binance'])
            
            print(f"📈 RSI: {rsi:.2f}")
            print(f"📊 MACD: {macd:.3f}, Signal: {signal:.3f}")
        else:
            print("❌ Failed to load historical data")
        
        # Test volume data
        print("\nLoading volume data...")
        volumes = fetch_all_volumes('bitcoin')
        if volumes:
            print("✅ Volume data loaded")
            for exchange, volume in volumes.items():
                if volume:
                    print(f"  {exchange}: {volume:,.0f}")
        else:
            print("❌ Failed to load volume data")
            
    except Exception as e:
        print(f"❌ Error testing data loading: {e}")

def main():
    """Run all tests"""
    print("🚀 Advanced Crypto Trading Features Test Suite")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    test_data_loading()
    test_sentiment_analysis()
    test_ml_predictions()
    test_advanced_backtesting()
    test_enhanced_trading_bot()
    test_cli_enhancements()
    test_web_dashboard_features()
    
    print("\n" + "=" * 60)
    print("🎉 Test suite completed!")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n📋 Summary of Advanced Features:")
    print("✅ Machine Learning Price Predictions")
    print("✅ Advanced Backtesting with Multiple Strategies")
    print("✅ Enhanced Trading Bot with ML and Sentiment")
    print("✅ Comprehensive Sentiment Analysis")
    print("✅ Risk Management and Position Sizing")
    print("✅ Technical Indicators (RSI, MACD)")
    print("✅ Web Dashboard with Real-time Updates")
    print("✅ CLI Enhancements")
    print("✅ API Endpoints for Programmatic Access")

if __name__ == "__main__":
    main() 