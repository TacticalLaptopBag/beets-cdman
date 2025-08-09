import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable, Optional, override
from beets.library import Library, parse_query_string, Item
from more_itertools import divide

from ..dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from ..util import get_directory_size, get_song_length
from .cd import CD
from .cd_folder import CDFolder

MAX_SIZE_MP3 = 700 * 1024 * 1024

MP3CDDefinition = dict[str, list[dict[str, str]]]


class MP3CD(CD):
    def __init__(self, lib: Library, path: Path, dry: bool, bitrate: int):
        super().__init__(lib, path, dry)
        self.folders: list[CDFolder] = []
        self.bitrate = bitrate
        self.dry = dry

    def __str__(self):
        folders = ""
        for i, folder in enumerate(self.folders):
            folders += str(folder)
            if i != len(self.folders) - 1:
                folders += ", "
        return f"{self.path}: [{folders}]"

    @property
    @override
    def size_warning(self) -> str:
        return (
            f"MP3 CD {self.path.name} is {self.get_size() / 1024 / 1024:.1f} MiB, "
            f"which is larger than {MAX_SIZE_MP3 / 1024 / 1024} MiB!"
        )

    def find_folder_path(self, dirname: str) -> Optional[Path]:
        """
        Extracts the path of the folder from the given dirname,
        and then returns the current dirname of that folder.
        Example: "05 Lemaitre" would return "07 Lemaitre" if Lemaitre was moved to position 7.
        It could return None if Lemaitre is not in this CD.
        """
        # First we need to extract the actual name from the given directory name
        # Currently dirname is expected to be in the example format of "09 Folder"
        name_regex = r"^\d+\s+(.*$)"
        name_match = re.match(name_regex, dirname)
        if name_match is None:
            # dirname isn't in the expected format
            return None

        # Ignore the numbers, the capture group should be everything after
        # the folder's position
        folder_name = name_match.group(1)
        if type(folder_name) != str:
            # Something went wrong, maybe nothing was captured?
            return None

        # We now have the name of the folder,
        # let's see if it's even in this CD
        folder_idx = self.find_folder(folder_name)
        if folder_idx == -1:
            # Folder is not in CD
            return None
        folder = self.folders[folder_idx]
        
        # Folder is in CD, retrieve the path and return it
        return folder.get_path(folder_idx, self.path, len(self.folders))

    def has_folder(self, dirname: str) -> bool:
        return self.find_folder(dirname) != -1

    def find_folder(self, dirname: str) -> int:
        """
        Gets the index of the folder provided
        """
        for i, folder in enumerate(self.folders):
            if folder.dirname == dirname:
                return i
        return -1

    @override
    def get_size(self) -> int | float:
        """
        Returns size of CD in bytes as an int.
        """
        return get_directory_size(self.path)

    @override
    def _get_track_size(self, file: Path) -> int | float:
        return file.stat().st_size

    @override
    def _get_max_size(self) -> int | float:
        return MAX_SIZE_MP3

    @override
    def _get_queries(self) -> list[str]:
        return [folder.query for folder in self.folders]

    @override
    def cleanup(self, executor: DimensionalThreadPoolExecutor):
        for existing_path in self.path.iterdir():
            if not existing_path.is_dir():
                continue

            # Existing CD folder found.
            new_path = self.find_folder_path(existing_path.name)
            if new_path == existing_path:
                # Folder has not been removed or reordered
                continue

            if new_path is None:
                # Folder was not found in CD, must have been removed
                print(f"Found existing folder `{existing_path.name}` that is no longer in CD `{self.path.name}`. This folder will be removed.")
                executor.submit(shutil.rmtree, existing_path)
                continue

            # Folder was found in CD, but at a different position
            print(f"Existing folder `{existing_path.name}` has been reordered, renaming to `{new_path}`.")
            executor.submit(os.rename, existing_path, new_path)
        return None

    @override
    def convert(self, executor: DimensionalThreadPoolExecutor):
        for i, folder in enumerate(self.folders):
            query, _ = parse_query_string(folder.query, Item)
            folder_path = folder.get_path(i, self.path, len(self.folders))
            folder_path.mkdir(parents=True, exist_ok=True)
            items = self.lib.items(query)
            self._clean_folder(items, folder_path, executor)
            self._convert_folder(items, folder_path, executor)
        return None

    def _clean_folder(self, items: Iterable[Item], folder_path: Path, executor: DimensionalThreadPoolExecutor):
        converted_paths: list[Path] = [folder_path / (item.filepath.stem + ".mp3") for item in items]

        for path in folder_path.iterdir():
            if path.suffix != ".mp3":
                continue
            if not path.is_file():
                continue

            if path not in converted_paths:
                print(f"Found removed file `{path}`. This file will be removed.")
                executor.submit(os.remove, path)

    def _convert_folder(self, items: Iterable[Item], folder_path: Path, executor: DimensionalThreadPoolExecutor):
        for items_chunk in divide(executor.max_workers, items):
            executor.submit(self._convert_folder_chunk, items_chunk, folder_path, executor)
        return None

    def _convert_folder_chunk(self, items: Iterable[Item], folder_path: Path, executor: DimensionalThreadPoolExecutor):
        for item in items:
            converted_path = folder_path / (item.filepath.stem + ".mp3")
            if converted_path.exists():
                if converted_path.is_file():
                    converted_duration = math.ceil(get_song_length(converted_path))
                    orig_duration = math.ceil(get_song_length(item.filepath))
                    if abs(converted_duration - orig_duration) > 1:
                        print(f"Found partially converted file `{converted_path}`. This file will be reconverted.")
                        os.remove(converted_path)
                    else:
                        print(f"Skipping `{item.filepath.name}` as it is already in {folder_path}")
                        continue
                else:
                    print(f"FATAL: {converted_path} already exists, but it isn't a file!")
                    print("Unsure how to proceed, you should probably manually intervene here.")
                    exit(1)

            def job(src_file: Path, dest_file: Path):
                print(f"Converting `{src_file.name}` to {self.bitrate}K MP3 in {dest_file.parent}")
                self._convert_file(src_file, dest_file)

            executor.submit(job, item.filepath, converted_path)
        return None

    def _convert_file(self, file: Path, dest_file: Path):
        # TODO: convert plugin? 🥺👉👈
        # ffmpeg -i "$flac_file" -hide_banner -loglevel error -acodec libmp3lame -ar 44100 -b:a 128k -vn "$output_file"
        if self.dry:
            return None
        
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(file),
                "-hide_banner",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-b:a", f"{self.bitrate}k",
                "-vn", str(dest_file)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            sys.stderr.write(f"Error converting `{file}`! Look in `{dest_file.parent}` for ffmpeg logs.\n")
            stdout_log_path = dest_file.with_suffix(".stdout.log")
            stderr_log_path = dest_file.with_suffix(".stderr.log")
            with stdout_log_path.open("wb") as stdout_log:
                stdout_log.write(result.stdout)
            with stderr_log_path.open("wb") as stderr_log:
                stderr_log.write(result.stderr)

        return None
