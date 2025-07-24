#!/usr/bin/env python3
"""
Demo script for new crypto trading volume features
Showcases the enhanced analytics and sentiment analysis capabilities
"""

import time
from fetch_volume import (
    fetch_market_sentiment_analysis, 
    fetch_price_history,
    fetch_coingecko_trending,
    fetch_all_volumes
)

def demo_sentiment_analysis():
    """Demonstrate sentiment analysis for multiple coins"""
    print("🎭 DEMO: Market Sentiment Analysis")
    print("=" * 50)
    
    # Get trending coins
    trending = fetch_coingecko_trending()[:3]  # Top 3 trending
    
    for coin in trending:
        print(f"\n📊 Analyzing sentiment for {coin.upper()}...")
        
        sentiment = fetch_market_sentiment_analysis(coin)
        if sentiment:
            print(f"   Symbol: {sentiment['symbol']}")
            print(f"   Overall Sentiment: {sentiment['overall_sentiment'].upper()}")
            print(f"   Composite Score: {sentiment['composite_score']:.3f}")
            
            components = sentiment['components']
            print(f"   Components:")
            print(f"     News: {components['news_sentiment']:.3f}")
            print(f"     RSI: {components['rsi_sentiment']:.3f}")
            print(f"     MACD: {components['macd_sentiment']:.3f}")
            print(f"     Volume: {components['volume_sentiment']:.3f}")
            
            news = sentiment['news_breakdown']
            print(f"   News: {news['positive']} positive, {news['negative']} negative, {news['neutral']} neutral")
        else:
            print(f"   ❌ Could not analyze sentiment for {coin}")
        
        time.sleep(1)  # Be nice to APIs

def demo_analytics_data():
    """Demonstrate enhanced analytics data"""
    print("\n📈 DEMO: Enhanced Analytics Data")
    print("=" * 50)
    
    # Get trending coins
    trending = fetch_coingecko_trending()[:3]
    
    for coin in trending:
        print(f"\n📊 Analytics for {coin.upper()}...")
        
        # Get price history
        prices = fetch_price_history(coin, days=7)
        if prices:
            print(f"   Price History: {len(prices)} data points")
            print(f"   Current Price: ${prices[-1]:.2f}")
            print(f"   Price Change: {((prices[-1] - prices[0]) / prices[0] * 100):.2f}%")
        
        # Get volume data
        volumes = fetch_all_volumes(coin.upper())
        if volumes:
            total_volume = sum(v for v in volumes.values() if v)
            print(f"   Total 24h Volume: ${total_volume:,.0f}")
            print(f"   Top Exchange: {max(volumes.items(), key=lambda x: x[1] or 0)[0]}")
        
        time.sleep(1)

def demo_api_endpoints():
    """Demonstrate new API endpoints"""
    print("\n🔌 DEMO: New API Endpoints")
    print("=" * 50)
    
    print("Available endpoints:")
    print("  GET /api/sentiment/<coin> - Get sentiment analysis for a coin")
    print("  POST /api/sentiment/batch - Get sentiment for multiple coins")
    print("  GET /analytics - Enhanced analytics dashboard")
    print("  GET /sentiment - Real-time sentiment dashboard")
    
    print("\nExample API calls:")
    print("  curl http://localhost:5000/api/sentiment/bitcoin")
    print("  curl -X POST http://localhost:5000/api/sentiment/batch \\")
    print("       -H 'Content-Type: application/json' \\")
    print("       -d '{\"coins\": [\"bitcoin\", \"ethereum\"]}'")

def demo_web_dashboards():
    """Demonstrate web dashboard features"""
    print("\n🌐 DEMO: Web Dashboard Features")
    print("=" * 50)
    
    print("New Dashboard Pages:")
    print("  1. /analytics - Enhanced Analytics Dashboard")
    print("     • Real-time volume charts")
    print("     • Market dominance metrics")
    print("     • 7-day trend analysis")
    print("     • Auto-refreshing data")
    
    print("\n  2. /sentiment - Market Sentiment Dashboard")
    print("     • Real-time sentiment analysis")
    print("     • Component breakdown (News, RSI, MACD, Volume)")
    print("     • Sentiment comparison charts")
    print("     • Color-coded sentiment indicators")
    
    print("\n  3. Enhanced Main Dashboard")
    print("     • Improved navigation")
    print("     • Better data visualization")
    print("     • Real-time updates")

def demo_cli_features():
    """Demonstrate new CLI features"""
    print("\n💻 DEMO: New CLI Features")
    print("=" * 50)
    
    print("New CLI Commands:")
    print("  python cli.py --coin bitcoin --sentiment")
    print("    • Comprehensive sentiment analysis")
    print("    • Component breakdown")
    print("    • News sentiment analysis")
    print("    • Technical indicator sentiment")
    
    print("\nCombined Analysis:")
    print("  python cli.py --coin bitcoin --trend --sentiment --correlation")
    print("    • Volume trends")
    print("    • Sentiment analysis")
    print("    • Price-volume correlation")
    print("    • All in one command")

def main():
    """Run the demo"""
    print("🚀 Crypto Trading Volume - New Features Demo")
    print("=" * 60)
    print("This demo showcases the new analytics and sentiment analysis features")
    print("that have been added to the crypto trading volume platform.")
    print("=" * 60)
    
    try:
        demo_sentiment_analysis()
        demo_analytics_data()
        demo_api_endpoints()
        demo_web_dashboards()
        demo_cli_features()
        
        print("\n" + "=" * 60)
        print("🎉 Demo Complete!")
        print("=" * 60)
        print("To try these features:")
        print("1. Start the server: python web_dashboard.py")
        print("2. Visit http://localhost:5000")
        print("3. Login with user/pass")
        print("4. Navigate to /analytics and /sentiment")
        print("5. Try CLI: python cli.py --coin bitcoin --sentiment")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("Make sure the required dependencies are installed and APIs are accessible")

if __name__ == "__main__":
    main() 