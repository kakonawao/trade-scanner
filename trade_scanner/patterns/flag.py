from dataclasses import dataclass, field

import pandas as pd

from ..indicators import add_indicators
from ..types import Ticker
from .base import Pattern, PatternError, Result


@dataclass
class BullFlagDetails:
    pole_date: str | None = None
    pole_price: float | None = None
    pole_pct: float | None = None
    flag_low: str | None = None
    flag_retracement_pct: float | None = None
    flag_bars: int | None = None
    flag_tightness_pct: float | None = None
    vol_dry: bool | None = None
    breakout_pct: float | None = None
    vol_breakout: bool | None = None
    current_price: float | None = None
    trend_ok: bool | None = None
    criteria_met: int = 0
    criteria_total: int = 0
    criteria_failed: list[str] = field(default_factory=list)


class BullFlag(Pattern):
    name = "flag"

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
        self._validate_input(df, 150)
        df = add_indicators(df)

        recent = df.iloc[-self._lookback:]
        if recent["High"].isna().all():
            return None
        pole_high_idx = recent["High"].idxmax()
        pole_high = recent.loc[pole_high_idx, "High"]
        pole_high_pos = df.index.get_loc(pole_high_idx)

        start_pos = max(0, pole_high_pos - self._max_pole_bars)
        pole_window = df.iloc[start_pos : pole_high_pos + 1]
        pole_low_idx = pole_window["Low"].idxmin()
        pole_low = pole_window.loc[pole_low_idx, "Low"]
        pole_pct = (pole_high - pole_low) / pole_low

        if not (self._min_pole_pct <= pole_pct <= self._max_pole_pct):
            return None

        pole_start_row = df.loc[pole_low_idx]
        trend_ok = self._is_uptrend(pole_start_row)

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

        flag_low = flag["Low"].min()
        pole_height = pole_high - pole_low
        if pole_height <= 0:
            return None
        flag_retrace = (pole_high - flag_low) / pole_height
        if flag_retrace > self._max_retracement_pct:
            return None

        vol_dry = self._is_volume_dry(flag)
        flag_tightness = flag["RANGE_PCT"].mean()
        current_close = self._current_close(df)
        breakout_pct = (current_close - pole_high) / pole_high

        vol_breakout = self._detect_breakout_volume(df, flag_end_pos, pole_high)

        score = self._compute_score(pole_pct, flag_retrace, flag_tightness, vol_dry, flag_bars, breakout_pct, vol_breakout, trend_ok)

        criteria = self._check_qualifiers(
            pole_pct, flag_retrace, flag_tightness, vol_dry, flag_bars, breakout_pct, vol_breakout, trend_ok,
        )
        criteria_met, criteria_total, criteria_failed = self._score_criteria(criteria)
        score = self._adjust_score(score, criteria_met, criteria_total)

        _fmt = self._fmt_date

        return Result(
            symbol=Ticker(),
            pattern="flag",
            score=score,
            signal=None,
            details=BullFlagDetails(
                pole_date=_fmt(pole_high_idx),
                pole_price=round(pole_high, 2),
                pole_pct=round(pole_pct * 100, 1),
                flag_low=round(flag_low, 2),
                flag_retracement_pct=round(flag_retrace * 100, 1),
                flag_bars=flag_bars,
                flag_tightness_pct=round(flag_tightness, 2),
                vol_dry=bool(vol_dry),
                breakout_pct=round(breakout_pct * 100, 1),
                vol_breakout=vol_breakout,
                current_price=round(current_close, 2),
                trend_ok=trend_ok,
                criteria_met=criteria_met,
                criteria_total=criteria_total,
                criteria_failed=criteria_failed,
            ),
        )

    @staticmethod
    def _is_uptrend(row: pd.Series) -> bool:
        sma_50_ok = not pd.isna(row.get("SMA_50"))
        sma_150_ok = not pd.isna(row.get("SMA_150"))
        return bool(sma_50_ok and sma_150_ok and row["SMA_50"] > row["SMA_150"])

    @staticmethod
    def _compute_score(
        pole_pct: float,
        flag_retrace: float,
        flag_tightness: float,
        vol_dry: bool,
        flag_bars: int,
        breakout_pct: float,
        vol_breakout: bool,
        trend_ok: bool,
    ) -> int:
        return (
            BullFlag._score_pole_height(pole_pct)
            + BullFlag._score_retracement(flag_retrace)
            + BullFlag._score_flag_tightness(flag_tightness)
            + BullFlag._score_volume(vol_dry)
            + BullFlag._score_flag_duration(flag_bars)
            + BullFlag._score_breakout_proximity(breakout_pct)
            + BullFlag._score_breakout_volume(vol_breakout)
            + BullFlag._score_trend(trend_ok)
        )

    @staticmethod
    def _check_qualifiers(
        pole_pct: float,
        flag_retrace: float,
        flag_tightness: float,
        vol_dry: bool,
        flag_bars: int,
        breakout_pct: float,
        vol_breakout: bool,
        trend_ok: bool,
    ) -> dict[str, bool]:
        return {
            "pole": 0.15 <= pole_pct <= 0.35,
            "retrace": 0.25 <= flag_retrace <= 0.40,
            "tightness": flag_tightness < 0.05,
            "volume_dry": vol_dry,
            "duration": 5 <= flag_bars <= 15,
            "breakout_volume": vol_breakout,
            "trend": trend_ok,
        }

    @staticmethod
    def _score_pole_height(pole_pct: float) -> int:
        if 0.15 <= pole_pct <= 0.35:
            return 15
        if 0.35 <= pole_pct <= 0.50:
            return 10
        if 0.10 <= pole_pct < 0.15:
            return 5
        return 0

    @staticmethod
    def _score_retracement(flag_retrace: float) -> int:
        if 0.25 <= flag_retrace <= 0.40:
            return 20
        if 0.15 <= flag_retrace < 0.25:
            return 15
        if 0.40 < flag_retrace <= 0.50:
            return 10
        if flag_retrace < 0.15:
            return 10
        return 0

    @staticmethod
    def _score_flag_tightness(tightness: float) -> int:
        if tightness < 0.03:
            return 15
        if tightness < 0.05:
            return 10
        return 5

    @staticmethod
    def _score_volume(vol_dry: bool) -> int:
        return 10 if vol_dry else 0

    @staticmethod
    def _score_flag_duration(bars: int) -> int:
        if 5 <= bars <= 15:
            return 10
        if 3 <= bars < 5 or 15 < bars <= 20:
            return 5
        return 0

    @staticmethod
    def _score_breakout_proximity(breakout_pct: float) -> int:
        if breakout_pct >= 0:
            return 10
        if breakout_pct >= -0.02:
            return 7
        if breakout_pct >= -0.05:
            return 3
        return 0

    @staticmethod
    def _score_breakout_volume(vol_breakout: bool) -> int:
        return 10 if vol_breakout else 0

    @staticmethod
    def _score_trend(trend_ok: bool) -> int:
        return 10 if trend_ok else 0
