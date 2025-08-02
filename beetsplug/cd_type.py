from enum import Enum


class CDType(Enum):
    AUDIO = 0
    MP3 = 1

    @classmethod
    def from_name(cls, name: str) -> "CDType":
        return cls[name.upper()]
