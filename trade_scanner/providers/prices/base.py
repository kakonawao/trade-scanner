from abc import ABC, abstractmethod

import pandas as pd

from ...types import Instrument


class DataProvider(ABC):
    @classmethod
    @abstractmethod
    def to_provider_symbol(cls, instrument: Instrument) -> str:
        ...

    @abstractmethod
    def get_history(
        self, instruments: list[Instrument], period: str = "1y",
        end: str | None = None,
    ) -> dict[Instrument, pd.DataFrame | None]:
        ...
