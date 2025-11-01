from enum import Enum


class AudioPopulateMode(Enum):
    SOFT_LINK = "soft_link"
    HARD_LINK = "hard_link"
    COPY = "copy"

    @classmethod
    def from_str(cls, string: str):
        match string.lower():
            case "soft_link":
                return cls.SOFT_LINK
            case "hard_link":
                return cls.HARD_LINK
            case "copy":
                return cls.COPY
            case _:
                return None
