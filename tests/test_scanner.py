from unittest.mock import patch

import numpy as np
import pandas as pd

from trade_scanner.scanner import scan
from trade_scanner.types import Ticker


def _vcp_df() -> pd.DataFrame:
    n = 250
    rng = np.random.default_rng(42)
    uptrend = np.linspace(80, 160, n - 60)
    peak = np.full(10, 160)
    contraction = np.linspace(160, 140, 30) + rng.normal(0, 0.5, 30)
    right_side = np.linspace(140, 160, 20) + rng.normal(0, 0.3, 20)
    close = np.concatenate([uptrend, peak, contraction, right_side])
    close = np.maximum(close, 1)

    high = close * (1 + rng.uniform(0.005, 0.025, len(close)))
    low = close * (1 - rng.uniform(0.005, 0.025, len(close)))

    volume_decline = np.linspace(3_000_000, 500_000, len(close))
    volume_noise = rng.uniform(-100_000, 100_000, len(close))
    volume = np.maximum(volume_decline + volume_noise, 100_000).astype(int)

    return pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


@patch("trade_scanner.providers.instruments.file.FileProvider.get_instruments")
@patch("trade_scanner.providers.prices.yahoo.YahooProvider.get_history")
def test_scan_returns_results(mock_get_history, mock_get_instruments):
    aapl = Ticker(symbol="AAPL")
    msft = Ticker(symbol="MSFT")
    mock_get_instruments.return_value = ["AAPL", "MSFT"]
    mock_get_history.return_value = {
        aapl: _vcp_df(),
        msft: _vcp_df(),
    }

    from trade_scanner.providers.prices import YahooProvider
    from trade_scanner.providers.instruments import FileProvider

    results = list(scan(
        instrument_provider=FileProvider("/irrelevant"),
        data_provider=YahooProvider(),
        pattern_names=["vcp"],
    ))
    assert len(results) > 0
    assert all(r.score >= 0 for r in results)
    assert all(r.symbol in (aapl, msft) for r in results)


@patch("trade_scanner.providers.instruments.file.FileProvider.get_instruments")
@patch("trade_scanner.providers.prices.yahoo.YahooProvider.get_history")
def test_scan_reports_failures(mock_get_history, mock_get_instruments):
    aapl = Ticker(symbol="AAPL")
    msft = Ticker(symbol="MSFT")
    bad = Ticker(symbol="BAD")
    mock_get_instruments.return_value = ["AAPL", "MSFT", "BAD"]
    mock_get_history.return_value = {
        aapl: _vcp_df(),
        msft: _vcp_df(),
        bad: pd.DataFrame({"Close": range(100)}),
    }

    from trade_scanner.providers.prices import YahooProvider
    from trade_scanner.providers.instruments import FileProvider

    results = list(scan(
        instrument_provider=FileProvider("/irrelevant"),
        data_provider=YahooProvider(),
        pattern_names=["vcp"],
    ))
    assert len(results) == 3
    bad_result = [r for r in results if r.symbol == bad][0]
    assert bad_result.error is not None
    assert "Insufficient data" in bad_result.error
    assert bad_result.score is None
    assert bad_result.signal is None


@patch("trade_scanner.providers.instruments.file.FileProvider.get_instruments")
@patch("trade_scanner.providers.prices.yahoo.YahooProvider.get_history")
def test_scan_includes_no_match(mock_get_history, mock_get_instruments):
    aapl = Ticker(symbol="AAPL")
    msft = Ticker(symbol="MSFT")
    mock_get_instruments.return_value = ["AAPL", "MSFT"]

    n = 250
    rng = np.random.default_rng(42)
    close = np.linspace(100, 50, n)
    high = close * (1 + rng.uniform(0.005, 0.025, n))
    low = close * (1 - rng.uniform(0.005, 0.025, n))
    volume = np.full(n, 1_000_000)
    df_downtrend = pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })

    mock_get_history.return_value = {
        aapl: _vcp_df(),
        msft: df_downtrend,
    }

    from trade_scanner.providers.prices import YahooProvider
    from trade_scanner.providers.instruments import FileProvider

    results = list(scan(
        instrument_provider=FileProvider("/irrelevant"),
        data_provider=YahooProvider(),
        pattern_names=["vcp"],
    ))
    assert len(results) == 2
    no_match = [r for r in results if r.symbol == msft][0]
    assert no_match.score == 0
    assert no_match.signal is None
    assert no_match.error is None
