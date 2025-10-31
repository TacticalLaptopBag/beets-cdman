from enum import Enum


class AudioPopulateMode(Enum):
    SOFT_LINK = "soft_link"
    HARD_LINK = "hard_link"
    COPY = "copy"
