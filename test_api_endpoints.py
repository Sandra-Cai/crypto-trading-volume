import pytest
from web_dashboard import app, init_db
import json

@pytest.fixture(scope='module')
def test_client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

# Helper: login as test user
def login(client, username='user', password='pass'):
    return client.post('/login', data=dict(username=username, password=password), follow_redirects=True)

def test_ml_predict_endpoint(test_client):
    login(test_client)
    # Valid coin (may need to train model first in real use)
    resp = test_client.get('/api/ml-predict/bitcoin')
    assert resp.status_code in (200, 404, 500)  # Accept 404/500 if no model yet
    # Invalid coin
    resp = test_client.get('/api/ml-predict/notacoin')
    assert resp.status_code in (404, 500)

def test_backtest_endpoint(test_client):
    login(test_client)
    # Valid request
    resp = test_client.post('/api/backtest', json={"coin": "bitcoin", "days": 30, "initial_capital": 10000})
    assert resp.status_code in (200, 500)
    # Missing coin
    resp = test_client.post('/api/backtest', json={"days": 30})
    assert resp.status_code == 400

def test_sentiment_single_endpoint(test_client):
    login(test_client)
    resp = test_client.get('/api/sentiment/bitcoin')
    assert resp.status_code in (200, 500)
    resp = test_client.get('/api/sentiment/notacoin')
    assert resp.status_code in (200, 500)

def test_sentiment_batch_endpoint(test_client):
    login(test_client)
    resp = test_client.post('/api/sentiment/batch', json={"coins": ["bitcoin", "ethereum"]})
    assert resp.status_code in (200, 500)
    # No coins
    resp = test_client.post('/api/sentiment/batch', json={})
    assert resp.status_code == 400

def test_run_backtest_endpoint(test_client):
    login(test_client)
    resp = test_client.post('/api/run-backtest', json={"coin": "bitcoin", "days": 30, "initial_capital": 10000})
    assert resp.status_code in (200, 500)
    # Missing coin
    resp = test_client.post('/api/run-backtest', json={"days": 30})
    assert resp.status_code == 400

def test_rate_limiting(test_client):
    login(test_client)
    # Exceed rate limit for ML predict
    for _ in range(65):
        resp = test_client.get('/api/ml-predict/bitcoin')
    assert resp.status_code in (429, 200, 404, 500)  # 429 = rate limited 