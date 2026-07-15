from dataclasses import dataclass, field

import pandas as pd

from ..indicators import add_indicators
from ..types import Ticker
from .base import Pattern, PatternError, Result


@dataclass
class VcpDetails:
    peak_date: str | None = None
    trough_date: str | None = None
    end_date: str | None = None
    recovery_pct: float | None = None
    peak_price: float | None = None
    trough_price: float | None = None
    current_price: float | None = None
    decline_pct: float | None = None
    contraction_ratio: float | None = None
    contraction_stages: int | None = None
    tight_range_pct: float | None = None
    vol_dry: bool | None = None
    is_tight: bool | None = None
    vol_breakout: bool | None = None
    peak_distance_pct: float | None = None
    vcp_trend: str | None = None
    criteria_met: int = 0
    criteria_total: int = 0
    criteria_failed: list[str] = field(default_factory=list)


class VCP(Pattern):
    name = "vcp"

    def __init__(
        self,
        min_decline: float = 0.05,
        max_decline: float = 0.55,
        min_consolidation_bars: int = 15,
        weak_threshold: int = 35,
        mid_threshold: int = 50,
        strong_threshold: int = 70,
    ):
        self._min_decline = min_decline
        self._max_decline = max_decline
        self._min_consolidation_bars = min_consolidation_bars
        self._weak_threshold = weak_threshold
        self._mid_threshold = mid_threshold
        self._strong_threshold = strong_threshold

    def detect(self, df: pd.DataFrame) -> Result[VcpDetails] | None:
        self._validate_input(df, 175)
        df = add_indicators(df)

        result = self._find_peak(df)
        if result is None:
            return None

        peak_idx, peak_price, trough_price, decline_pct, consolidation = result

        if not self._is_uptrend(consolidation.iloc[0]):
            return None

        contraction_ratio = self._contraction_ratio(consolidation)
        contraction_stages = self._count_contraction_stages(consolidation)
        vol_dry = self._is_volume_dry(consolidation)
        avg_range_pct, is_tight = self._tightness(consolidation)

        current_close = self._current_close(df)
        close_at_vcp_end = consolidation["Close"].iloc[-1]
        peak_distance_pct = (peak_price - close_at_vcp_end) / peak_price
        if peak_price > trough_price:
            recovery_pct = (close_at_vcp_end - trough_price) / (peak_price - trough_price)
            display_recovery = (current_close - trough_price) / (peak_price - trough_price)
        else:
            recovery_pct = 1.0
            display_recovery = 1.0
        display_peak_distance = (peak_price - current_close) / peak_price

        last_5 = consolidation["Close"].iloc[-5:]
        roc = (last_5.iloc[-1] - last_5.iloc[0]) / last_5.iloc[0]

        consolidation_end_pos = df.index.get_loc(consolidation.index[-1])
        vol_breakout = self._detect_breakout_volume(df, consolidation_end_pos, peak_price)

        score = self._compute_score(
            decline_pct, contraction_ratio,
            contraction_stages, vol_dry, is_tight,
            recovery_pct, roc, peak_distance_pct, vol_breakout,
        )

        criteria = self._check_qualifiers(
            decline_pct, contraction_ratio,
            contraction_stages, vol_dry, is_tight,
            recovery_pct, roc, peak_distance_pct, vol_breakout,
        )
        criteria_met, criteria_total, criteria_failed = self._score_criteria(criteria)
        score = self._adjust_score(score, criteria_met, criteria_total)
        signal = self._classify(score)

        _fmt = self._fmt_date
        after_peak = df.loc[peak_idx:]
        trough_date = _fmt(after_peak["Low"].idxmin())
        vcp_end = _fmt(consolidation.index[-1])
        last_valid = df["Close"].last_valid_index()
        if last_valid is not None and consolidation.index[-1] == last_valid:
            vcp_end = "current"

        return Result(
            symbol=Ticker(),
            pattern="vcp",
            score=score,
            signal=signal,
            details=VcpDetails(
                decline_pct=round(decline_pct * 100, 1),
                contraction_ratio=round(contraction_ratio, 2),
                contraction_stages=contraction_stages,
                tight_range_pct=round(avg_range_pct, 2),
                vol_dry=bool(vol_dry),
                is_tight=bool(is_tight),
                vol_breakout=vol_breakout,
                peak_price=round(peak_price, 2),
                trough_price=round(trough_price, 2),
                current_price=round(current_close, 2),
                vcp_trend=self._classify_trend(roc),
                peak_distance_pct=round(display_peak_distance * 100, 1),
                recovery_pct=round(display_recovery * 100, 1),
                peak_date=_fmt(peak_idx),
                trough_date=trough_date,
                end_date=vcp_end,
                criteria_met=criteria_met,
                criteria_total=criteria_total,
                criteria_failed=criteria_failed,
            ),
        )

    def _find_peak(self, df: pd.DataFrame) -> tuple | None:
        recent = df.iloc[-90:].copy()
        if recent["High"].isna().all():
            return None

        for peak_val in sorted(recent["High"].unique(), reverse=True):
            if pd.isna(peak_val):
                continue
            matches = recent[recent["High"] == peak_val]
            peak_idx = matches.index[-1]
            peak_price = peak_val
            peak_pos = df.index.get_loc(peak_idx)
            after_peak = df.iloc[peak_pos:]
            if len(after_peak) < self._min_consolidation_bars:
                continue

            trough_idx = after_peak["Low"].idxmin()
            trough_price = after_peak.loc[trough_idx, "Low"]
            decline_pct = (peak_price - trough_price) / peak_price

            if not (self._min_decline <= decline_pct <= self._max_decline):
                continue

            last_close = df["Close"].iloc[-1]
            if not pd.isna(last_close) and last_close < trough_price:
                continue

            below_peak = after_peak["Close"] < peak_price
            if below_peak.any():
                end_idx = below_peak[::-1].idxmax()
                end_pos = df.index.get_loc(end_idx)
            else:
                end_pos = peak_pos

            consolidation = df.iloc[peak_pos : end_pos + 1]

            if len(consolidation) < self._min_consolidation_bars:
                continue

            return peak_idx, peak_price, trough_price, decline_pct, consolidation

        return None

    @staticmethod
    def _is_uptrend(row: pd.Series) -> bool:
        if pd.isna(row["SMA_50"]) or pd.isna(row["SMA_150"]):
            return False
        if row["Close"] <= row["SMA_50"]:
            return False
        if row["SMA_50"] <= row["SMA_150"]:
            return False
        if not pd.isna(row["SMA_200"]) and row["Close"] <= row["SMA_200"]:
            return False
        return True

    @staticmethod
    def _contraction_ratio(consolidation: pd.DataFrame) -> float:
        start_atr5 = consolidation["ATR_5"].iloc[0]
        end_atr5 = consolidation["ATR_5"].iloc[-1]
        if start_atr5 > 0:
            return end_atr5 / start_atr5
        return 1.0

    @staticmethod
    def _count_contraction_stages(consolidation: pd.DataFrame) -> int:
        chunk_size = max(5, len(consolidation) // 4)
        stages = 0
        for i in range(1, 4):
            end = min((i + 1) * chunk_size, len(consolidation))
            if end >= len(consolidation):
                break
            prev_atr = consolidation["ATR_10"].iloc[
                (i - 1) * chunk_size : i * chunk_size
            ].mean()
            curr_atr = consolidation["ATR_10"].iloc[
                i * chunk_size : end
            ].mean()
            if curr_atr < prev_atr:
                stages += 1
        return stages

    @staticmethod
    def _tightness(consolidation: pd.DataFrame) -> tuple[float, bool]:
        last_5 = consolidation.iloc[-5:]
        avg_range_pct = last_5["RANGE_PCT"].mean()
        return avg_range_pct, avg_range_pct < 3.0

    @staticmethod
    def _score_decline(decline_pct: float) -> int:
        if 0.15 <= decline_pct <= 0.25:
            return 13
        if 0.10 <= decline_pct < 0.15:
            return 9
        if 0.25 < decline_pct <= 0.35:
            return 7
        if decline_pct < 0.10:
            return 4
        if decline_pct <= 0.55:
            return 4
        return 0

    @staticmethod
    def _score_contraction(contraction_ratio: float) -> int:
        if contraction_ratio < 0.5:
            return 22
        if contraction_ratio < 0.75:
            return 18
        if contraction_ratio < 0.9:
            return 13
        if contraction_ratio < 1.1:
            return 4
        return 0

    @staticmethod
    def _score_contraction_stages(stages: int) -> int:
        return min(stages * 4, 10)

    @staticmethod
    def _score_volume(vol_dry: bool) -> int:
        return 14 if vol_dry else 0

    @staticmethod
    def _score_tightness(is_tight: bool) -> int:
        return 17 if is_tight else 0

    @staticmethod
    def _score_recovery(recovery_pct: float) -> int:
        return min(int(recovery_pct * 13), 13)

    @staticmethod
    def _score_peak_distance(peak_distance_pct: float) -> int:
        return max(0, 4 - int(peak_distance_pct * 100))

    @staticmethod
    def _score_trend(roc: float) -> int:
        if roc >= 0.03:
            return 4
        if roc >= 0.01:
            return 2
        return 0

    @staticmethod
    def _score_breakout_volume(vol_breakout: bool) -> int:
        return 3 if vol_breakout else 0

    @staticmethod
    def _classify_trend(roc: float) -> str:
        if roc >= 0.03:
            return "rising"
        if roc >= 0.01:
            return "steady"
        if roc <= -0.03:
            return "falling"
        if roc <= -0.01:
            return "weakening"
        return "flat"

    @staticmethod
    def _check_qualifiers(
        decline_pct: float,
        contraction_ratio: float,
        contraction_stages: int,
        vol_dry: bool,
        is_tight: bool,
        recovery_pct: float,
        roc: float,
        peak_distance_pct: float,
        vol_breakout: bool,
    ) -> dict[str, bool]:
        return {
            "decline": 0.10 <= decline_pct <= 0.35,
            "contraction": contraction_ratio < 0.9,
            "stages": contraction_stages >= 2,
            "volume_dry": vol_dry,
            "tightness": is_tight,
            "recovery": 0.10 <= recovery_pct <= 0.99,
            "trend": roc >= 0.01,
            "breakout_volume": vol_breakout,
        }

    @staticmethod
    def _compute_score(
        decline_pct: float,
        contraction_ratio: float,
        contraction_stages: int,
        vol_dry: bool,
        is_tight: bool,
        recovery_pct: float,
        roc: float,
        peak_distance_pct: float,
        vol_breakout: bool,
    ) -> int:
        return (
            VCP._score_decline(decline_pct)
            + VCP._score_contraction(contraction_ratio)
            + VCP._score_contraction_stages(contraction_stages)
            + VCP._score_volume(vol_dry)
            + VCP._score_tightness(is_tight)
            + VCP._score_recovery(recovery_pct)
            + VCP._score_peak_distance(peak_distance_pct)
            + VCP._score_trend(roc)
            + VCP._score_breakout_volume(vol_breakout)
        )

    def _classify(self, score: int) -> str | None:
        if score >= self._strong_threshold:
            return "strong"
        if score >= self._mid_threshold:
            return "mid"
        if score >= self._weak_threshold:
            return "weak"
        return None
