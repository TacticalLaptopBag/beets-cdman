from enum import Enum
from typing import Optional


class AudioPopulateMode(Enum):
    """
    How an AudioCD will populate its CD folders.
    
    :param SOFT_LINK: Music files are symlinked from the user's library to the CD folder
    :param HARD_LINK: Music files are hard linked from the user's library to the CD folder
    :param COPY: Music files are copied from the user's library to the CD folder
    :param CONVERT: Music files are converted to a variable bitrate MP3 from the user's library to the CD folder
    """
    
    SOFT_LINK = "soft_link"
    HARD_LINK = "hard_link"
    COPY = "copy"
    CONVERT = "convert"

    @classmethod
    def from_str(cls, string: str) -> Optional["AudioPopulateMode"]:
        """
        Parses a string as a valid enum value.
        If the provided string does not match any value,
        this function returns None
        """
        match string.lower():
            case "soft_link":
                return cls.SOFT_LINK
            case "hard_link":
                return cls.HARD_LINK
            case "copy":
                return cls.COPY
            case "convert":
                return cls.CONVERT
            case _:
                return None
