from pathlib import Path
import shutil
from typing import override

from beetsplug.cd.track import CDTrack

from ...stats import Stats
from ...config import Config
from ...dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from ...util import unnumber_name
from ..cd import CD
from .mp3_folder import MP3Folder

# TODO: __root__ folder should go to CD root!


def _rmdir_job(path: Path):
    if Config.verbose:
        print(f"Remove folder {path}")

    if not Config.dry:
        shutil.rmtree(path)
    Stats.folder_removed()


def _mvdir_job(src_path: Path, dst_path: Path):
    if Config.verbose:
        print(f"Existing folder moved from {src_path} to {dst_path}")

    if not Config.dry:
        src_path.rename(dst_path)
    Stats.folder_moved()


class MP3CD(CD):
    def __init__(
        self,
        path: Path,
        folders: list[MP3Folder],
        executor: DimensionalThreadPoolExecutor,
    ) -> None:
        super().__init__(path, executor)
        self._folders = folders

    @CD.max_size.getter
    def max_size(self) -> float:
        return 700_000_000

    @override
    def cleanup(self):
        for existing_path in self._path.iterdir():
            if not existing_path.is_dir():
                continue

            existing_folder_name = unnumber_name(existing_path.name)
            existing_folder = next((folder for folder in self._folders if folder.name == existing_folder_name), None)
            if existing_folder is None:
                # Folder is no longer in CD
                self._executor.submit(_rmdir_job, existing_path)
                continue
            
            assert existing_folder._numberized
            if existing_folder.path == existing_path:
                # Path remains unchanged
                continue

            # Folder has been renamed
            _mvdir_job(existing_path, existing_folder.path)

        for folder in self._folders:
            self._cleanup_path(folder.path, folder._tracks)
        return None

    @override
    def get_tracks(self):
        return [track for folder in self._folders for track in folder.tracks]

    @override
    def numberize(self):
        folder_count = len(self._folders)
        for i, folder in enumerate(self._folders):
            folder.numberize(i+1, folder_count)
