#!/usr/bin/env python3
"""
Test script for new crypto trading volume features
Tests the new analytics dashboard and sentiment analysis functionality
"""

import requests
import json
import time
from fetch_volume import fetch_market_sentiment_analysis, fetch_price_history

def test_sentiment_analysis():
    """Test the new sentiment analysis functionality"""
    print("🧪 Testing Sentiment Analysis...")
    
    # Test sentiment analysis for Bitcoin
    try:
        sentiment = fetch_market_sentiment_analysis('bitcoin')
        if sentiment:
            print("✅ Sentiment analysis working!")
            print(f"   Symbol: {sentiment['symbol']}")
            print(f"   Overall Sentiment: {sentiment['overall_sentiment']}")
            print(f"   Composite Score: {sentiment['composite_score']:.3f}")
            print(f"   Components: {sentiment['components']}")
            return True
        else:
            print("❌ Sentiment analysis returned None")
            return False
    except Exception as e:
        print(f"❌ Sentiment analysis failed: {e}")
        return False

def test_price_history():
    """Test the price history functionality"""
    print("🧪 Testing Price History...")
    
    try:
        prices = fetch_price_history('bitcoin', days=7)
        if prices and len(prices) > 0:
            print("✅ Price history working!")
            print(f"   Retrieved {len(prices)} price points")
            print(f"   Latest price: ${prices[-1]:.2f}")
            return True
        else:
            print("❌ Price history returned empty")
            return False
    except Exception as e:
        print(f"❌ Price history failed: {e}")
        return False

def test_web_server():
    """Test if the web server is running and new endpoints work"""
    print("🧪 Testing Web Server Endpoints...")
    
    base_url = "http://localhost:5000"
    
    # Test if server is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Web server is running!")
        else:
            print(f"❌ Web server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Web server is not running (start with: python web_dashboard.py)")
        return False
    
    # Test sentiment API endpoint
    try:
        response = requests.get(f"{base_url}/api/sentiment/bitcoin", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Sentiment API endpoint working!")
            print(f"   Sentiment: {data.get('overall_sentiment', 'N/A')}")
            return True
        else:
            print(f"❌ Sentiment API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Sentiment API failed: {e}")
        return False

def test_cli_sentiment():
    """Test CLI sentiment functionality"""
    print("🧪 Testing CLI Sentiment Command...")
    
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, 'cli.py', '--coin', 'bitcoin', '--sentiment'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and 'Sentiment Analysis' in result.stdout:
            print("✅ CLI sentiment command working!")
            return True
        else:
            print(f"❌ CLI sentiment command failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI sentiment test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing New Crypto Trading Volume Features")
    print("=" * 50)
    
    tests = [
        ("Price History", test_price_history),
        ("Sentiment Analysis", test_sentiment_analysis),
        ("CLI Sentiment", test_cli_sentiment),
        ("Web Server", test_web_server),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! New features are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print("\n📝 Next Steps:")
    print("1. Start the web server: python web_dashboard.py")
    print("2. Visit http://localhost:5000 and login (user/pass)")
    print("3. Navigate to /analytics for enhanced analytics")
    print("4. Navigate to /sentiment for sentiment analysis")
    print("5. Use CLI: python cli.py --coin bitcoin --sentiment")

if __name__ == "__main__":
    main() 