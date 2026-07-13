from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from trade_scanner.providers.prices import DataProvider, YahooProvider
from trade_scanner.types import CurrencyPair, ISIN, Ticker


@pytest.fixture
def mock_single_ticker():
    dates = pd.date_range("2026-07-06", periods=5, freq="B")
    columns = pd.MultiIndex.from_tuples(
        [("Open", "AAPL"), ("High", "AAPL"), ("Low", "AAPL"),
         ("Close", "AAPL"), ("Volume", "AAPL")],
        names=["Price", "Ticker"],
    )
    data = np.array([
        [307.36, 314.20, 307.00, 312.66, 53590000],
        [315.29, 315.48, 310.15, 310.66, 42490000],
        [311.91, 314.82, 307.05, 313.39, 41323500],
        [310.51, 316.53, 308.16, 316.22, 48124500],
        [314.72, 316.91, 312.17, 315.32, 34109200],
    ])
    return pd.DataFrame(data, index=dates, columns=columns)


@pytest.fixture
def mock_multi_ticker():
    dates = pd.date_range("2026-07-06", periods=5, freq="B")
    columns = pd.MultiIndex.from_tuples(
        [("AAPL", "Open"), ("AAPL", "High"), ("AAPL", "Low"),
         ("AAPL", "Close"), ("AAPL", "Volume"),
         ("MSFT", "Open"), ("MSFT", "High"), ("MSFT", "Low"),
         ("MSFT", "Close"), ("MSFT", "Volume")],
        names=["Ticker", "Price"],
    )
    data = np.array([
        [307.36, 314.20, 307.00, 312.66, 53590000,
         387.04, 389.15, 384.00, 386.50, 22000000],
        [315.29, 315.48, 310.15, 310.66, 42490000,
         392.49, 395.57, 390.00, 393.20, 18500000],
        [311.91, 314.82, 307.05, 313.39, 41323500,
         384.03, 385.31, 382.00, 383.80, 19500000],
        [310.51, 316.53, 308.16, 316.22, 48124500,
         388.10, 390.50, 386.00, 389.40, 21000000],
        [314.72, 316.91, 312.17, 315.32, 34109200,
         391.25, 393.00, 389.50, 392.10, 17800000],
    ])
    return pd.DataFrame(data, index=dates, columns=columns)


def test_yahoo_provider_is_data_provider():
    assert isinstance(YahooProvider(), DataProvider)


@patch("trade_scanner.providers.prices.yahoo.yf.download")
def test_yahoo_provider_returns_dataframe(mock_download, mock_multi_ticker):
    mock_download.return_value = mock_multi_ticker
    provider = YahooProvider()
    instruments = [Ticker(symbol="AAPL"), Ticker(symbol="MSFT")]
    result = provider.get_history(instruments, period="5d")
    assert len(result) == 2
    for inst in instruments:
        assert inst in result
        assert result[inst] is not None
    mock_download.assert_called_once()


@patch("trade_scanner.providers.prices.yahoo.yf.download")
def test_yahoo_provider_returns_ohlcv_columns(mock_download, mock_single_ticker):
    mock_download.return_value = mock_single_ticker
    provider = YahooProvider()
    result = provider.get_history([Ticker(symbol="AAPL")], period="5d")
    df = result[Ticker(symbol="AAPL")]
    required = {"Open", "High", "Low", "Close", "Volume"}
    assert required.issubset(set(df.columns))


@patch("trade_scanner.providers.prices.yahoo.yf.download")
def test_yahoo_provider_unknown_symbol(mock_download):
    mock_download.return_value = pd.DataFrame()
    provider = YahooProvider()
    result = provider.get_history([Ticker(symbol="INVALID_SYMBOL_XYZ")])
    assert result[Ticker(symbol="INVALID_SYMBOL_XYZ")] is None


@pytest.mark.parametrize(
    "instrument, expected",
    [
        (Ticker(symbol="AAPL"), "AAPL"),
        (Ticker(mic="XNYS", symbol="BRK.A"), "BRK.A"),
        (Ticker(mic="XPAR", symbol="SAP"), "SAP.PA"),
        (Ticker(mic="XLON", symbol="BP"), "BP.L"),
        (Ticker(mic="XETR", symbol="SAP"), "SAP.DE"),
        (Ticker(mic="XNAS", symbol="AAPL"), "AAPL"),
        (Ticker(mic="UNKN", symbol="TICK"), "TICK"),
        (CurrencyPair(base="EUR", counter="USD"), "EURUSD=X"),
        (CurrencyPair(base="BTC", counter="USD"), "BTCUSD=X"),
        (ISIN(code="US0378331005"), "US0378331005"),
    ],
)
def test_to_provider_symbol(instrument, expected):
    assert YahooProvider.to_provider_symbol(instrument) == expected
