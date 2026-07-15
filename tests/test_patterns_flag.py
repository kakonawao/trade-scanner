import numpy as np
import pandas as pd

import pytest

from trade_scanner.patterns import Pattern, PatternError, BullFlag


def _flag_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)

    base = np.linspace(100, 110, 175)
    pole_close = np.linspace(110, 143, 10)
    flag_close = np.linspace(143, 130, 8)
    after = np.linspace(130, 131, 2)
    close = np.concatenate([base, pole_close, flag_close, after]) + rng.normal(0, 0.2, 195)
    close = np.maximum(close, 1)

    mult = np.concatenate([
        np.full(175, 0.015),
        np.linspace(0.020, 0.030, 10),
        np.linspace(0.005, 0.004, 8),
        np.full(2, 0.01),
    ])
    high = close * (1 + mult)
    low = close * (1 - mult)

    pole_vol = rng.integers(2_000_000, 3_000_000, 10)
    flag_vol_dec = np.linspace(2_000_000, 500_000, 8).astype(int)
    base_vol = rng.integers(800_000, 1_200_000, 175)
    volume = np.concatenate([base_vol, pole_vol, flag_vol_dec, [500_000, 500_000]])

    return pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_flag_basics():
    bf = BullFlag()
    assert isinstance(bf, Pattern)
    assert bf.name == "flag"


def test_flag_detects_valid_pattern():
    df = _flag_df()
    result = BullFlag().detect(df)
    assert result is not None
    assert result.pattern == "flag"
    assert result.score >= 0

    details = result.details
    assert details.pole_pct is not None
    assert 15.0 <= details.pole_pct <= 50.0
    assert details.flag_retracement_pct is not None
    assert details.flag_retracement_pct <= 50.0
    assert details.flag_bars is not None
    assert 3 <= details.flag_bars <= 25
    assert details.breakout_pct is not None
    assert details.vol_breakout is not None


def test_flag_rejects_missing_columns():
    df = pd.DataFrame({"Close": range(200)})
    with pytest.raises(PatternError, match="Missing required columns"):
        BullFlag().detect(df)


def test_flag_rejects_too_few_rows():
    df = _flag_df().iloc[:100]
    with pytest.raises(PatternError, match="Insufficient data"):
        BullFlag().detect(df)


def test_flag_rejects_all_nan_columns():
    df = _flag_df()
    for col in ("High", "Low", "Close", "Volume"):
        df[col] = float("nan")
    with pytest.raises(PatternError, match="No price data available"):
        BullFlag().detect(df)


def test_flag_rejects_partial_nan_column():
    df = _flag_df()
    df["High"] = float("nan")
    with pytest.raises(PatternError, match="entirely NaN"):
        BullFlag().detect(df)


def test_flag_rejects_downtrend():
    rng = np.random.default_rng(42)
    n = 200
    close = np.linspace(160, 80, n) + rng.normal(0, 0.5, n)
    high = close * 1.02
    low = close * 0.98
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = BullFlag().detect(df)
    assert result is None


def test_flag_no_room_after_pole():
    rng = np.random.default_rng(42)
    n = 200
    close = np.linspace(100, 145, n)
    high = close * (1 + rng.uniform(0.01, 0.03, n))
    low = close * (1 - rng.uniform(0.01, 0.03, n))
    df = pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = BullFlag().detect(df)
    assert result is None


def test_flag_pole_too_small():
    rng = np.random.default_rng(42)
    n = 200
    close = np.linspace(100, 110, n)
    high = close * (1 + rng.uniform(0.01, 0.03, n))
    low = close * (1 - rng.uniform(0.01, 0.03, n))
    df = pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = BullFlag().detect(df)
    assert result is None


def test_flag_pole_too_large():
    rng = np.random.default_rng(42)
    n = 200
    base = np.linspace(100, 110, 175)
    spike = np.linspace(110, 200, 25)
    close = np.concatenate([base, spike])
    high = close * (1 + rng.uniform(0.01, 0.03, n))
    low = close * (1 - rng.uniform(0.01, 0.03, n))
    df = pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = BullFlag().detect(df)
    assert result is None


def test_flag_retrace_too_deep():
    rng = np.random.default_rng(42)
    n = 175
    base = np.linspace(100, 110, 150)
    pole = np.linspace(110, 143, 10)
    flag = np.linspace(143, 100, 12)
    after = np.full(3, 100)
    close = np.concatenate([base, pole, flag, after]) + rng.normal(0, 0.2, n)
    close = np.maximum(close, 1)
    high = close * 1.02
    low = close * 0.98
    df = pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = BullFlag().detect(df)
    assert result is None


def test_flag_scores():
    df = _flag_df()
    result = BullFlag().detect(df)
    assert result is not None
    assert result.score > 0
    details = result.details
    assert details.criteria_met > 0
    assert details.criteria_total > 0
    assert details.flag_tightness_pct is not None
    assert details.vol_dry is not None
    assert details.trend_ok is True


def _flag_no_breakout_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = np.linspace(100, 110, 175)
    pole_close = np.linspace(110, 143, 10)
    flag_close = np.linspace(143, 130, 8)
    after = np.linspace(130, 135, 2)
    close = np.concatenate([base, pole_close, flag_close, after]) + rng.normal(0, 0.2, 195)
    close = np.maximum(close, 1)

    mult = np.concatenate([
        np.full(175, 0.015),
        np.linspace(0.020, 0.030, 10),
        np.linspace(0.005, 0.004, 8),
        np.full(2, 0.01),
    ])
    high = close * (1 + mult)
    low = close * (1 - mult)

    pole_vol = rng.integers(2_000_000, 3_000_000, 10)
    flag_vol_dec = np.linspace(2_000_000, 500_000, 8).astype(int)
    base_vol = rng.integers(800_000, 1_200_000, 175)
    volume = np.concatenate([base_vol, pole_vol, flag_vol_dec, [500_000, 500_000]])

    return pd.DataFrame({
        "Open": close * 0.995,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_flag_no_breakout():
    df = _flag_no_breakout_df()
    result = BullFlag().detect(df)
    assert result is not None
    assert result.details.vol_breakout is False
    assert result.score < 100
