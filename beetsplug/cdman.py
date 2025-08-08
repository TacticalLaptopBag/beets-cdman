import psutil
from beets.plugins import BeetsPlugin
from beets.library import Library
from beets.ui import Subcommand
from optparse import Values
from pathlib import Path
from confuse import RootView, YamlSource

from .dimensional_thread_pool_executor import DimensionalThreadPoolExecutor

from .cd.cd_folder import CDFolder
from .util import item_to_track_listing

from .cd.cd import CD
from .cd.mp3_cd import MP3CD, MP3CDDefinition


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
        self.bitrate: int = self.config["bitrate"].get(int) # pyright: ignore[reportAttributeAccessIssue]
        self.max_threads: int = self.config["threads"].get(int) # pyright: ignore[reportAttributeAccessIssue]
        if self.max_threads <= 0:
            raise ValueError("Config field 'threads' must be a positive integer!")

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
        if opts.threads is not None:
            print(f"Overriding config value 'threads': using {opts.threads} instead of {self.max_threads}")
            self.max_threads = opts.threads

        if opts.bitrate is not None:
            print(f"Overriding config value 'bitrate': using {opts.bitrate} instead of {self.bitrate}")
            self.bitrate = opts.bitrate

        self.dry = opts.dry

        self.executor = DimensionalThreadPoolExecutor(self.max_threads)
        
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

        if opts.list_unused:
            self._list_unused(cds, lib)
            self.executor.shutdown()
        else:
            self._populate_cds(cds, lib)
            self.executor.shutdown()
            self._report_size(cds)

        return None

    def _list_unused(self, cds: list[CD], lib: Library):
        unused_tracks = set([item_to_track_listing(item) for item in lib.items()])
        for cd in cds:
            cd_used_tracks = cd.get_used_tracks(lib)
            unused_tracks = unused_tracks.difference(cd_used_tracks)
            
        if len(unused_tracks) == 0:
            print("No track has been left untouched.")
            return None

        print("Tracks not in any defined CD:")
        for unused_track in unused_tracks:
            print(unused_track)
        return None

    def _populate_cds(self, cds: list[CD], lib: Library):
        for cd in cds:
            # Find removed or reordered folders
            if cd.path.exists():
                cd.cleanup(self.executor)

            # Convert
            cd.convert(lib, self.executor)
        return None

    def _load_cds_from_config(self) -> list[CD]:
        if "cds" not in self.config:
            print(
                "No CDs defined in config! "
                "Either add CDs in your beets config file or create "
                "CD definition files and pass them as arguments."
            )
            return []

        conf_cds: MP3CDDefinition = self.config["cds"].get(dict) # pyright: ignore[reportAssignmentType]
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
            cds_dict: MP3CDDefinition = config.get(dict) # pyright: ignore[reportAssignmentType]
            cds = self._load_cds(cds_dict)
            return cds
        except:
            print(f"Error while loading from file `{path}` - is this a valid cdman definition file?")
            return []
    
    def _load_cds(self, cd_data: MP3CDDefinition) -> list[CD]:
        cds: list[CD] = []

        for cd_name in cd_data:
            cd = MP3CD(self.cds_path / cd_name, self.bitrate, self.dry)
            cd_folders_data = cd_data[cd_name]
            for cd_folder_data in cd_folders_data:
                cd_folder = CDFolder(cd_folder_data)
                cd.folders.append(cd_folder)
            cds.append(cd) 

        return cds

    def _report_size(self, cds: list[CD]):
        for cd in cds:
            if not cd.is_exceeding_size():
                continue
            print()
            cd_splits = cd.get_splits()
            print(
                f"WARNING: {cd.size_warning} "
                "This will not fit on a traditional CD. "
                f"However, you could split the CD into {len(cd_splits)} CDs, "
                "if you divide the CD into chunks starting with these files:"
            )
            for split in cd_splits:
                print(split)
