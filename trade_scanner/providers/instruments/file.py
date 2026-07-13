from .base import InstrumentListProvider


class FileProvider(InstrumentListProvider):
    def __init__(self, path: str) -> None:
        self.path = path

    def get_instruments(self) -> list[str]:
        result: list[str] = []
        with open(self.path) as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    result.append(line)
        return result
