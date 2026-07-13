import pandas as pd

from trade_scanner.indicators import add_indicators


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Open": [100.0 + i for i in range(250)],
        "High": [102.0 + i for i in range(250)],
        "Low": [99.0 + i for i in range(250)],
        "Close": [101.0 + i for i in range(250)],
        "Volume": [1_000_000 + i * 1000 for i in range(250)],
    })


def test_add_indicators():
    df = _sample_df()
    result = add_indicators(df)
    assert isinstance(result, pd.DataFrame)
    assert "SMA_50" in result.columns
    assert "SMA_150" in result.columns
    assert "SMA_200" in result.columns
    assert "ATR_5" in result.columns
    assert "ATR_10" in result.columns
    assert "ATR_21" in result.columns
    assert "VMA_10" in result.columns
    assert "VMA_50" in result.columns
    assert "RANGE_PCT" in result.columns

    expected_sma = df["Close"].rolling(50).mean()
    assert result["SMA_50"].iloc[-1] == expected_sma.iloc[-1]
    assert result["ATR_5"].iloc[-1] > 0
