from abc import ABC, abstractmethod
from collections.abc import Sequence
import os
from pathlib import Path
from typing import Iterator
from magic import Magic
from more_itertools import divide

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.util import unnumber_name
from beetsplug.cd.track import CDTrack


def _rm_job(path: Path):
    if Config.verbose:
        print(f"Removed track {path}")

    if not Config.dry:
        os.remove(path)
    Stats.delete_track()


def _mv_job(src_path: Path, dst_path: Path):
    if Config.verbose:
        print(f"Existing track moved from {src_path} to {dst_path}")
    
    if not Config.dry:
        src_path.rename(dst_path)
    Stats.move_track()


class CDSplit:
    """
    A section of a populated CD that fits onto a single physical CD.
    """
    def __init__(
        self,
        init: CDTrack,
        size: float = 0.0,
    ) -> None:
        self.start = init
        self.end = init
        self.size = size


class CD(ABC):
    """
    A representation of a user-defined CD
    """
    
    def __init__(self, path: Path, executor: DimensionalThreadPoolExecutor) -> None:
        super().__init__()
        self._path = path
        self._executor = executor
        self._test_size = -1

    @property
    def pretty_type(self) -> str:
        raise RuntimeError("pretty_type is not overridden!")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def max_size(self) -> float:
        raise RuntimeError("max_size is not overridden!")

    def cleanup(self):
        """
        Removes tracks that no longer exist in the CD,
        and renames tracks that have been reordered.
        """
        self._executor.submit(self._cleanup)

    @abstractmethod
    def _cleanup(self):
        pass

    def _cleanup_path(self, path: Path, tracks: Sequence[CDTrack]):
        # If the directory doesn't exist, don't bother cleaning it up
        if not path.exists(): return
        for existing_path in path.iterdir():
            # If not a file, don't bother, it wasn't made by cdman
            if not existing_path.is_file() and not existing_path.is_symlink():
                continue
            
            # Skip over all non-audio files
            mime_path = existing_path.resolve() if existing_path.is_symlink() else existing_path
            mimetype = Magic(mime=True).from_file(mime_path)
            if not mimetype.startswith("audio/"):
                continue

            # Check for existing tracks
            existing_track_name = unnumber_name(existing_path.stem)
            existing_tracks = [track for track in tracks if track.name == existing_track_name]
            if len(existing_tracks) == 0:
                # Track is no longer in CD
                self._executor.submit(_rm_job, existing_path)
                continue

            # Check if this track already exists in this position
            exact_track = next(filter(lambda t: t.dst_path == existing_path, existing_tracks), None)
            if exact_track is not None:
                # Path remains unchanged
                continue
            
            found_track = False
            for existing_track in existing_tracks:
                if existing_track.is_similar(existing_path) and not existing_track.dst_path.exists():
                    # Path changed, and is likely the same song
                    self._executor.submit(_mv_job, existing_path, existing_track.dst_path)
                    found_track = True
                    break
            if found_track:
                continue
            
            # Does not appear to be the same song
            self._executor.submit(_rm_job, existing_path)
    
    def populate(self):
        """
        Takes the found tracks from the user's library and puts them into CD folders.
        """

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
    def is_empty(self) -> bool:
        pass

    @abstractmethod
    def numberize(self):
        pass

    def calculate_splits(self) -> Sequence[CDSplit]:
        """
        Determine where the CD must be split to fit onto a physical CD.
        """
        
        splits: list[CDSplit] = []
        tracks = self.get_tracks()
        if len(tracks) == 0:
            return []

        next_split = CDSplit(tracks[0])
        max_size = self.max_size if self._test_size < 0 else self._test_size
        for track in tracks:
            track_size = len(track)

            if next_split.size + track_size > max_size:
                # Too big for one CD
                splits.append(next_split)
                next_split = CDSplit(track, track_size)
            else:
                next_split.size += track_size
                
            next_split.end = track
        
        splits.append(next_split)
        return splits
