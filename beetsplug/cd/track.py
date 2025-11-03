from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, override
import ffmpeg

from beetsplug.util import unnumber_name


class CDTrack(ABC):
    """
    A track found from a defined CD
    """

    def __init__(self, src_path: Path, dst_directory: Path):
        self._src_path = src_path
        self.dst_directory = dst_directory
        self._dst_path: Optional[Path] = None
        self._name = unnumber_name(src_path.stem)
        self.__src_stream: Optional[Any] = None
        self.__dst_stream: Optional[Any] = None

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

    @property
    def _src_stream(self) -> Optional[Any]:
        if self.__src_stream is None:
            self.__src_stream = self._get_stream(self.src_path)

        return self.__src_stream

    @property
    def _dst_stream(self) -> Optional[Any]:
        if self.__dst_stream is None:
            self.__dst_stream = self._get_stream(self.dst_path)

        return self.__dst_stream

    @classmethod
    def _get_stream(cls, path: Path) -> Any:
        try:
            probe = ffmpeg.probe(str(path))
        except ffmpeg.Error:
            return None

        stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        return stream

    @abstractmethod
    def _get_dst_extension(self) -> str:
        """
        Returns the extension for the destination file, including the leading period.
        """
        pass

    def set_dst_path(self, track_number: int, track_count: int):
        """
        Numbers the track and determines where it will be populated.
        """
        digit_length = max(2, len(str(track_count)))
        numbered = str(track_number).zfill(digit_length)
        self._dst_path = self.dst_directory / f"{numbered} {self._name}{self._get_dst_extension()}"
        return None

    def is_similar(self, other_path: Path) -> bool:
        """
        Determines whether this track is similar enough to the provided path
        to be considered the same.
        """
        # There can be very small differences if source and dest teeter on the edge of .5
        # A difference of 1 second is likely the same song
        src_duration = round(self.get_duration(self._src_path))
        dst_duration = round(self.get_duration(other_path))
        duration_diff = abs(src_duration - dst_duration)
        return duration_diff <= 1

    def get_size(self) -> int:
        """
        Gets the size of the track file in bytes
        """
        if self._dst_path is None:
            raise RuntimeError("set_dst_path must be run before get_size!")
        return self._dst_path.stat().st_size

    def get_duration(self, path: Path) -> float:
        """
        Gets the length of the track in seconds
        """
        if not path.exists():
            return 0.0

        if path == self.src_path:
            stream = self._src_stream
        elif path == self.dst_path:
            stream = self._dst_stream
        else:
            stream = self._get_stream(path)

        if stream is None:
            return 0.0

        duration = float(stream["duration"])
        return duration

    @abstractmethod
    def populate(self):
        pass

    @abstractmethod
    def __len__(self):
        """
        Gets the size of the track as it is measured by its CD.
        """
        raise RuntimeError("__len__ is not overridden!")

    @override
    def __str__(self) -> str:
        return f"CDTrack(name={self.name}, src_path={self.src_path}, dst_path={self.dst_path})"

