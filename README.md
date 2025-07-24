# crypto-trading-volume

This project provides real-time monitoring and analysis of trending cryptocurrencies' trading volumes across major exchange platforms. It is designed to help both exchange operators and individual traders make informed decisions by identifying market trends, unusual activity, and potential trading opportunities.

## Features
- Real-time tracking of trading volumes for top cryptocurrencies
- Aggregation of data from 6 major exchanges (Binance, Coinbase, Kraken, KuCoin, OKX, Bybit)
- Advanced trend analysis with moving averages and volume spike detection
- Price-volume correlation analysis for market insights
- Alerts for significant volume changes or unusual activity
- Customizable watchlists for specific coins or exchanges
- Portfolio tracking with value and volume-weighted analysis
- CSV export functionality
- Mobile-friendly web dashboard with user authentication
- API rate limiting and caching for improved performance
- Volume spike detection (20x average threshold)
- Statistical correlation analysis between price and volume movements
- **NEW: Enhanced Analytics Dashboard** with real-time charts and market metrics
- **NEW: Real-time Market Sentiment Analysis** combining news, social, technical indicators, and volume data
- **NEW: Sentiment API endpoints** for programmatic access to sentiment data

## Quick Start with Docker

### Using Docker Compose (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd crypto-trading-volume

# Start the application
docker-compose up -d

# Access the dashboard at http://localhost:5000
# Login with username: user, password: pass
```

### Using Docker directly
```bash
# Build the image
docker build -t crypto-trading-volume .

# Run the container
docker run -p 5000:5000 crypto-trading-volume

# Access the dashboard at http://localhost:5000
```

## Manual Installation

### Prerequisites
- Python 3.9 or higher
- pip

### Installation Steps
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd crypto-trading-volume
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   # Start the web dashboard
   python web_dashboard.py
   
   # Or use the CLI
   python cli.py --top 5
   ```

## Usage

### Web Dashboard
1. Start the application and navigate to `http://localhost:5000`
2. Login with username: `user`, password: `pass`
3. Select a coin, exchange, and enable features like trends, spike detection, or correlation analysis
4. Upload a portfolio CSV file (columns: `coin,amount`) for portfolio tracking
5. **NEW: Visit `/analytics` for enhanced analytics dashboard**
6. **NEW: Visit `/sentiment` for real-time sentiment analysis**

### Command Line Interface

#### Basic Usage
```bash
# Show top 7 trending coins
python cli.py

# Show top 5 trending coins
python cli.py --top 5

# Query specific coin
python cli.py --coin bitcoin

# Query specific exchange
python cli.py --exchange binance

# Show 7-day historical trends
python cli.py --trend
```

#### Advanced Features
```bash
# Set volume alerts
python cli.py --alert-volume 1000000

# Set price alerts
python cli.py --alert-price 50000

# Export results to CSV
python cli.py --export-csv results.csv

# Portfolio tracking
python cli.py --portfolio my_portfolio.csv

# Detect volume spikes (20x average)
python cli.py --detect-spikes

# Calculate price-volume correlation
python cli.py --correlation

# NEW: Comprehensive sentiment analysis
python cli.py --coin bitcoin --sentiment

# Combine multiple features
python cli.py --coin bitcoin --trend --detect-spikes --correlation --sentiment --export-csv analysis.csv
```

#### Portfolio CSV Format
Create a CSV file with columns `coin` and `amount`:
```csv
coin,amount
bitcoin,0.5
ethereum,2.0
solana,10.0
```

## Advanced Analytics

### Volume Spike Detection
The system automatically detects when trading volume is significantly higher than the 7-day average:
- Threshold: 20x the average volume
- Helps identify unusual market activity
- Available in both CLI and dashboard

### Price-Volume Correlation
Calculate the statistical correlation between price and volume changes:
- Range: -1 to +1 (negative = inverse correlation, positive = direct correlation)
- Helps understand market dynamics
- Available for all supported exchanges

### Multi-Exchange Analysis
Compare trading volumes across 6 major exchanges:
- Binance, Coinbase, Kraken, KuCoin, OKX, Bybit
- Aggregated data for comprehensive market view
- Exchange-specific trend analysis

### **NEW: Market Sentiment Analysis**
Comprehensive sentiment analysis combining multiple data sources:
- **News Sentiment**: Analyzes recent news headlines for positive/negative sentiment
- **Social Sentiment**: Tracks social media sentiment trends
- **Technical Indicators**: RSI and MACD sentiment analysis
- **Volume Sentiment**: Volume trend analysis
- **Composite Score**: Weighted combination of all sentiment factors
- **Real-time Updates**: Auto-refreshing sentiment dashboard

#### Sentiment Components:
- **News Sentiment (30% weight)**: Based on recent news headlines
- **RSI Sentiment (20% weight)**: Technical indicator sentiment
- **MACD Sentiment (20% weight)**: Moving average convergence divergence
- **Volume Sentiment (30% weight)**: Volume trend analysis

#### Sentiment Categories:
- **Bullish**: Composite score > 0.3
- **Bearish**: Composite score < -0.3
- **Neutral**: Score between -0.3 and 0.3

## API Endpoints

### New Sentiment Analysis Endpoints

#### Get Sentiment for Single Coin
```bash
GET /api/sentiment/bitcoin
```

Response:
```json
{
  "symbol": "BITCOIN",
  "composite_score": 0.45,
  "overall_sentiment": "bullish",
  "components": {
    "news_sentiment": 0.6,
    "rsi_sentiment": 0.5,
    "macd_sentiment": 0.3,
    "volume_sentiment": 0.4
  },
  "news_breakdown": {
    "positive": 8,
    "negative": 2,
    "neutral": 5,
    "total": 15
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

#### Batch Sentiment Analysis
```bash
POST /api/sentiment/batch
Content-Type: application/json

{
  "coins": ["bitcoin", "ethereum", "solana"]
}
```

Response:
```json
{
  "results": {
    "BITCOIN": { /* sentiment data */ },
    "ETHEREUM": { /* sentiment data */ },
    "SOLANA": { /* sentiment data */ }
  },
  "total_analyzed": 3,
  "timestamp": "2024-01-15T10:30:00"
}
```

## Background Tasking (Celery)

The platform uses Celery with Redis for background jobs such as periodic data refresh and alerting.

### Running with Docker Compose

Docker Compose will automatically start Redis and a Celery worker:

```bash
docker-compose up -d
```

### Manual Usage

1. Start Redis:
   ```bash
   docker run -p 6379:6379 redis:7
   ```
2. Start the Celery worker:
   ```bash
   CELERY_BROKER_URL=redis://localhost:6379/0 CELERY_RESULT_BACKEND=redis://localhost:6379/0 celery -A tasks worker --loglevel=info
   ```
3. (Optional) Start the Celery beat scheduler for periodic jobs:
   ```bash
   celery -A tasks beat --loglevel=info
   ```

### What does it do?
- Every 10 minutes, trending coins and their volumes are refreshed in the background (see `tasks.py`).
- You can add more background jobs for alerting, analytics, etc.

## Deployment

### Docker Deployment
The application is containerized and ready for deployment:

```bash
# Build and run with docker-compose
docker-compose up -d

# Or build and run manually
docker build -t crypto-trading-volume .
docker run -d -p 5000:5000 --name crypto-app crypto-trading-volume
```

### Cloud Deployment
The application can be deployed to various cloud platforms:

#### Heroku
1. Create a `Procfile`:
   ```
   web: python web_dashboard.py
   ```
2. Deploy using Heroku CLI or GitHub integration

#### AWS/GCP/Azure
- Use the provided Dockerfile with container services
- Set environment variables for production settings
- Configure load balancers and auto-scaling as needed

## Configuration

### Environment Variables
- `FLASK_ENV`: Set to `production` for production deployment
- `FLASK_APP`: Set to `web_dashboard.py` (default)

### Security Notes
- Change the default username/password in `web_dashboard.py` for production
- Use a strong secret key for Flask sessions
- Consider using environment variables for sensitive configuration

## API Rate Limits
The application includes caching to handle API rate limits:
- CoinGecko: 50 calls/minute
- Binance: 1200 requests/minute
- Coinbase: 3 requests/second
- Kraken: 15 requests/10 seconds
- KuCoin: 1800 requests/minute
- OKX: 20 requests/2 seconds
- Bybit: 120 requests/minute

## Troubleshooting

### Common Issues
1. **API Errors**: Check your internet connection and API availability
2. **Port Already in Use**: Change the port in docker-compose.yml or use a different port
3. **Login Issues**: Default credentials are `user`/`pass` - change these for production

### Logs
```bash
# Docker logs
docker-compose logs crypto-trading-volume

# Manual installation logs
# Check console output for error messages
```

## Contributing
Contributions are welcome! Please open issues or submit pull requests for new features, bug fixes, or improvements.

## License
This project is licensed under the MIT License.

## Performance
- All exchange and market data fetching is now fully asynchronous, powered by [aiohttp](https://docs.aiohttp.org/), for high performance and scalability.
- **NEW: Sentiment analysis is cached for 5 minutes to improve performance**

## Requirements
- Python 3.8+
- aiohttp
- requests
- flask
- plotly
- (see requirements.txt for full list)

## Installation
```bash
pip install -r requirements.txt
```

## Public API

The platform exposes a REST API for third-party integrations and power users.

### Endpoints

- `GET /api/trending` — Get trending coins (from CoinGecko)
- `GET /api/volumes/<coin>` — Get 24h trading volumes for a coin across all exchanges
- `GET /api/historical/<coin>` — Get historical volume data for a coin
- `GET /api/market_data/<coin>` — Get market data for a coin (market cap, price change, etc.)
- `GET /api/onchain/<coin>` — Get on-chain stats for a coin
- `GET /api/whale_alerts/<coin>` — Get recent whale transactions for a coin
- `GET /api/portfolio` — Get user portfolio (favorites); requires API key
- **NEW: `GET /api/sentiment/<coin>` — Get comprehensive sentiment analysis for a coin**
- **NEW: `POST /api/sentiment/batch` — Get sentiment analysis for multiple coins**

### Authentication

- Endpoints under `/api/portfolio` require an API key.
- Pass your API key in the `X-API-KEY` header.
- (For demo, the API key is your password; in production, use a dedicated API key field.)

### Example Usage

#### Get trending coins
```bash
curl https://yourdomain/api/trending
```

#### Get volumes for Bitcoin
```bash
curl https://yourdomain/api/volumes/bitcoin
```

#### Get sentiment analysis for Bitcoin
```bash
curl https://yourdomain/api/sentiment/bitcoin
```

#### Get user portfolio (with API key)
```bash
curl -H "X-API-KEY: <your-api-key>" https://yourdomain/api/portfolio
```

### Response Format
All endpoints return JSON. Example:
```json
{
  "coin": "bitcoin",
  "volumes": {
    "binance": 123456.78,
    "coinbase": 23456.12,
    ...
  }
}
```

### Rate Limits
- Please respect fair use. For high-volume or commercial use, contact the maintainers.

## Email Alerts Setup

To enable real email delivery for alerts and summaries, set the following environment variables:

- `SMTP_HOST` — SMTP server hostname (e.g., smtp.gmail.com)
- `SMTP_PORT` — SMTP server port (usually 587)
- `SMTP_USER` — SMTP username (your email address or SMTP user)
- `SMTP_PASSWORD` — SMTP password or app password
- `SMTP_FROM` — (optional) From address for emails (defaults to SMTP_USER)

Example (in your shell or Docker Compose):
```sh
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your@email.com
export SMTP_PASSWORD=yourpassword
export SMTP_FROM=alerts@yourdomain.com
```

If these are not set, emails will not be sent (but will be logged to the console for testing).
