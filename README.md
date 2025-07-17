# crypto-trading-volume

This project provides real-time monitoring and analysis of trending cryptocurrencies' trading volumes across major exchange platforms. It is designed to help both exchange operators and individual traders make informed decisions by identifying market trends, unusual activity, and potential trading opportunities.

## Features
- Real-time tracking of trading volumes for top cryptocurrencies
- Aggregation of data from multiple exchange platforms (Binance, Coinbase, Kraken)
- Trend analysis and visualization tools with moving averages
- Alerts for significant volume changes or unusual activity
- Customizable watchlists for specific coins or exchanges
- Portfolio tracking with value and volume-weighted analysis
- CSV export functionality
- Mobile-friendly web dashboard with user authentication
- API rate limiting and caching for improved performance

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
docker run -p 50000pto-trading-volume

# Access the dashboard at http://localhost:50anual Installation

### Prerequisites
- Python 30.9 or higher
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
   python cli.py --top 5   ```

## Usage

### Web Dashboard
1. Start the application and navigate to `http://localhost:50ogin with username: `user`, password: `pass`3t a coin, exchange, and enable features like trends or alerts
4. Upload a portfolio CSV file (columns: `coin,amount`) for portfolio tracking

### Command Line Interface

#### Basic Usage
```bash
# Show top7nding coins
python cli.py

# Show top5nding coins
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
python cli.py --alert-volume 10000# Set price alerts
python cli.py --alert-price 50000

# Export results to CSV
python cli.py --export-csv results.csv

# Portfolio tracking
python cli.py --portfolio my_portfolio.csv
```

#### Portfolio CSV Format
Create a CSV file with columns `coin` and `amount`:
```csv
coin,amount
bitcoin,0.5thereum,2.0
solana,10.0
```

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

#### Heroku1Create a `Procfile`:
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
- CoinGecko:50calls/minute
- Binance: 1200 requests/minute
- Coinbase: 3 requests/second
- Kraken: 15 requests/10 seconds

## Troubleshooting

### Common Issues
1PI Errors**: Check your internet connection and API availability2 **Port Already in Use**: Change the port in docker-compose.yml or use a different port3 **Login Issues**: Default credentials are `user`/`pass` - change these for production

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
