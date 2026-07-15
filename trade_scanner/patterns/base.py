from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

import pandas as pd

from ..types import Instrument

T = TypeVar("T")


class PatternError(Exception):
    ...


@dataclass
class Result(Generic[T]):
    symbol: Instrument
    pattern: str
    score: int | None
    signal: str | None
    details: T
    error: str | None = None


class Pattern(ABC):
    name: str
    _REQUIRED = {"High", "Low", "Close", "Volume"}

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> Result | None:
        ...

    @staticmethod
    def _fmt_date(idx) -> str:
        return str(idx.date()) if hasattr(idx, "date") else str(idx)

    @staticmethod
    def _validate_input(df: pd.DataFrame, min_rows: int) -> None:
        if df is None:
            raise PatternError("No price data available")
        if len(df) < min_rows:
            raise PatternError(f"Insufficient data: got {len(df)} rows, need at least {min_rows}")
        required = Pattern._REQUIRED
        missing = required - set(df.columns)
        if missing:
            raise PatternError(f"Missing required columns: {', '.join(sorted(missing))}")
        bad = [c for c in required if df[c].isna().all()]
        if bad:
            if len(bad) == len(required):
                raise PatternError("No price data available")
            raise PatternError(f"Column(s) entirely NaN: {', '.join(bad)}")

    @staticmethod
    def _current_close(df: pd.DataFrame) -> float:
        idx = df["Close"].last_valid_index()
        return df.loc[idx, "Close"] if idx is not None else float("nan")

    @staticmethod
    def _detect_breakout_volume(df: pd.DataFrame, after_idx, reference_price: float) -> bool:
        after = df.iloc[after_idx + 1:]
        breakout = after["Close"] >= reference_price
        if not breakout.any():
            return False
        first = breakout.idxmax()
        window = df.iloc[df.index.get_loc(first):df.index.get_loc(first) + 3]
        return bool(any(window["Volume"] > window["VMA_10"]))

    @staticmethod
    def _is_volume_dry(consolidation: pd.DataFrame) -> bool:
        return consolidation["VMA_10"].iloc[-1] < consolidation["VMA_50"].iloc[-1]

    @staticmethod
    def _score_criteria(criteria: dict[str, bool]) -> tuple[int, int, list[str]]:
        total = len(criteria)
        failed = [k for k, v in criteria.items() if not v]
        met = total - len(failed)
        return met, total, failed

    @staticmethod
    def _adjust_score(score: int, criteria_met: int, criteria_total: int) -> int:
        return int(score * criteria_met / criteria_total) if criteria_total > 0 else 0
