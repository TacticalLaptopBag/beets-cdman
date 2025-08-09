import os
import re
from abc import ABC
from pathlib import Path
import shutil
from typing import Optional, override
from beets.library import Library, parse_query_string, Item
from magic import Magic

from ..dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from ..util import get_directory_audio_length, get_song_length, item_to_track_listing
from .cd import CD


MAX_SIZE_AUDIO = 4_800


class AudioCD(CD):
    NAME_REGEX = r"^\d+\s+(.*$)"

    def __init__(self, lib: Library, path: Path, dry: bool):
        super().__init__(lib, path, dry)
        self.track_queries: list[str] = []
        self._track_paths: Optional[dict[Path, Path]] = None

    @property
    @override
    def size_warning(self) -> str:
        return (
            f"Audio CD {self.path.name} is {self.get_size() / 60:.1f} minutes long, "
            f"which is longer than {MAX_SIZE_AUDIO / 60} minutes!"
        )

    @override
    def get_size(self) -> int | float:
        return get_directory_audio_length(self.path)

    @override
    def _get_track_size(self, file: Path) -> int | float:
        return get_song_length(file)

    @override
    def _get_max_size(self) -> int | float:
        return MAX_SIZE_AUDIO

    @override
    def _get_queries(self) -> list[str]:
        return self.track_queries
        
    @override
    def cleanup(self, executor: DimensionalThreadPoolExecutor):
        for existing_path in self.path.iterdir():
            if not existing_path.is_file():
                continue

            mimetype = Magic(mime=True).from_file(existing_path)
            if not mimetype.startswith("audio/"):
                continue

            # Existing track found
            new_path = self.find_track_path(existing_path.name)
            if new_path == existing_path:
                # Track not removed or reordered
                continue

            if new_path is None:
                # Track not found in CD, must have been removed
                print(f"Found existing track `{existing_path.name}` that is no longer in CD `{self.path.name}`. This track will be removed.")
                executor.submit(os.remove, existing_path)
                continue

            # Track was found in CD, but at a different position
            print(f"Existing track `{existing_path.name}` has been reordered, renaming to `{new_path}`.")
            executor.submit(os.rename, existing_path, new_path)
        return None

    @override
    def convert(self, executor: DimensionalThreadPoolExecutor):
        for src_path in self.track_paths:
            dest_path = self.track_paths[src_path]
            def job(src: Path, dest: Path):
                print(f"Copying `{src.name}` to `{dest.name}` in {dest.parent}")
            executor.submit(shutil.copy2, src_path, dest_path)

    @property
    def track_paths(self) -> dict[Path, Path]:
        if self._track_paths is None:
            # Get all track names first
            track_names: dict[Path, str] = {}
            for track_query in self.track_queries:
                query, _ = parse_query_string(track_query, Item)
                items = self.lib.items(query)
                for item in items:
                    track_name = item.filepath.name
                    track_name_match = re.match(AudioCD.NAME_REGEX, item.filepath.name)
                    if track_name_match is not None:
                        match_group = track_name_match.group(1)
                        if type(track_name) == str:
                            track_name = match_group

                    track_names[item.filepath] = track_name

            # Go through every track name and remap it to its final name
            zero_count = len(str(len(track_names)))
            self._track_paths = {}
            for i, track_path in enumerate(track_names):
                track_name = track_names[track_path]
                self._track_paths[track_path] = self.path / f"{str(i).zfill(zero_count)} {track_name}"
                
        return self._track_paths

    def find_track(self, track_name: str) -> Optional[Path]:
        for track_src in self.track_paths:
            if track_name in track_src.name:
                return track_src
        return None

    def find_track_path(self, track_name: str) -> Optional[Path]:
        name_match = re.match(AudioCD.NAME_REGEX, track_name)
        if name_match is None:
            # track_name wasn't in the expected format
            return None

        # Ignore the numbers, the capture group should be everything after
        # the track's position
        track_title = name_match.group(1)
        if type(track_title) != str:
            # Something went wrong, maybe nothing was captured?
            return None
        
        # We now have the name of the track,
        # let's see if it's even in this CD
        track_src = self.find_track(track_title)
        if track_src is None:
            # Track is not in CD
            return None

        track_dest = self.track_paths[track_src]
        return track_dest
    