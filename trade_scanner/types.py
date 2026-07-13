from dataclasses import dataclass


@dataclass(frozen=True)
class Ticker:
    mic: str | None = None
    symbol: str = ""

    def __str__(self) -> str:
        if self.mic:
            return f"{self.mic}:{self.symbol}"
        return self.symbol


@dataclass(frozen=True)
class ISIN:
    code: str = ""

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True)
class CurrencyPair:
    base: str = ""
    counter: str = ""

    def __str__(self) -> str:
        return f"{self.base}/{self.counter}"


Instrument = Ticker | ISIN | CurrencyPair


def _is_isin(s: str) -> bool:
    return len(s) == 12 and s[:2].isalpha() and s[2:].isalnum()


def parse_instrument(s: str) -> Instrument:
    if ":" in s:
        mic, symbol = s.split(":", 1)
        return Ticker(mic=mic, symbol=symbol)
    if "/" in s:
        base, counter = s.split("/", 1)
        return CurrencyPair(base=base, counter=counter)
    if _is_isin(s):
        return ISIN(code=s)
    return Ticker(symbol=s)
