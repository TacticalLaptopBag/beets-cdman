from pathlib import Path
from typing import override

from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.cd.cd import CD
from beetsplug.cd.audio.audio_track import AudioTrack


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

    @CD.pretty_type.getter
    def pretty_type(self) -> str:
        return "Audio"

    @CD.max_size.getter
    def max_size(self) -> float:
        # 80 minutes of audio in seconds
        return 80 * 60

    @override
    def _cleanup(self):
        self._cleanup_path(self._path, self._tracks)

    @override
    def get_tracks(self):
        return self._tracks

    @override
    def is_empty(self) -> bool:
        return len(self._tracks) == 0

    @override
    def numberize(self):
        track_count = len(self._tracks)
        for i, track in enumerate(self._tracks):
            track.set_dst_path(i+1, track_count)
