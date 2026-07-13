from .base import DataProvider
from .yahoo import YahooProvider

PRICES_PROVIDERS: dict[str, type[DataProvider]] = {
    "yahoo": YahooProvider,
}
