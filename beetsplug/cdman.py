import shutil
import os
import re
import psutil
from typing import Iterable, Optional
from beets.plugins import BeetsPlugin
from beets.library import Library, parse_query_string, Item
from beets.ui import Subcommand
from optparse import Values
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor


"""
cdman:
    cds_path: ~/Music/CDs
    bitrate: 128
    cds:
        arcadian:
            - dirname: The Arcadian Wild
              query: album:"The Arcadian Wild"
            - dirname: Welcome
              query: album:"Welcome (Reframed)"
"""

class CDFolder:
    def __init__(self, item_dict: dict):
        self.dirname = item_dict["name"]
        self.query = item_dict["query"]

    def get_path(self, idx: int, cd_path: Path, total_count: int) -> Path:
        padding = len(str(total_count))
        padded_idx = str(idx + 1).rjust(padding, "0")
        indexed_dirname = f"{padded_idx} {self.dirname}"
        return cd_path / indexed_dirname

    def __str__(self) -> str:
        return f"{self.dirname}: {self.query}"


class CD:
    def __init__(self, path: Path):
        self.path = path
        self.folders: list[CDFolder] = []

    def __str__(self) -> str:
        folders = ""
        for i, folder in enumerate(self.folders):
            folders += str(folder)
            if i != len(self.folders) - 1:
                folders += ", "
        return f"{self.path}: [{folders}]"

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


class CDManPlugin(BeetsPlugin):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        hw_thread_count = psutil.cpu_count() or 4
        self.config.add({
            "cache_path": "~/.cache/beets-cdman",
            "bitrate": 128,
            "cds": [],
            "threads": hw_thread_count,
        })

        self.bitrate = self.config["bitrate"].get()
        self.cache_path = Path(self.config["cache_path"].get(str)).expanduser() # pyright: ignore[reportArgumentType]

    def commands(self):
        return [self._get_subcommand()]

    def _get_subcommand(self):
        cmd = Subcommand("cdman", help="manage MP3 CDs")
        def cdman_cmd(lib: Library, opts: Values, args: list[str]):
            self._cmd(lib, opts, args)
        cmd.func = cdman_cmd
        return cmd

    def _cmd(self, lib: Library, opts: Values, args: list[str]):
        cds = self._load_cds()

        max_workers: int = self.config["threads"].get(int) # pyright: ignore[reportAssignmentType]
        with ThreadPoolExecutor(max_workers) as executor:
            for cd in cds:
                # Find removed or reordered folders
                if cd.path.exists():
                    for existing_path in cd.path.iterdir():
                        if not existing_path.is_dir():
                            continue
                        new_path = cd.find_folder_path(existing_path.name)
                        if new_path == existing_path:
                            continue
                        if new_path is None:
                            print(f"Found existing folder `{existing_path.name}` that is no longer in CD `{cd.path.name}`. This folder will be removed.")
                            executor.submit(shutil.rmtree, existing_path)
                        else:
                            print(f"Existing folder `{existing_path.name}` has been reordered, renaming to `{new_path}`.")
                            executor.submit(os.rename, existing_path, new_path)

                # Convert
                for i, folder in enumerate(cd.folders):
                    query, _ = parse_query_string(folder.query, Item)
                    folder_path = folder.get_path(i, cd.path, len(cd.folders))
                    folder_path.mkdir(parents=True, exist_ok=True)
                    items = lib.items(query)
                    self._clean_folder(items, folder_path, executor)
                    self._convert_folder(items, folder_path, executor)
        return None

    def _clean_folder(self, items: Iterable[Item], folder_path: Path, executor: ThreadPoolExecutor):
        converted_paths: list[Path] = []
        for item in items:
            converted_paths.append(folder_path / (item.filepath.stem + ".mp3"))

        for path in folder_path.iterdir():
            if path.suffix != ".mp3":
                continue
            if not path.is_file() and not path.is_symlink():
                continue

            if path not in converted_paths:
                print(f"Found removed file `{path}` in folder `{folder_path}`. This file will be removed.")
                executor.submit(os.remove, path)

    def _convert_folder(self, items: Iterable[Item], folder_path: Path, executor: ThreadPoolExecutor):
        for item in items:
            converted_path = folder_path / (item.filepath.stem + ".mp3")
            if converted_path.exists():
                if converted_path.is_file() or converted_path.is_symlink():
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
        # Make directory structure in cache path in the following format:
        # cd-name/folder-name/file.mp3
        tmp_path = self.cache_path / dest_file.parent.parent.name / dest_file.parent.name
        tmp_file_path = tmp_path / dest_file.name
        if tmp_file_path.exists():
            os.remove(tmp_file_path)

        # ffmpeg -i "$flac_file" -hide_banner -loglevel error -acodec libmp3lame -ar 44100 -b:a 128k -vn "$output_file"
        subprocess.run(
            [
                "ffmpeg",
                "-i", str(file),
                "-hide_banner",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-b:a", f"{self.bitrate}k",
                "-vn", str(tmp_file_path)
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # TODO: Does this even solve anything?
        # What if the user cancels the command while moving the file?
        # Now we're back to the original problem, just a lot more unlikely
        tmp_file_path.rename(dest_file)
        return None

    def _load_cds(self) -> list[CD]:
        cds_path = Path(self.config["cds_path"].get(str)) # pyright: ignore[reportArgumentType]
        conf_cds: dict = self.config["cds"].get(dict) # pyright: ignore[reportAssignmentType]
        cd_names = conf_cds.keys()

        cds: list[CD] = []
        for cd_name in cd_names:
            cd_path = cds_path / cd_name
            cd = CD(cd_path)
            for cd_item_dict in conf_cds[cd_name]:
                cd_folder = CDFolder(cd_item_dict)
                cd.folders.append(cd_folder)
            cds.append(cd)
        return cds
