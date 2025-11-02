from collections.abc import Sequence
from datetime import datetime
import os
from pathlib import Path
from threading import Lock, Thread
import psutil
from typing import Optional, override
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Library, parse_query_string, Item
from optparse import Values

from beetsplug.cd.cd import CD, CDSplit
from beetsplug.cd_parser import CDParser
from beetsplug.config import Config
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.printer import Printer
from beetsplug.stats import Stats


class CDManPlugin(BeetsPlugin):
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)

        hw_thread_count = psutil.cpu_count() or 4
        self.config.add({
            "cds_path": "~/Music/CDs",
            "bitrate": 192,
            "threads": hw_thread_count,
        })
        self._summary_thread = Thread(
            target=self._summary_thread_function,
            name="Summary",
        )
        return None

    @override
    def commands(self):
        return [self._get_subcommand()]

    def _get_subcommand(self):
        cmd = Subcommand("cdman", help="manage CDs")
        cmd.parser.add_option(
            "--threads", "-t",
            help="The maximum number of threads to use. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--bitrate", "-b",
            help="The bitrate (in kbps) to use when converting files to MP3. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--populate-mode", "-p",
            help="Determines how Audio CDs are populated. "+
                "Must be one of COPY, HARD_LINK, or SOFT_LINK. "+
                "This overrides the config value of the same name.",
            type=str,
        )
        cmd.parser.add_option(
            "--dry", "-d",
            help="When run with this flag present, 'cdman' goes through "
                "all the motions of a normal command, but doesn't "
                "actually perform any conversions. "
                "Note that directories may be created in your cds_path directory.",
            action="store_true",
        )
        cmd.parser.add_option(
            "--verbose", "-v",
            help="Prints detailed output of what 'cdman' is currently doing.",
            action="store_true",
        )
        cmd.parser.add_option(
            "--list-unused", "-l",
            help="Lists tracks in your beets library that are not found in any of your CDs",
            action="store_true",
        )
        cmd.parser.add_option(
            "--list-unused-paths", "-L",
            help="Lists track paths in your beets library that were not found in any of your CDs "+
                "This overrides --list-unused.",
            action="store_true",
        )

        def cdman_cmd(lib: Library, opts: Values, args: list[str]):
            self._cmd(lib, opts, args)
        cmd.func = cdman_cmd
        return cmd

    def _get_duplicates(self, cds: list[CD]) -> set[str]:
        cd_paths = set[Path]()
        duplicates = set[str]()
        for cd in cds:
            if cd.path in cd_paths:
                duplicates.add(cd.path.name)
            cd_paths.add(cd.path)
        return duplicates

    def _cmd(self, lib: Library, opts: Values, args: list[str]):
        max_threads: int = self.config["threads"].get(int) if opts.threads is None else opts.threads  # type: ignore
        self._executor = DimensionalThreadPoolExecutor(max_threads)

        Config.verbose = opts.verbose
        Config.dry = opts.dry

        cd_parser = CDParser(lib, opts, self.config, self._executor)
        if len(args) == 0:
            # Load CDs from config
            cds = cd_parser.from_config()
        else:
            # Load CDs from args
            cds: list[CD] = []
            for arg in args:
                arg_path = Path(arg)
                if not arg_path.exists():
                    print(f"No such file or directory: {arg_path}")
                    continue
                arg_cds = cd_parser.from_path(arg_path)
                cds.extend(arg_cds)

        if len(cds) == 0:
            print("No CD definitions found!")
            self._executor.shutdown()
            return None

        duplicates = self._get_duplicates(cds)
        if len(duplicates) > 0:
            print("Duplicate CD definitions found! Check your beets config and CD definition files for duplicate CD names.")
            print(f"Duplicate CDs: {", ".join(duplicates)}")
            self._executor.shutdown()
            return None

        if opts.list_unused or opts.list_unused_paths:
            self._list_unused(lib, opts, cds)
        else:
            self._populate(cds)
        
        return None

    def _list_unused(self, lib: Library, opts: Values, cds: list[CD]):
        cd_track_paths = set([track.src_path for cd in cds for track in cd.get_tracks()])

        parsed_query, _ = parse_query_string("", Item)
        items = lib.items(parsed_query)
        for item in items:
            if item.filepath in cd_track_paths:
                continue

            if opts.list_unused_paths:
                print(item.filepath)
            else:
                print(f"{item.get("artist")} - {item.get("album")} - {item.get("title")}")
            
        self._executor.shutdown()
        return None

    def _populate(self, cds: list[CD]):
        self._summary_thread.start()

        cd_splits: dict[CD, Sequence[CDSplit]] = {}
        cd_splits_lock = Lock()
        def split_job(cd: CD):
            splits = cd.calculate_splits()
            with cd_splits_lock:
                cd_splits[cd] = splits

        with self._executor:
            for cd in cds:
                cd.numberize()
                cd.cleanup()
                cd.populate()

            # Wait for all populates to finish before calculating splits
            if not Config.dry:
                self._executor.wait()
                Stats.set_calculating()
                for cd in cds:
                    self._executor.submit(split_job, cd)

        Stats.set_done()
        self._summary_thread.join()

        for cd in cd_splits:
            splits = cd_splits[cd]
            if len(splits) > 1:
                print(f"`{cd.path.name}` is too big to fit on one CD! It must be split across multiple CDs like so:")
                for i, split in enumerate(splits):
                    path_start = split.start.dst_path.name
                    path_end = split.end.dst_path.name
                    if cd.pretty_type == "MP3":
                        path_start = f"{split.start.dst_path.parent.name}{os.path.sep}{path_start}"
                        path_end = f"{split.end.dst_path.parent.name}{os.path.sep}{path_end}"
                    print(f"\t({i+1}/{len(splits)}): {path_start} -- {path_end}")
        return None

    def _summary_thread_function(self):
        p = Printer()
        spinner = ["-", "\\", "|", "/"]
        dancing_dots = [".", "..", " ..", "  ..", "   ..", "    .", "    .", "   ..", "  ..", " ..", "..", "."]
        ellipses = ["", ".", ".", "..", "..", "...", "...", "...", "..."]

        current_indicator = 0
        indicator_time = 0.1 if not Config.verbose else None
        last_check = datetime.now().timestamp()
        while True:
            with Stats.changed_cond:
                Stats.changed_cond.wait(indicator_time)

            if Stats.is_calculating:
                indicator = ellipses
            elif Stats.tracks_populating > 0:
                indicator = spinner
            else:
                indicator = dancing_dots

            if indicator_time is not None:
                if datetime.now().timestamp() - last_check >= indicator_time:
                    current_indicator += 1
                    last_check = datetime.now().timestamp()
            current_indicator = current_indicator % len(indicator)

            with Stats.lock:
                if Config.verbose and not Stats.is_done:
                    continue

                p.print_line(1, f"Found CDs: {Stats.cds}")

                p.print_line(3, f"Tracks populated: {Stats.tracks_populated}")
                p.print_line(4, f"Tracks skipped: {Stats.tracks_skipped}")
                p.print_line(5, f"Tracks deleted: {Stats.tracks_deleted}")
                p.print_line(6, f"Tracks moved: {Stats.tracks_moved}")
                p.print_line(7, f"Tracks failed: {Stats.tracks_failed}")
                p.print_line(8, f"Folders deleted: {Stats.folders_deleted}")
                p.print_line(9, f"Folders moved: {Stats.folders_moved}")

                if not Config.verbose:
                    if Stats.is_calculating:
                        msg = f"Checking CD sizes{indicator[current_indicator]}"
                    else:
                        if Stats.tracks_populating > 0:
                            msg = f"Tracks populating: {Stats.tracks_populating} {indicator[current_indicator] * Stats.tracks_populating}"
                        else:
                            msg = f"Searching for tracks{indicator[current_indicator]}"
                    p.print_line(11, msg)

                if Stats.is_done:
                    break
        return None
