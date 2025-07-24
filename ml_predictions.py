#!/usr/bin/env python3
"""
Machine Learning Prediction Module for Crypto Price Forecasting
Uses multiple ML models and ensemble methods for price prediction
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from fetch_volume import (
    fetch_all_historical, fetch_market_sentiment_analysis,
    calculate_rsi, calculate_macd
)
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
import joblib
import os

class CryptoPricePredictor:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.model_performance = {}
        
    def prepare_features(self, df, lookback=30):
        """Prepare features for machine learning models"""
        features = []
        targets = []
        dates = []
        
        for i in range(lookback, len(df) - 1):
            # Price-based features
            price_window = df['price'].iloc[i-lookback:i]
            returns = df['returns'].iloc[i-lookback:i]
            
            feature_vector = [
                # Price statistics
                np.mean(price_window),
                np.std(price_window),
                np.min(price_window),
                np.max(price_window),
                price_window.iloc[-1] / price_window.iloc[0] - 1,  # Price change over window
                
                # Return statistics
                np.mean(returns),
                np.std(returns),
                np.sum(returns > 0) / len(returns),  # Positive return ratio
                
                # Technical indicators
                df['rsi'].iloc[i] if not np.isnan(df['rsi'].iloc[i]) else 50,
                df['macd'].iloc[i] if not np.isnan(df['macd'].iloc[i]) else 0,
                df['macd_signal'].iloc[i] if not np.isnan(df['macd_signal'].iloc[i]) else 0,
                
                # Moving averages
                df['price_ma_5'].iloc[i] if not np.isnan(df['price_ma_5'].iloc[i]) else df['price'].iloc[i],
                df['price_ma_20'].iloc[i] if not np.isnan(df['price_ma_20'].iloc[i]) else df['price'].iloc[i],
                
                # Volume features
                df['volume'].iloc[i] if not np.isnan(df['volume'].iloc[i]) else 0,
                df['volume_ma'].iloc[i] if not np.isnan(df['volume_ma'].iloc[i]) else 0,
                df['volume'].iloc[i] / df['volume_ma'].iloc[i] if not np.isnan(df['volume_ma'].iloc[i]) and df['volume_ma'].iloc[i] > 0 else 1,
                
                # Volatility
                df['volatility'].iloc[i] if not np.isnan(df['volatility'].iloc[i]) else 0,
                
                # Price momentum
                df['price'].iloc[i] / df['price'].iloc[i-1] - 1,
                df['price'].iloc[i] / df['price'].iloc[i-5] - 1,
                df['price'].iloc[i] / df['price'].iloc[i-10] - 1,
                
                # Distance from highs/lows
                (np.max(price_window) - df['price'].iloc[i]) / df['price'].iloc[i],
                (df['price'].iloc[i] - np.min(price_window)) / df['price'].iloc[i],
            ]
            
            # Remove any NaN values
            if not any(np.isnan(feature_vector)):
                features.append(feature_vector)
                targets.append(df['price'].iloc[i+1])  # Next day's price
                dates.append(df['date'].iloc[i])
        
        return np.array(features), np.array(targets), dates
    
    def train_models(self, coin, days=180):
        """Train multiple ML models for price prediction"""
        print(f"Training ML models for {coin.upper()}...")
        
        # Load and prepare data
        df = self.load_and_prepare_data(coin, days)
        if df is None:
            return False
        
        # Prepare features
        X, y, dates = self.prepare_features(df)
        if len(X) < 50:
            print("Insufficient data for training")
            return False
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Define models
        models = {
            'RandomForest': RandomForestRegressor(n_estimators=100, random_state=42),
            'GradientBoosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'LinearRegression': LinearRegression()
        }
        
        # Train each model
        for model_name, model in models.items():
            print(f"Training {model_name}...")
            
            # Scale features (except for tree-based models)
            if model_name == 'LinearRegression':
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                self.scalers[model_name] = scaler
            else:
                X_train_scaled = X_train
                X_test_scaled = X_test
            
            # Train model
            model.fit(X_train_scaled, y_train)
            self.models[model_name] = model
            
            # Make predictions
            y_pred = model.predict(X_test_scaled)
            
            # Calculate metrics
            mse = mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            self.model_performance[model_name] = {
                'mse': mse,
                'mae': mae,
                'r2': r2,
                'rmse': np.sqrt(mse)
            }
            
            # Feature importance (for tree-based models)
            if hasattr(model, 'feature_importances_'):
                self.feature_importance[model_name] = model.feature_importances_
            
            print(f"  {model_name} - R²: {r2:.3f}, RMSE: {np.sqrt(mse):.2f}")
        
        return True
    
    def load_and_prepare_data(self, coin, days):
        """Load and prepare data with technical indicators"""
        try:
            hist_data = fetch_all_historical(coin.upper(), days=days)
            if not hist_data or not hist_data.get('binance'):
                return None
            
            prices = hist_data['binance']
            dates = pd.date_range(end=datetime.now(), periods=len(prices), freq='D')
            
            df = pd.DataFrame({
                'date': dates,
                'price': prices,
                'volume': hist_data.get('binance_volume', [0] * len(prices))
            })
            
            # Calculate technical indicators
            df['returns'] = df['price'].pct_change()
            df['rsi'] = self.calculate_rsi_series(df['price'])
            df['macd'], df['macd_signal'] = self.calculate_macd_series(df['price'])
            df['volume_ma'] = df['volume'].rolling(window=7).mean()
            df['price_ma_5'] = df['price'].rolling(window=5).mean()
            df['price_ma_20'] = df['price'].rolling(window=20).mean()
            df['volatility'] = df['price'].rolling(window=10).std()
            
            return df
            
        except Exception as e:
            print(f"Error loading data: {e}")
            return None
    
    def calculate_rsi_series(self, prices, period=14):
        """Calculate RSI for a series of prices"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd_series(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD for a series of prices"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        return macd, macd_signal
    
    def predict_price(self, coin, days_ahead=1):
        """Predict future price using ensemble of models"""
        if not self.models:
            print("No trained models available. Please train models first.")
            return None
        
        # Load recent data
        df = self.load_and_prepare_data(coin, days=60)
        if df is None:
            return None
        
        # Prepare features for prediction
        X, _, _ = self.prepare_features(df)
        if len(X) == 0:
            print("Insufficient recent data for prediction")
            return None
        
        # Use most recent feature vector
        latest_features = X[-1:]
        
        # Make predictions with all models
        predictions = {}
        for model_name, model in self.models.items():
            if model_name in self.scalers:
                features_scaled = self.scalers[model_name].transform(latest_features)
            else:
                features_scaled = latest_features
            
            pred = model.predict(features_scaled)[0]
            predictions[model_name] = pred
        
        # Ensemble prediction (weighted average)
        weights = {
            'RandomForest': 0.4,
            'GradientBoosting': 0.4,
            'LinearRegression': 0.2
        }
        
        ensemble_prediction = sum(predictions[model] * weights[model] 
                                for model in predictions.keys() 
                                if model in weights)
        
        current_price = df['price'].iloc[-1]
        
        return {
            'current_price': current_price,
            'predicted_price': ensemble_prediction,
            'predicted_change': (ensemble_prediction - current_price) / current_price,
            'individual_predictions': predictions,
            'prediction_date': datetime.now() + timedelta(days=days_ahead)
        }
    
    def get_prediction_confidence(self, coin):
        """Get confidence level for predictions based on model performance"""
        if not self.model_performance:
            return 0.0
        
        # Calculate average R² score
        avg_r2 = np.mean([perf['r2'] for perf in self.model_performance.values()])
        
        # Get recent volatility
        df = self.load_and_prepare_data(coin, days=30)
        if df is not None:
            recent_volatility = df['volatility'].iloc[-1] / df['price'].iloc[-1]
            # Higher volatility = lower confidence
            volatility_factor = max(0.1, 1 - recent_volatility)
        else:
            volatility_factor = 0.5
        
        confidence = avg_r2 * volatility_factor
        return min(max(confidence, 0.0), 1.0)
    
    def save_models(self, coin):
        """Save trained models to disk"""
        if not self.models:
            print("No models to save")
            return
        
        model_dir = f"models/{coin.lower()}"
        os.makedirs(model_dir, exist_ok=True)
        
        for model_name, model in self.models.items():
            model_path = f"{model_dir}/{model_name}.joblib"
            joblib.dump(model, model_path)
            print(f"Saved {model_name} to {model_path}")
        
        # Save scalers
        for scaler_name, scaler in self.scalers.items():
            scaler_path = f"{model_dir}/{scaler_name}_scaler.joblib"
            joblib.dump(scaler, scaler_path)
            print(f"Saved {scaler_name} scaler to {scaler_path}")
        
        # Save performance metrics
        import json
        perf_path = f"{model_dir}/performance.json"
        with open(perf_path, 'w') as f:
            json.dump(self.model_performance, f, indent=2)
        print(f"Saved performance metrics to {perf_path}")
    
    def load_models(self, coin):
        """Load trained models from disk"""
        model_dir = f"models/{coin.lower()}"
        
        if not os.path.exists(model_dir):
            print(f"No saved models found for {coin}")
            return False
        
        try:
            # Load models
            for model_name in ['RandomForest', 'GradientBoosting', 'LinearRegression']:
                model_path = f"{model_dir}/{model_name}.joblib"
                if os.path.exists(model_path):
                    self.models[model_name] = joblib.load(model_path)
                    print(f"Loaded {model_name} from {model_path}")
            
            # Load scalers
            for scaler_name in ['LinearRegression']:
                scaler_path = f"{model_dir}/{scaler_name}_scaler.joblib"
                if os.path.exists(scaler_path):
                    self.scalers[scaler_name] = joblib.load(scaler_path)
                    print(f"Loaded {scaler_name} scaler from {scaler_path}")
            
            # Load performance metrics
            perf_path = f"{model_dir}/performance.json"
            if os.path.exists(perf_path):
                with open(perf_path, 'r') as f:
                    self.model_performance = json.load(f)
                print(f"Loaded performance metrics from {perf_path}")
            
            return len(self.models) > 0
            
        except Exception as e:
            print(f"Error loading models: {e}")
            return False
    
    def print_model_performance(self):
        """Print detailed model performance metrics"""
        if not self.model_performance:
            print("No performance metrics available")
            return
        
        print("\nModel Performance Summary:")
        print("-" * 50)
        for model_name, metrics in self.model_performance.items():
            print(f"{model_name}:")
            print(f"  R² Score: {metrics['r2']:.3f}")
            print(f"  RMSE: {metrics['rmse']:.2f}")
            print(f"  MAE: {metrics['mae']:.2f}")
            print()

def main():
    """Main function to demonstrate ML predictions"""
    predictor = CryptoPricePredictor()
    
    # Test with Bitcoin
    coin = 'bitcoin'
    
    # Try to load existing models
    if not predictor.load_models(coin):
        print("Training new models...")
        predictor.train_models(coin)
        predictor.save_models(coin)
    
    # Make prediction
    prediction = predictor.predict_price(coin)
    if prediction:
        print(f"\nPrice Prediction for {coin.upper()}:")
        print(f"Current Price: ${prediction['current_price']:,.2f}")
        print(f"Predicted Price: ${prediction['predicted_price']:,.2f}")
        print(f"Predicted Change: {prediction['predicted_change']:.2%}")
        print(f"Prediction Date: {prediction['prediction_date'].strftime('%Y-%m-%d')}")
        
        print(f"\nIndividual Model Predictions:")
        for model, price in prediction['individual_predictions'].items():
            print(f"  {model}: ${price:,.2f}")
        
        confidence = predictor.get_prediction_confidence(coin)
        print(f"\nPrediction Confidence: {confidence:.1%}")
    
    # Print model performance
    predictor.print_model_performance()

if __name__ == "__main__":
    main() 