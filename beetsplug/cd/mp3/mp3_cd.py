from pathlib import Path
import shutil
from typing import override

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.util import unnumber_name
from beetsplug.cd.cd import CD
from beetsplug.cd.mp3.mp3_folder import MP3Folder


def _rmdir_job(path: Path):
    if Config.verbose:
        print(f"Remove folder {path}")

    if not Config.dry:
        shutil.rmtree(path)
    Stats.delete_folder()


def _mvdir_job(src_path: Path, dst_path: Path):
    if Config.verbose:
        print(f"Existing folder moved from {src_path} to {dst_path}")

    if not Config.dry:
        src_path.rename(dst_path)
    Stats.move_folder()


class MP3CD(CD):
    def __init__(
        self,
        path: Path,
        folders: list[MP3Folder],
        executor: DimensionalThreadPoolExecutor,
    ) -> None:
        super().__init__(path, executor)
        self._folders = folders

    @CD.pretty_type.getter
    def pretty_type(self) -> str:
        return "MP3"

    @CD.max_size.getter
    def max_size(self) -> float:
        # Approximately 701.3 MiB, which is the maximum size of a data CD,
        # according to K3b.
        return 735_397_888

    @override
    def _cleanup(self):
        # If the CD doesn't exist yet, there's nothing to cleanup
        if not self._path.exists(): return

        for existing_path in self._path.iterdir():
            # MP3 CDs are defined with folders first
            # (__root__ folder will cleanup itself later)
            if not existing_path.is_dir():
                continue

            # Check for existing folders
            existing_folder_name = unnumber_name(existing_path.name)
            existing_folders = [folder for folder in self._folders if folder.name == existing_folder_name]
            if len(existing_folders) == 0:
                # Folder is no longer in CD
                self._executor.submit(_rmdir_job, existing_path)
                continue
            
            # Confirm that the folders have been numberized
            for existing_folder in existing_folders:
                assert existing_folder._numberized

            # Check if this exact folder exists in its current position
            exact_folder = next(filter(lambda f: f.path == existing_path, existing_folders), None)
            if exact_folder is not None:
                # Path remains unchanged
                continue

            for existing_folder in existing_folders:
                if not existing_folder.path.exists():
                    # Folder has been renamed
                    _mvdir_job(existing_path, existing_folder.path)
                    break

        # Go through each folder and clean up their tracks
        for folder in self._folders:
            self._executor.submit(self._cleanup_path, folder.path, folder._tracks)
        return None

    @override
    def get_tracks(self):
        # Get all tracks from each folder
        return [track for folder in self._folders for track in folder.tracks]

    @override
    def is_empty(self) -> bool:
        if len(self._folders) == 0:
            return True
        
        for folder in self._folders:
            if len(folder.tracks) == 0:
                return True
        
        return False

    @override
    def numberize(self):
        folder_count = len(self._folders)
        folder_number = 1
        for folder in self._folders:
            folder.numberize(folder_number, folder_count)
            # If this is a root folder, it shouldn't affect the other folders' numbering
            if not folder.is_root:
                folder_number += 1
