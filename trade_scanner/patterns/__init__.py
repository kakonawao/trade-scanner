from .base import Pattern
from .base import PatternError as PatternError
from .base import Result as Result
from .flag import BullFlag
from .vcp import VCP

PATTERNS: dict[str, type[Pattern]] = {
    "vcp": VCP,
    "flag": BullFlag,
}
