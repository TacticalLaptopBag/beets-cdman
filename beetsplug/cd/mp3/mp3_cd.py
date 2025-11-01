from pathlib import Path
import shutil
from typing import override

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.util import unnumber_name
from beetsplug.cd.cd import CD
from beetsplug.cd.mp3.mp3_folder import MP3Folder

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
        return 735_397_888

    @override
    def cleanup(self):
        if not self._path.exists(): return
        for existing_path in self._path.iterdir():
            if not existing_path.is_dir():
                continue

            existing_folder_name = unnumber_name(existing_path.name)
            existing_folders = [folder for folder in self._folders if folder.name == existing_folder_name]
            if len(existing_folders) == 0:
                # Folder is no longer in CD
                self._executor.submit(_rmdir_job, existing_path)
                continue
            
            for existing_folder in existing_folders:
                assert existing_folder._numberized
            exact_folder = next(filter(lambda f: f.path == existing_path, existing_folders), None)
            if exact_folder is not None:
                # Path remains unchanged
                continue

            for existing_folder in existing_folders:
                if not existing_folder.path.exists():
                    # Folder has been renamed
                    _mvdir_job(existing_path, existing_folder.path)
                    break

        for folder in self._folders:
            self._cleanup_path(folder.path, folder._tracks)
        return None

    @override
    def get_tracks(self):
        return [track for folder in self._folders for track in folder.tracks]

    @override
    def numberize(self):
        folder_count = len(self._folders)
        folder_number = 1
        for folder in self._folders:
            folder.numberize(folder_number, folder_count)
            if not folder.is_root:
                folder_number += 1
