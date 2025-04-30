import os
import pytest
import redis
import requests
from unittest.mock import patch, MagicMock
from . import dev_tmdb

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "0")
    monkeypatch.setenv("TMDB_ACCOUNT_ID", "123")
    monkeypatch.setenv("TMDB_ACCOUNT_BEARER", "testtoken")
    monkeypatch.setenv("TUNNEL_HOST_NAME", "127.0.0.1")
    monkeypatch.setenv("TUNNEL_PORT", "1089")

@pytest.fixture
def mock_redis(mocker):
    mock = mocker.patch("redis.Redis")
    instance = mock.return_value
    instance.ping.return_value = True
    return instance

@pytest.fixture
def mock_requests(mocker):
    mock = mocker.patch("requests.get")
    response = MagicMock()
    response.json.return_value = {"results": [1, 2, 3]}
    response.raise_for_status.return_value = None
    mock.return_value = response
    return mock

def test_get_redis_client_success(mocker):
    # Create a mock Redis instance
    mock_redis = mocker.MagicMock(spec=redis.Redis)
    mock_redis.ping.return_value = True
    
    # Patch Redis.Redis to return our mock instance
    mocker.patch('redis.Redis', return_value=mock_redis)
    
    client = dev_tmdb.get_redis_client()
    assert client is not None
    # Verify ping was called
    mock_redis.ping.assert_called_once()

def test_get_redis_client_failure(mocker):
    mock_redis = mocker.patch("redis.Redis")
    mock_redis.return_value.ping.side_effect = redis.ConnectionError("Failed to connect")
    
    with pytest.raises(redis.ConnectionError):
        dev_tmdb.get_redis_client()

def test_request_json_uses_proxy_and_headers(mock_requests, monkeypatch):
    monkeypatch.setattr(dev_tmdb, 'HEADERS', {'Authorization': 'Bearer testtoken'})
    monkeypatch.setattr(dev_tmdb, 'PROXIES', {
        'http': 'socks5h://127.0.0.1:1089',
        'https': 'socks5h://127.0.0.1:1089'
    })
    
    url = "http://example.com"
    extra = {"test": "value"}
    
    data = dev_tmdb.request_json(url, extra)
    assert data == {"results": [1, 2, 3]}
    mock_requests.assert_called_once_with(
        url,
        headers=dev_tmdb.HEADERS,
        proxies=dev_tmdb.PROXIES,
        timeout=10
    )

def test_request_json_failure(mocker, monkeypatch):
    monkeypatch.setattr(dev_tmdb, 'HEADERS', {'Authorization': 'Bearer testtoken'})
    monkeypatch.setattr(dev_tmdb, 'PROXIES', {
        'http': 'socks5h://127.0.0.1:1089',
        'https': 'socks5h://127.0.0.1:1089'
    })
    
    mocker.patch("requests.get", side_effect=requests.RequestException("Failed"))
    mocker.patch.object(dev_tmdb, "logger")
    
    with pytest.raises(requests.RequestException):
        dev_tmdb.request_json("http://example.com", {})

def test_health_check_success(mocker):
    mocker.patch('tmdb.dev_tmdb.get_redis_client').return_value.ping.return_value = True
    dev_tmdb.redis_client = dev_tmdb.get_redis_client()
    assert dev_tmdb.health_check() is True

def test_health_check_failure(mocker):
    mock_redis = mocker.patch('tmdb.dev_tmdb.get_redis_client')
    mock_redis.return_value.ping.side_effect = redis.ConnectionError("Failed")
    # Need to set redis_client for the test
    dev_tmdb.redis_client = mock_redis.return_value
    assert dev_tmdb.health_check() is False
