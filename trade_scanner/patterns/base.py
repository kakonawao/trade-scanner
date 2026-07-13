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

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> Result | None:
        ...
