from dataclasses import dataclass
from typing import Optional


@dataclass
class ReupItem:
    url: str
    content: str
    pin: Optional[str] = None

    @property
    def is_uploaded(self) -> bool:
        return self.pin is not None

    @property
    def is_success(self) -> bool:
        return self.pin not in (None, "fail", "skip")

    @property
    def is_fail(self) -> bool:
        return self.pin == "fail"

    @property
    def is_skip(self) -> bool:
        return self.pin == "skip"
