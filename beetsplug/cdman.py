import math
import sys
import shutil
import os
import psutil
import subprocess
from typing import Iterable
from beets.plugins import BeetsPlugin
from beets.library import Library, parse_query_string, Item
from beets.ui import Subcommand
from optparse import Values
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from confuse import RootView, YamlSource

from .cd_folder import CDFolder
from .cd_type import CDType
from .util import get_song_length

from .cd import CD, MAX_SIZE_AUDIO, MAX_SIZE_MP3, CDDefinition


"""
cdman:
    cds_path: ~/Music/CDs
    bitrate: 128
    cds:
        arcadian:
            type: mp3
            folders:
                - name: The Arcadian Wild
                  query: "'album:The Arcadian Wild'"
                - name: Welcome
                  query: "'album:Welcome (Reframed)'"
        discovery:
            type: audio
            track_queries:
                - "'artist:Daft Punk' 'album:Discovery'"
                - "'artist:Fantom' 'album:Discovery'"
"""


class CDManPlugin(BeetsPlugin):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        hw_thread_count = psutil.cpu_count() or 4
        self.config.add({
            "cds_path": "~/Music/CDs",
            "bitrate": 128,
            "threads": hw_thread_count,
        })

        self.cds_path = Path(self.config["cds_path"].get(str)).expanduser() # pyright: ignore[reportArgumentType]
        self.bitrate = self.config["bitrate"].get()
        self.max_threads: int = self.config["threads"].get(int) # pyright: ignore[reportAttributeAccessIssue]

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
        def cdman_cmd(lib: Library, opts: Values, args: list[str]):
            self._cmd(lib, opts, args)
        cmd.func = cdman_cmd
        return cmd

    def _cmd(self, lib: Library, opts: Values, args: list[str]):
        cds: list[CD]
        if len(args) == 0:
            cds = self._load_cds_from_config()
        else:
            cds = []
            for arg in args:
                arg_path = Path(arg)
                if not arg_path.exists():
                    print(f"No such file or directory: {arg_path}")
                    continue
                cds.extend(self._load_cds_from_path(Path(arg)))
        
        if opts.threads is not None:
            print(f"Overriding config value 'threads': using {opts.threads} instead of {self.max_threads}")
            self.max_threads = opts.threads

        if opts.bitrate is not None:
            print(f"Overriding config value 'bitrate': using {opts.bitrate} instead of {self.bitrate}")
            self.bitrate = opts.bitrate

        self.dry = opts.dry

        if opts.list_unused:
            self._list_unused(cds, lib)
        else:
            self._populate_cds(cds, lib)
            self._report_size(cds)

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
            print("No track has been left untouched.")
            return None

        print("Tracks not in any defined CD:")
        for unused_track in unused_tracks:
            print(unused_track)
        return None

    def _populate_cds(self, cds: list[CD], lib: Library):
        with ThreadPoolExecutor(self.max_threads) as executor:
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
                            print(f"Found existing folder `{existing_path.name}` that is no longer in CD `{cd.path.name}`. This folder will be removed.")
                            executor.submit(shutil.rmtree, existing_path)
                            continue

                        # Folder was found in CD, but at a different position
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
        converted_paths: list[Path] = [folder_path / (item.filepath.stem + ".mp3") for item in items]

        for path in folder_path.iterdir():
            if path.suffix != ".mp3":
                continue
            if not path.is_file():
                continue

            if path not in converted_paths:
                print(f"Found removed file `{path}`. This file will be removed.")
                executor.submit(os.remove, path)

    def _convert_folder(self, items: Iterable[Item], folder_path: Path, executor: ThreadPoolExecutor):
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

    def _load_cds_from_config(self) -> list[CD]:
        if "cds" not in self.config:
            print(
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
            print(f"Error while loading from file `{path}` - is this a valid cdman definition file?")
            return []
    
    def _load_cds(self, cd_data: CDDefinition) -> list[CD]:
        cds: list[CD] = []

        for cd_name in cd_data:
            cd = CD(self.cds_path / cd_name, CDType.MP3)
            cd_folders_data = cd_data[cd_name]
            for cd_folder_data in cd_folders_data:
                cd_folder = CDFolder(cd_folder_data)
                cd.folders.append(cd_folder)
            cds.append(cd) 

        return cds

    def _report_size(self, cds: list[CD]):
        for cd in cds:
            cd_size = cd.get_size()
            size_warning: str
            cd_max_size: int
            if cd.type == CDType.MP3:
                cd_max_size = MAX_SIZE_MP3
                size_warning = (
                    f"MP3 CD {cd.path.name} is {cd_size / 1_000_000:.1f} MB, "
                    f"which is larger than {cd_max_size / 1_000_000} MB!"
                )
            else:
                cd_max_size = MAX_SIZE_AUDIO
                size_warning = (
                    f"Audio CD {cd.path.name} is {cd_size / 60:.1f} minutes long, "
                    f"which is longer than {cd_max_size / 60} minutes!"
                )

            if cd_size > cd_max_size:
                print()
                cd_splits = cd.get_splits()
                print(
                    f"WARNING: {size_warning} "
                    f"However, you could split the CD into {len(cd_splits)} CDs, "
                    "if you divide the CD into chunks starting with these files:"
                )
                for split in cd_splits:
                    print(split)
