import math
import sys
import shutil
import os
import re
from threading import Thread
import psutil
import subprocess
import ffmpeg
from typing import Iterable, Optional
from beets.plugins import BeetsPlugin
from beets.library import Library, parse_query_string, Item
from beets.ui import Subcommand
from optparse import Values
from pathlib import Path
from confuse import RootView, YamlSource
from more_itertools import divide

from beetsplug.printer import Printer
from beetsplug.stats import Stats

from .dimensional_thread_pool_executor import DimensionalThreadPoolExecutor


verbose = False

def log(*values: object):
    if not verbose: return
    print(*values)


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

CDDefinition = dict[str, list[dict[str, str]]]

class CDFolder:
    def __init__(self, item_dict: dict[str, str]):
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
            "cds_path": "~/Music/CDs",
            "bitrate": 128,
            "threads": hw_thread_count,
        })

        self.stats = Stats()
        self.summary_thread = Thread(
            target=self.summary_thread_function,
            name="Summary",
        )
        
        self.bitrate = self.config["bitrate"].get(int)
        self.max_threads: int = self.config["threads"].get(int) # pyright: ignore[reportAttributeAccessIssue]
        if self.max_threads <= 0:
            raise ValueError("Config field 'threads' must be a positive integer!")

    def summary_thread_function(self):
        p = Printer()
        while True:
            with self.stats.changed_cond:
                self.stats.changed_cond.wait()

            with self.stats.lock:
                if verbose and not self.stats.done:
                    continue
                p.print_line(0, f"Tracks converted: {self.stats.convert_count}")
                p.print_line(1, f"Tracks skipped: {self.stats.skip_count}")
                p.print_line(2, f"Tracks deleted: {self.stats.removed_count}")
                p.print_line(3, f"Folders moved: {self.stats.folders_moved_count}")
                p.print_line(4, f"Failed conversions: {self.stats.failed_convert_count}")
                if self.stats.done:
                    break

    def commands(self):
        return [self._get_subcommand()]

    def _get_subcommand(self):
        cmd = Subcommand("cdman", help="manage MP3 CDs")
        cmd.parser.add_option(
            "--threads", "-t",
            help = 
                "The maximum number of threads to use. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--bitrate", "-b",
            help = 
                "The bitrate (in kbps) to use when converting files to MP3. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--dry", "-d",
            help =
                "When run with this flag present, 'cdman' goes through "
                "all the motions of a normal command, but doesn't "
                "actually perform any conversions. "
                "Note that directories may be created in your cds_path directory.",
            action="store_true",
        )
        cmd.parser.add_option(
            "--list-unused", "-l",
            help = 
                "Lists all tracks in your library that are not in any CD definitions.",
            action="store_true",
        )
        cmd.parser.add_option(
            "--verbose", "-v",
            help = 
                "Print extra terminal output",
            action="store_true", 
        )
        def cdman_cmd(lib: Library, opts: Values, args: list[str]):
            self._cmd(lib, opts, args)
        cmd.func = cdman_cmd
        return cmd

    def _cmd(self, lib: Library, opts: Values, args: list[str]):
        self.executor = DimensionalThreadPoolExecutor(self.max_threads)
        
        cds: list[CD]
        if len(args) == 0:
            cds = self._load_cds_from_config()
        else:
            cds = []
            for arg in args:
                arg_path = Path(arg)
                if not arg_path.exists():
                    log(f"No such file or directory: {arg_path}")
                    continue
                cds.extend(self._load_cds_from_path(Path(arg)))
        
        if opts.threads is not None:
            log(f"Overriding config value 'threads': using {opts.threads} instead of {self.max_threads}")
            self.max_threads = opts.threads

        if opts.bitrate is not None:
            log(f"Overriding config value 'bitrate': using {opts.bitrate} instead of {self.bitrate}")
            self.bitrate = opts.bitrate

        global verbose
        verbose = opts.verbose

        self.summary_thread.start()

        self.dry = opts.dry

        if opts.list_unused:
            self._list_unused(cds, lib)
        else:
            self._populate_cds(cds, lib)

        self.executor.shutdown()
        with self.stats.lock:
            self.stats.done = True
        self.stats.notify()
        self.summary_thread.join()
        return None

    def _item_to_track_listing(self, item: Item) -> str:
        return f"{item.get("artist")} - {item.get("album")} - {item.get("title")}"

    def _list_unused(self, cds: list[CD], lib: Library):
        unused_tracks = set([self._item_to_track_listing(item) for item in lib.items()])
        removed_tracks: set[str] = set()
        for cd in cds:
            for folder in cd.folders:
                folder_query, _ = parse_query_string(folder.query, Item)
                folder_items = lib.items(folder_query)
                for item in folder_items:
                    track = self._item_to_track_listing(item)
                    if track not in removed_tracks:
                        unused_tracks.remove(track)
                        removed_tracks.add(track)
            
        if len(unused_tracks) == 0:
            log("No track has been left untouched.")
            return None

        log("Tracks not in any defined CD:")
        for unused_track in unused_tracks:
            log(unused_track)
        return None

    def _rm_folder(self, folder_path: Path):
        removed_count = len(list(folder_path.iterdir()))
        shutil.rmtree(folder_path)
        with self.stats.lock:
            self.stats.removed_count += removed_count
        self.stats.notify()

    def _rm_track(self, track_path: Path):
        os.remove(track_path)
        with self.stats.lock:
            self.stats.removed_count += 1
        self.stats.notify()

    def _rename_folder(self, existing_path: Path, new_path: Path):
        os.rename(existing_path, new_path)
        with self.stats.lock:
            self.stats.folders_moved_count += 1
        self.stats.notify()

    def _populate_cds(self, cds: list[CD], lib: Library):
        for cd in cds:
            # Find removed or reordered folders
            if cd.path.exists():
                for existing_path in cd.path.iterdir():
                    if not existing_path.is_dir():
                        continue

                    # Existing CD folder found.
                    new_path = cd.find_folder_path(existing_path.name)
                    if new_path == existing_path:
                        # Folder has not been removed or reordered
                        continue

                    if new_path is None:
                        # Folder was not found in CD, must have been removed
                        log(f"Found existing folder `{existing_path.name}` that is no longer in CD `{cd.path.name}`. This folder will be removed.")
                        self.executor.submit(self._rm_folder, existing_path)
                        continue

                    # Folder was found in CD, but at a different position
                    log(f"Existing folder `{existing_path.name}` has been reordered, renaming to `{new_path}`.")
                    self.executor.submit(self._rename_folder, existing_path, new_path)

            # Convert
            for i, folder in enumerate(cd.folders):
                query, _ = parse_query_string(folder.query, Item)
                folder_path = folder.get_path(i, cd.path, len(cd.folders))
                folder_path.mkdir(parents=True, exist_ok=True)
                items = lib.items(query)
                self._clean_folder(items, folder_path)
                self._convert_folder(items, folder_path)
        return None

    def _get_song_length(self, path: Path) -> float:
        try:
            probe = ffmpeg.probe(str(path))
        except ffmpeg.Error:
            return 0.0

        stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        if stream is None:
            return 0.0

        duration = float(stream["duration"])
        return duration

    def _clean_folder(self, items: Iterable[Item], folder_path: Path):
        converted_paths: list[Path] = [folder_path / (item.filepath.stem + ".mp3") for item in items]

        for path in folder_path.iterdir():
            if path.suffix != ".mp3":
                continue
            if not path.is_file():
                continue

            if path not in converted_paths:
                log(f"Found removed file `{path}`. This file will be removed.")
                self.executor.submit(self._rm_track, path)

    def _convert_folder(self, items: Iterable[Item], folder_path: Path):
        for items_chunk in divide(self.max_threads, items):
            self.executor.submit(self._convert_folder_chunk, items_chunk, folder_path)
        return None

    def _convert_folder_chunk(self, items: Iterable[Item], folder_path: Path):
        for item in items:
            converted_path = folder_path / (item.filepath.stem + ".mp3")
            if converted_path.exists():
                if converted_path.is_file():
                    converted_duration = math.ceil(self._get_song_length(converted_path))
                    orig_duration = math.ceil(self._get_song_length(item.filepath))
                    if abs(converted_duration - orig_duration) > 1:
                        log(f"Found partially converted file `{converted_path}`. This file will be reconverted.")
                        os.remove(converted_path)
                    else:
                        log(f"Skipping `{item.filepath.name}` as it is already in {folder_path}")
                        with self.stats.lock:
                            self.stats.skip_count += 1
                        self.stats.notify()
                        continue
                else:
                    log(f"FATAL: {converted_path} already exists, but it isn't a file!")
                    log("Unsure how to proceed, you should probably manually intervene here.")
                    exit(1)

            def job(src_file: Path, dest_file: Path):
                log(f"Converting `{src_file.name}` to {self.bitrate}K MP3 in {dest_file.parent}")
                self._convert_file(src_file, dest_file)

            self.executor.submit(job, item.filepath, converted_path)
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
            if verbose:
                sys.stderr.write(f"Error converting `{file}`! Look in `{dest_file.parent}` for ffmpeg logs.\n")
            stdout_log_path = dest_file.with_suffix(".stdout.log")
            stderr_log_path = dest_file.with_suffix(".stderr.log")
            with stdout_log_path.open("wb") as stdout_log:
                stdout_log.write(result.stdout)
            with stderr_log_path.open("wb") as stderr_log:
                stderr_log.write(result.stderr)
            with self.stats.lock:
                self.stats.failed_convert_count += 1
            self.stats.notify()
        else:
            with self.stats.lock:
                self.stats.convert_count += 1
            self.stats.notify()

        return None

    def _load_cds_from_config(self) -> list[CD]:
        if "cds" not in self.config:
            log(
                "No CDs defined in config! "
                "Either add CDs in your beets config file or create "
                "CD definition files and pass them as arguments."
            )
            return []

        conf_cds: CDDefinition = self.config["cds"].get(dict) # pyright: ignore[reportAssignmentType]
        cds = self._load_cds(conf_cds)
        return cds
    
    def _load_cds_from_path(self, path: Path) -> list[CD]:
        if path.is_dir():
            child_cds: list[CD] = []
            for child in path.iterdir():
                child_cds.extend(self._load_cds_from_path(child))
            return child_cds

        if not path.is_file():
            return []
        if path.suffix != ".yml":
            return []

        try:
            config = RootView([YamlSource(str(path))])
            cds_dict: CDDefinition = config.get(dict) # pyright: ignore[reportAssignmentType]
            cds = self._load_cds(cds_dict)
            return cds
        except:
            log(f"Error while loading from file `{path}` - is this a valid cdman definition file?")
            return []
    
    def _load_cds(self, cd_data: CDDefinition) -> list[CD]:
        cds_path = Path(self.config["cds_path"].get(str)).expanduser() # pyright: ignore[reportArgumentType]
        cds: list[CD] = []

        for cd_name in cd_data:
            cd = CD(cds_path / cd_name)
            cd_folders_data = cd_data[cd_name]
            for cd_folder_data in cd_folders_data:
                cd_folder = CDFolder(cd_folder_data)
                cd.folders.append(cd_folder)
            cds.append(cd) 

        return cds
    
