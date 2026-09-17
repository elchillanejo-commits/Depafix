"""Tests para core y data."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from data.kraken_client import KrakenClient
from data.buffer import VelaBuffer
from core.brain import TradingBrain


@pytest.fixture
def sample_candles():
    return [
        {"timestamp": "2024-01-01T00:00:00", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
        {"timestamp": "2024-01-01T00:01:00", "open": 100.5, "high": 102, "low": 100, "close": 101, "volume": 1200},
    ]


def test_buffer_add_and_cache():
    buf = VelaBuffer()
    c = {"pair": "BTC/USD", "timeframe": "1h", "timestamp": "2024-01-01T00:00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}
    buf.add(c)
    assert buf.get_last("BTC/USD", "1h") is not None


def test_brain_no_signal_with_few_candles():
    brain = TradingBrain()
    candles = {
        "15m": [{"timestamp": "2024-01-01T00:00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}],
    }
    result = brain.process("BTC/USD", candles)
    assert result is None


@pytest.mark.asyncio
async def test_kraken_client_context():
    client = KrakenClient()
    assert client.session is None
