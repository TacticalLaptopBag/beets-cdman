from abc import ABC, abstractmethod
from collections.abc import Sequence
import os
from pathlib import Path
from typing import Iterator
from magic import Magic
from more_itertools import divide

from ..stats import Stats
from ..config import Config
from ..dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from ..util import unnumber_name
from .track import CDTrack


# TODO: Calculate splits

def _rm_job(path: Path):
    if Config.verbose:
        print(f"Removed track {path}")

    if not Config.dry:
        os.remove(path)
    Stats.track_removed()


def _mv_job(src_path: Path, dst_path: Path):
    if Config.verbose:
        print(f"Existing track moved from {src_path} to {dst_path}")
    
    if not Config.dry:
        src_path.rename(dst_path)
    Stats.track_moved()


class CD(ABC):
    def __init__(self, path: Path, executor: DimensionalThreadPoolExecutor) -> None:
        super().__init__()
        self._path = path
        self._executor = executor

    @property
    def path(self) -> Path:
        return self._path

    @abstractmethod
    def cleanup(self):
        pass

    def _cleanup_path(self, path: Path, tracks: Sequence[CDTrack]):
        for existing_path in path.iterdir():
            if not existing_path.is_file():
                continue
            
            mimetype = Magic(mime=True).from_file(existing_path)
            if not mimetype.startswith("audio/"):
                continue

            existing_track_name = unnumber_name(existing_path.name)
            existing_track = next((track for track in tracks if track.name == existing_track_name), None)
            if existing_track is None:
                # Track is no longer in CD
                self._executor.submit(_rm_job, existing_path)
                continue

            if existing_track.dst_path == existing_path:
                # Path remains unchanged
                continue
            
            if existing_track.is_similar(existing_path):
                # Path changed, and is likely the same song
                self._executor.submit(_mv_job, existing_path, existing_track.dst_path)
                continue
            
            # Does not appear to be the same song
            self._executor.submit(_rm_job, existing_path)
    
    def populate(self):
        tracks = self.get_tracks()
        for track_chunk in divide(self._executor.max_workers, tracks):
            self._executor.submit(self._populate_chunk, track_chunk)
        return None

    def _populate_chunk(self, chunk: Iterator[CDTrack]):
        for track in chunk:
            self._executor.submit(track.populate)
        return None

    @abstractmethod
    def get_tracks(self) -> Sequence[CDTrack]:
        pass

    @abstractmethod
    def numberize(self):
        pass
