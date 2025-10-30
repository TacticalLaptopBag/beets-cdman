from pathlib import Path
from typing import override
from more_itertools import divide

from ...dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from ..cd import CD
from .audiotrack import AudioTrack


class AudioCD(CD):
    def __init__(
        self,
        path: Path,
        tracks: list[AudioTrack],
        executor: DimensionalThreadPoolExecutor,
    ) -> None:
        super().__init__(path, executor)
        self._tracks = tracks
        self._executor = executor

    @override
    def cleanup(self):
        self._cleanup_path(self._path, self._tracks)

    @override
    def populate(self):
        for track_chunk in divide(self._executor.max_workers, self._tracks):
            self._executor.submit(self._populate_chunk, track_chunk)
        return None

    @override
    def get_tracks(self):
        return self._tracks

    @override
    def numberize(self):
        track_count = len(self._tracks)
        for i, track in enumerate(self._tracks):
            track.set_dst_path(i+1, track_count)
