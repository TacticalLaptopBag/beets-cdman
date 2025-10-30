from pathlib import Path

from ...dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from .mp3track import MP3Track


class MP3Folder:
    def __init__(self, path: Path, tracks: list[MP3Track], executor: DimensionalThreadPoolExecutor):
        self._path = path
        self._name = path.name
        self._tracks = tracks
        self._numberized = False
        self._executor = executor

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        return self._name

    def numberize(self, folder_number: int, folder_count: int):
        if self._numberized:
            raise RuntimeError(f"Folder at {self._path} is already numberized!")
            
        self._numberized = True
        digit_length = max(2, len(str(folder_count)))
        numbered = str(folder_number).zfill(digit_length)
        self._path = self._path.parent / f"{numbered} {self._path.stem}"

        track_count = len(self._tracks)
        for i, track in enumerate(self._tracks):
            track.set_dst_path(i+1, track_count)
        return None
