from abc import ABC, abstractmethod


class InstrumentListProvider(ABC):
    @abstractmethod
    def get_instruments(self) -> list[str]:
        ...
