from dataclasses import dataclass

import pandas as pd

from ..indicators import add_indicators
from ..types import Ticker
from .base import Pattern, PatternError, Result


@dataclass
class BullFlagDetails:
    pole_date: str | None = None
    pole_price: float | None = None
    pole_pct: float | None = None
    flag_low: float | None = None
    flag_retracement_pct: float | None = None
    flag_bars: int | None = None
    flag_tightness_pct: float | None = None
    vol_dry: bool | None = None
    breakout_pct: float | None = None
    current_price: float | None = None
    trend_ok: bool | None = None
    criteria_met: int = 0
    criteria_total: int = 0


display_fields: list[str] = [
    "pole_date", "pole_pct", "flag_retracement_pct", "flag_bars", "breakout_pct", "current_price",
]

field_labels: dict[str, str] = {
    "pole_date": "pole date",
    "pole_pct": "pole gain",
    "flag_retracement_pct": "retrace",
    "flag_bars": "flag bars",
    "breakout_pct": "breakout",
    "current_price": "price",
}

_pct_fields: set[str] = {"pole_pct", "flag_retracement_pct", "breakout_pct"}


class BullFlag(Pattern):
    name = "flag"

    _REQUIRED = {"High", "Low", "Close", "Volume"}

    def __init__(
        self,
        min_pole_pct: float = 0.15,
        max_pole_pct: float = 0.50,
        max_pole_bars: int = 25,
        min_flag_bars: int = 3,
        max_flag_bars: int = 25,
        max_retracement_pct: float = 0.50,
        lookback: int = 90,
    ):
        self._min_pole_pct = min_pole_pct
        self._max_pole_pct = max_pole_pct
        self._max_pole_bars = max_pole_bars
        self._min_flag_bars = min_flag_bars
        self._max_flag_bars = max_flag_bars
        self._max_retracement_pct = max_retracement_pct
        self._lookback = lookback

    def detect(self, df: pd.DataFrame) -> Result | None:
        if df is None:
            raise PatternError("No price data available")
        if len(df) < 150:
            raise PatternError(f"Insufficient data: got {len(df)} rows, need at least 150")

        missing = self._REQUIRED - set(df.columns)
        if missing:
            raise PatternError(f"Missing required columns: {', '.join(sorted(missing))}")
        bad = [c for c in self._REQUIRED if df[c].isna().all()]
        if bad:
            if len(bad) == len(self._REQUIRED):
                raise PatternError("No price data available")
            raise PatternError(f"Column(s) entirely NaN: {', '.join(bad)}")

        df = add_indicators(df)

        # Find flagpole (sharp rally)
        recent = df.iloc[-self._lookback:]
        if recent["High"].isna().all():
            return None
        pole_high_idx = recent["High"].idxmax()
        pole_high = recent.loc[pole_high_idx, "High"]
        pole_high_pos = df.index.get_loc(pole_high_idx)

        # Walk backwards to find pole low (within max_pole_bars)
        start_pos = max(0, pole_high_pos - self._max_pole_bars)
        pole_window = df.iloc[start_pos : pole_high_pos + 1]
        pole_low_idx = pole_window["Low"].idxmin()
        pole_low = pole_window.loc[pole_low_idx, "Low"]
        pole_pct = (pole_high - pole_low) / pole_low

        if not (self._min_pole_pct <= pole_pct <= self._max_pole_pct):
            return None

        # Check uptrend at pole start (SMA_50 > SMA_150)
        pole_start_row = df.loc[pole_low_idx]
        sma_50_ok = not pd.isna(pole_start_row.get("SMA_50"))
        sma_150_ok = not pd.isna(pole_start_row.get("SMA_150"))
        trend_ok = bool(sma_50_ok and sma_150_ok and pole_start_row["SMA_50"] > pole_start_row["SMA_150"])

        # After the pole high, find the flag (pullback)
        after_pole = df.iloc[pole_high_pos + 1 :]
        if len(after_pole) < self._min_flag_bars:
            return None

        below_pole = after_pole["Close"] < pole_high
        if below_pole.any():
            flag_end_idx = below_pole[::-1].idxmax()
            flag_end_pos = df.index.get_loc(flag_end_idx)
        else:
            return None

        flag = df.iloc[pole_high_pos + 1 : flag_end_pos + 1]
        flag_bars = len(flag)
        if flag_bars < self._min_flag_bars or flag_bars > self._max_flag_bars:
            return None

        # Retracement check
        flag_low = flag["Low"].min()
        pole_height = pole_high - pole_low
        if pole_height <= 0:
            return None
        flag_retrace = (pole_high - flag_low) / pole_height
        if flag_retrace > self._max_retracement_pct:
            return None

        # Flag metrics
        vol_dry = flag["VMA_10"].iloc[-1] < flag["VMA_50"].iloc[-1]
        flag_tightness = flag["RANGE_PCT"].mean()
        last_valid_close_idx = df["Close"].last_valid_index()
        current_close = df.loc[last_valid_close_idx, "Close"] if last_valid_close_idx is not None else float("nan")
        breakout_pct = (current_close - pole_high) / pole_high

        # Score
        score = self._compute_score(pole_pct, flag_retrace, flag_tightness, vol_dry, flag_bars, breakout_pct, trend_ok)

        criteria_met, criteria_total = self._check_qualifiers(
            pole_pct, flag_retrace, flag_tightness, vol_dry, flag_bars, breakout_pct, trend_ok,
        )
        score = int(score * criteria_met / criteria_total) if criteria_total > 0 else 0

        def _fmt_date(idx):
            return str(idx.date()) if hasattr(idx, "date") else str(idx)

        return Result(
            symbol=Ticker(),
            pattern="flag",
            score=score,
            signal=None,
            details=BullFlagDetails(
                pole_date=_fmt_date(pole_high_idx),
                pole_price=round(pole_high, 2),
                pole_pct=round(pole_pct * 100, 1),
                flag_low=round(flag_low, 2),
                flag_retracement_pct=round(flag_retrace * 100, 1),
                flag_bars=flag_bars,
                flag_tightness_pct=round(flag_tightness, 2),
                vol_dry=bool(vol_dry),
                breakout_pct=round(breakout_pct * 100, 1),
                current_price=round(current_close, 2),
                trend_ok=trend_ok,
                criteria_met=criteria_met,
                criteria_total=criteria_total,
            ),
        )

    def _compute_score(
        self,
        pole_pct: float,
        flag_retrace: float,
        flag_tightness: float,
        vol_dry: bool,
        flag_bars: int,
        breakout_pct: float,
        trend_ok: bool,
    ) -> int:
        return (
            self._score_pole_height(pole_pct)
            + self._score_retracement(flag_retrace)
            + self._score_flag_tightness(flag_tightness)
            + self._score_volume(vol_dry)
            + self._score_flag_duration(flag_bars)
            + self._score_breakout_proximity(breakout_pct)
            + self._score_trend(trend_ok)
        )

    def _check_qualifiers(
        self,
        pole_pct: float,
        flag_retrace: float,
        flag_tightness: float,
        vol_dry: bool,
        flag_bars: int,
        breakout_pct: float,
        trend_ok: bool,
    ) -> tuple[int, int]:
        criteria = [
            0.15 <= pole_pct <= 0.35,
            0.25 <= flag_retrace <= 0.40,
            flag_tightness < 0.05,
            vol_dry,
            5 <= flag_bars <= 15,
            breakout_pct >= -0.02,
            trend_ok,
        ]
        return sum(criteria), len(criteria)

    def _score_pole_height(self, pole_pct: float) -> int:
        if 0.15 <= pole_pct <= 0.35:
            return 15
        if 0.35 <= pole_pct <= 0.50:
            return 10
        if 0.10 <= pole_pct < 0.15:
            return 5
        return 0

    def _score_retracement(self, flag_retrace: float) -> int:
        if 0.25 <= flag_retrace <= 0.40:
            return 20
        if 0.15 <= flag_retrace < 0.25:
            return 15
        if 0.40 < flag_retrace <= 0.50:
            return 10
        if flag_retrace < 0.15:
            return 10
        return 0

    def _score_flag_tightness(self, tightness: float) -> int:
        if tightness < 0.03:
            return 15
        if tightness < 0.05:
            return 10
        return 5

    def _score_volume(self, vol_dry: bool) -> int:
        return 15 if vol_dry else 0

    def _score_flag_duration(self, bars: int) -> int:
        if 5 <= bars <= 15:
            return 10
        if 3 <= bars < 5 or 15 < bars <= 20:
            return 5
        return 0

    def _score_breakout_proximity(self, breakout_pct: float) -> int:
        if breakout_pct >= 0:
            return 15
        if breakout_pct >= -0.02:
            return 10
        if breakout_pct >= -0.05:
            return 5
        return 0

    def _score_trend(self, trend_ok: bool) -> int:
        return 10 if trend_ok else 0
