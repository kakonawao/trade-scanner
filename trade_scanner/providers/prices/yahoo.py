import logging

import pandas as pd
import yfinance as yf

from ...types import CurrencyPair, ISIN, Instrument, Ticker
from .base import DataProvider

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_MIC_SUFFIX: dict[str, str] = {
    "XAMS": ".AS",
    "XASX": ".AX",
    "XBOM": ".BO",
    "XBRU": ".BR",
    "XCSE": ".CO",
    "XDUB": ".IR",
    "XETR": ".DE",
    "XFRA": ".DE",
    "XHKG": ".HK",
    "XICE": ".IC",
    "XKRX": ".KS",
    "XLIS": ".LS",
    "XLON": ".L",
    "XMAD": ".MC",
    "XMEX": ".MX",
    "XMIL": ".MI",
    "XNAS": "",
    "XNSE": ".NS",
    "XNYS": "",
    "XOSL": ".OL",
    "XPAR": ".PA",
    "XSES": ".SI",
    "XSTO": ".ST",
    "XSWX": ".SW",
    "XTAE": ".TA",
    "XTKS": ".T",
    "XTSE": ".TO",
    "XTSX": ".V",
    "XWAR": ".WA",
}


class YahooProvider(DataProvider):
    @classmethod
    def to_provider_symbol(cls, instrument: Instrument) -> str:
        match instrument:
            case Ticker(mic=mic, symbol=symbol):
                suffix = _MIC_SUFFIX.get(mic, "") if mic else ""
                return f"{symbol}{suffix}"
            case ISIN(code=code):
                return code
            case CurrencyPair(base=base, counter=counter):
                return f"{base}{counter}=X"

    def _fetch_data(self, symbols: list[str], period: str, end: str | None = None) -> pd.DataFrame:
        kwargs: dict = {"period": period, "progress": False}
        if end is not None:
            kwargs["end"] = end
        if len(symbols) == 1:
            raw = yf.download(symbols[0], **kwargs)
            if not raw.empty and isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.droplevel(1)
            return raw

        return yf.download(
            symbols,
            **kwargs,
            group_by="ticker",
        )

    def _build_result(
        self,
        raw: pd.DataFrame,
        instruments: list[Instrument],
        yahoo_symbols: dict[Instrument, str],
        unique_ys: list[str],
    ) -> dict[Instrument, pd.DataFrame | None]:
        result: dict[Instrument, pd.DataFrame | None] = {}

        if raw.empty:
            return {inst: None for inst in instruments}

        if len(unique_ys) == 1:
            yahoo_sym = unique_ys[0]
            for inst in instruments:
                if yahoo_symbols[inst] == yahoo_sym:
                    result[inst] = raw if len(raw) > 1 else None
        else:
            for inst in instruments:
                ys = yahoo_symbols[inst]
                try:
                    df = raw[ys]
                    result[inst] = df if len(df) > 1 else None
                except KeyError:
                    result[inst] = None

        return result

    def get_history(
        self, instruments: list[Instrument], period: str = "1y",
        end: str | None = None,
    ) -> dict[Instrument, pd.DataFrame | None]:
        if not instruments:
            return {}

        yahoo_symbols: dict[Instrument, str] = {}
        for inst in instruments:
            yahoo_symbols[inst] = self.to_provider_symbol(inst)

        unique_ys = list(set(yahoo_symbols.values()))
        raw = self._fetch_data(unique_ys, period, end)
        return self._build_result(raw, instruments, yahoo_symbols, unique_ys)
