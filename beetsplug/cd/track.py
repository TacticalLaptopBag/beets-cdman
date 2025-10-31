from abc import ABC, abstractmethod
import math
from pathlib import Path
from typing import Optional, override
import ffmpeg

from ..util import unnumber_name


class CDTrack(ABC):
    def __init__(self, src_path: Path, dst_directory: Path):
        self._src_path = src_path
        self.dst_directory = dst_directory
        self._dst_path: Optional[Path] = None
        self._name = unnumber_name(src_path.stem)

    @property
    def dst_path(self) -> Path:
        if self._dst_path is None:
            raise RuntimeError("Attempt to access dst_path before it has been set")
        return self._dst_path

    @property
    def src_path(self) -> Path:
        return self._src_path

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def _get_dst_extension(self) -> str:
        """
        Returns the extension for the destination file, including the leading period.
        """
        pass

    def set_dst_path(self, track_number: int, track_count: int):
        digit_length = max(2, len(str(track_count)))
        numbered = str(track_number).zfill(digit_length)
        self._dst_path = self.dst_directory / f"{numbered} {self._name}{self._get_dst_extension()}"
        return None

    def is_similar(self, other_path: Path) -> bool:
        src_duration = math.ceil(self.get_duration(self._src_path))
        dst_duration = math.ceil(self.get_duration(other_path))
        return src_duration == dst_duration

    def get_size(self) -> int:
        if self._dst_path is None:
            raise RuntimeError("set_dst_path must be run before get_size!")
        return self._dst_path.stat().st_size

    @classmethod
    def get_duration(cls, path: Path) -> float:
        if not path.exists():
            return 0.0

        try:
            probe = ffmpeg.probe(str(path))
        except ffmpeg.Error:
            return 0.0

        stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        if stream is None:
            return 0.0

        duration = float(stream["duration"])
        return duration

    @abstractmethod
    def populate(self):
        pass

    @abstractmethod
    def __len__(self):
        raise RuntimeError("__len__ is not overridden!")

    @override
    def __str__(self) -> str:
        return f"CDTrack(name={self.name}, src_path={self.src_path}, dst_path={self.dst_path})"

