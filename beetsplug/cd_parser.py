from optparse import Values
from pathlib import Path
from typing import OrderedDict
from confuse import ConfigView, RootView, YamlSource, Subview
from beets.library import Library, parse_query_string, Item

from beetsplug.cd.audio.audio_cd import AudioCD
from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.cd.audio.audio_track import AudioTrack
from beetsplug.cd.cd import CD
from beetsplug.cd.mp3.mp3_cd import MP3CD
from beetsplug.cd.mp3.mp3_folder import MP3Folder
from beetsplug.cd.mp3.mp3_track import MP3Track
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.m3uparser import parsem3u
from beetsplug.stats import Stats


class CDParser:
    """
    Handles parsing CD definitions into CD objects
    """

    def __init__(
        self,
        lib: Library,
        opts: Values,
        config: ConfigView,
        executor: DimensionalThreadPoolExecutor,
    ):
        self.lib = lib
        self.opts = opts
        self.config = config
        self.cds_path = Path(config["path"].get(str)).expanduser() # type: ignore
        self.executor = executor
    
    def from_config(self) -> list[CD]:
        """
        Loads CD definitions from the config
        """

        cds: list[CD] = []

        # Get CDs directly defined in the config file
        if "cds" in self.config:
            cds.extend(self._parse_data(self.config["cds"]))

        # Get CDs defined in external files referenced in the config
        if "cd_files" in self.config:
            cd_files: list[str] = self.config["cd_files"].get(list) # type: ignore
            for cd_file in cd_files:
                cds.extend(self.from_path(Path(cd_file)))

        return cds

    def from_path(self, path: Path) -> list[CD]:
        """
        Loads CD definitions from a CD definition file, or directory containing CD definition files
        """

        path = path.expanduser()

        # If the path is a directory, check its contents for CD definitions
        if path.is_dir():
            cds: list[CD] = []
            for child in path.iterdir():
                cds.extend(self.from_path(child))
            return cds

        # The path has already been confirmed to not be a directory,
        # if it isn't a file or symlink, we shouldn't bother with it
        if not path.is_file() and not path.is_symlink():
            return []

        # If the file isn't a YAML file, we shouldn't bother with it
        if path.suffix != ".yml" and path.suffix != ".yaml":
            return []
        
        try:
            # Parse CD data found in the definition file
            view = RootView([YamlSource(str(path))])
            return self._parse_data(view)
        except BaseException as e:
            print(f"Error while loading from file `{path}` - is this a valid cdman definition file?")
            print(e)
            print()
            return []

    def _parse_data(self, view: ConfigView) -> list[CD]:
        """
        Loads a top-level CD definition view
        """
        
        cds: list[CD] = []
        cd_names: list[str] = view.keys()
        for cd_name in cd_names:
            cd_view = view[cd_name]
            cd_type: str = cd_view["type"].get(str) # type: ignore
            if cd_type.lower() == "mp3":
                cds.append(self._parse_mp3_data(cd_view))
            elif cd_type.lower() == "audio":
                cds.append(self._parse_audio_data(cd_view))
            else:
                raise ValueError(f"Invalid type for CD '{cd_name}'. Must be either 'mp3' or 'audio'.\n")
        return cds

    def _get_cd_path(self, view: Subview) -> Path:
        name: str = view["name"].get(str) if "name" in view else view.key # type: ignore
        return Path(view["path"].get(str)) / name if "path" in view else self.cds_path / name # type: ignore

    def _parse_mp3_data(self, view: Subview) -> CD:
        """
        Loads an MP3 CD from a CD definition view
        """
        cd_path: Path = self._get_cd_path(view)

        # Determine bitrate
        bitrate: int = 0
        if "bitrate" in self.config:
            bitrate = self.config["bitrate"].get(int) # type: ignore
        if "bitrate" in view:
            bitrate = view["bitrate"].get(int) # type: ignore
        if self.opts.bitrate is not None:
            bitrate = self.opts.bitrate

        # Parse folders
        cd_folders: list[MP3Folder] = []
        folders_view = view["folders"]
        for folder_key in folders_view:
            folder_view = folders_view[folder_key]
            track_paths: list[Path] = []

            # Get folder name
            folder_name: str = folder_key # type: ignore
            if folder_key != "__root__" and "name" in folder_view:
                folder_name = folder_view["name"].get(str) # type: ignore

            tracks_data: list[OrderedDict[str, str]] = folder_view["tracks"].get(list) # type: ignore
            track_paths = self._parse_tracks(tracks_data)

            # Convert found track paths into MP3Tracks
            mp3_tracks = [MP3Track(track_path, bitrate) for track_path in track_paths]

            # Create folder and add it to the new CD
            folder = MP3Folder(
                cd_path / str(folder_name),
                mp3_tracks,
            )
            cd_folders.append(folder)

        cd = MP3CD(cd_path, cd_folders, self.executor)
        Stats.found_cd(cd.path.name, cd.pretty_type)
        return cd

    def _parse_audio_data(self, view: Subview) -> CD:
        """
        Loads an Audio CD from a CD definition view
        """
        cd_path = self._get_cd_path(view)

        # Determine the populate mode for this CD
        populate_mode = AudioPopulateMode.COPY
        if "audio_populate_mode" in self.config:
            pop_mode_str: str = self.config["audio_populate_mode"].get(str) # type: ignore
            populate_mode = AudioPopulateMode.from_str(pop_mode_str)
        if "populate_mode" in view:
            pop_mode_str: str = view["populate_mode"].get(str) # type: ignore
            populate_mode = AudioPopulateMode.from_str(pop_mode_str)
        if self.opts.populate_mode is not None:
            pop_mode_str: str = self.opts.populate_mode
            populate_mode = AudioPopulateMode.from_str(pop_mode_str)
        if populate_mode is None:
            raise ValueError(f"Invalid populate_mode for CD {view.key}")

        # Parse tracks
        tracks_data: list[OrderedDict[str, str]] = view["tracks"].get(list) # type: ignore
        track_paths = self._parse_tracks(tracks_data)

        # Convert found track paths into AudioTracks
        tracks = [AudioTrack(track_path, cd_path, populate_mode) for track_path in track_paths]
        cd = AudioCD(cd_path, tracks, self.executor)
        Stats.found_cd(cd.path.name, cd.pretty_type)
        return cd
    
    def _parse_tracks(self, tracks_data: list[OrderedDict[str, str]]) -> list[Path]:
        """
        Gets track paths from a tracks view
        """
        track_paths: list[Path] = []
        for track_entry in tracks_data:
            if "query" in track_entry:
                query = track_entry["query"]
                query_tracks = self._get_tracks_from_query(query)
                track_paths.extend(query_tracks)
            if "playlist" in track_entry:
                playlist_path = Path(track_entry["playlist"])
                playlist_tracks = self._get_tracks_from_playlist(playlist_path)
                track_paths.extend(playlist_tracks)
        return track_paths

    def _get_tracks_from_query(self, query: str) -> list[Path]:
        """
        Finds track paths from a beets query
        """
        parsed_query, _ = parse_query_string(query, Item)
        items = self.lib.items(parsed_query)
        return [item.filepath for item in items]

    def _get_tracks_from_playlist(self, playlist_path: Path) -> list[Path]:
        """
        Finds track paths from a playlist file
        """
        playlist_path = playlist_path.expanduser()
        if not playlist_path.is_file() and not playlist_path.is_symlink():
            raise ValueError(f"Provided playlist path `{playlist_path}` is not a file!")

        if playlist_path.suffix == ".m3u":
            return self._get_tracks_from_m3u_playlist(playlist_path)
        raise ValueError(f"Provided playlist file `{playlist_path}` is unsupported!")

    def _get_tracks_from_m3u_playlist(self, playlist_path: Path) -> list[Path]:
        """
        Finds track paths from an M3U playlist
        """
        tracks = parsem3u(str(playlist_path))
        paths: list[Path] = []
        for track in tracks:
            track_path = Path(track.path)
            if track_path.is_absolute():
                resolved_path = track_path.resolve()
            else:
                resolved_path = (playlist_path.parent / track_path).resolve()
            if not resolved_path.exists():
                raise ValueError(f"Playlist at `{playlist_path}` references missing track `{resolved_path}`")
            paths.append(resolved_path)
        return paths
