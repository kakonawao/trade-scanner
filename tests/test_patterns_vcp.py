import numpy as np
import pandas as pd

import pytest

from trade_scanner.patterns import Pattern, PatternError, VCP
from trade_scanner.types import Ticker


def _vcp_df() -> pd.DataFrame:
    n = 250
    rng = np.random.default_rng(42)
    uptrend = np.linspace(80, 160, n - 50)
    peak = np.full(10, 160)
    contraction = np.linspace(160, 140, 30) + rng.normal(0, 0.3, 30)
    right_side = np.linspace(140, 158, 10) + rng.normal(0, 0.15, 10)
    close = np.concatenate([uptrend, peak, contraction, right_side])
    close = np.maximum(close, 1)

    mult = np.concatenate([
        np.full(n - 50, 0.025),
        np.full(10, 0.020),
        np.linspace(0.020, 0.010, 30),
        np.full(10, 0.003),
    ])
    high = close * (1 + mult)
    low = close * (1 - mult)

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


def test_vcp_basics():
    vcp = VCP()
    assert isinstance(vcp, Pattern)
    assert vcp.name == "vcp"


def test_vcp_detects_valid_pattern():
    df = _vcp_df()
    result = VCP().detect(df)
    assert result is not None
    assert result.pattern == "vcp"
    assert result.signal == "strong"
    assert result.score >= 70
    assert result.symbol == Ticker()

    details = result.details
    assert details.decline_pct is not None
    assert 5.0 <= details.decline_pct <= 40.0
    assert details.contraction_ratio is not None
    assert details.contraction_ratio < 1.0
    assert details.contraction_stages is not None
    assert details.contraction_stages >= 2
    assert details.tight_range_pct is not None
    assert details.tight_range_pct < 3.0
    assert details.vol_dry is True
    assert details.is_tight is True


def test_vcp_rejects_missing_columns():
    df = pd.DataFrame({"Close": range(200)})
    with pytest.raises(PatternError, match="Missing required columns"):
        VCP().detect(df)


def test_vcp_rejects_too_few_rows():
    df = _vcp_df().iloc[:100]
    with pytest.raises(PatternError, match="Insufficient data"):
        VCP().detect(df)


def test_vcp_rejects_all_nan_columns():
    df = _vcp_df()
    for col in ("High", "Low", "Close", "Volume"):
        df[col] = float("nan")
    with pytest.raises(PatternError, match="No price data available"):
        VCP().detect(df)


def test_vcp_rejects_partial_nan_column():
    df = _vcp_df()
    df["High"] = float("nan")
    with pytest.raises(PatternError, match="entirely NaN"):
        VCP().detect(df)


def test_vcp_rejects_downtrend():
    rng = np.random.default_rng(42)
    n = 250
    close = np.linspace(160, 80, n) + rng.normal(0, 1, n)
    high = close * 1.02
    low = close * 0.98
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": np.full(n, 1_000_000),
    })
    result = VCP().detect(df)
    assert result is None
