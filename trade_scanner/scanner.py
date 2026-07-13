from collections.abc import Generator

from .patterns import PATTERNS, Pattern, PatternError, Result
from .providers.instruments import InstrumentListProvider
from .providers.prices import DataProvider
from .types import Instrument, parse_instrument


def _failed(symbol: Instrument, pattern_name: str, error: str) -> Result:
    return Result(
        symbol=symbol,
        pattern=pattern_name,
        score=None,
        signal=None,
        details=None,
        error=error,
    )


def scan(
    instrument_provider: InstrumentListProvider,
    data_provider: DataProvider,
    pattern_names: list[str] | None = None,
    period: str = "1y",
    end_date: str | None = None,
) -> Generator[Result]:
    if pattern_names is None:
        pattern_names = list(PATTERNS)
    patterns: list[Pattern] = []
    for name in pattern_names:
        cls = PATTERNS.get(name)
        if cls is None:
            raise ValueError(f"Unknown pattern: {name}")
        patterns.append(cls())

    raw_instruments = instrument_provider.get_instruments()
    if not raw_instruments:
        return

    instruments = [parse_instrument(s) for s in raw_instruments]
    prices = data_provider.get_history(instruments, period=period, end=end_date)

    for inst in instruments:
        df = prices.get(inst)
        for p in patterns:
            pattern_name = p.name
            if df is None:
                yield _failed(inst, pattern_name, "No price data available")
                continue
            try:
                result = p.detect(df)
                if result is None:
                    yield Result(
                        symbol=inst,
                        pattern=pattern_name,
                        score=0,
                        signal=None,
                        details=None,
                    )
                else:
                    result.symbol = inst
                    yield result
            except PatternError as e:
                yield _failed(inst, pattern_name, str(e))
            except Exception as e:
                yield _failed(inst, pattern_name, f"Unexpected error: {e}")
