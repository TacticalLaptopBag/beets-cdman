import sys
from xspf_lib import Playlist
from optparse import Values
from pathlib import Path
from typing import Optional, OrderedDict
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


class CDParser:
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
        cds: list[CD] = []

        if "cds" in self.config:
            cds.extend(self._parse_data(self.config["cds"]))

        if "cd_files" in self.config:
            cd_files: list[str] = self.config["cd_files"].get(list) # type: ignore
            for cd_file in cd_files:
                cds.extend(self.from_path(Path(cd_file)))

        return cds

    def from_path(self, path: Path) -> list[CD]:
        if path.is_dir():
            cds: list[CD] = []
            for child in path.iterdir():
                cds.extend(self.from_path(child))

        if not path.is_file() and not path.is_symlink():
            return []

        if path.suffix != ".yml":
            return []
        
        try:
            view = RootView([YamlSource(str(path))])
            return self._parse_data(view)
        except:
            print(f"Error while loading from file `{path}` - is this a valid cdman definition file?")
            return []

    def _parse_data(self, view: ConfigView) -> list[CD]:
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
                sys.stderr.write(f"Invalid type for CD '{cd_name}'. Must be either 'mp3' or 'audio'.\n")
        return cds

    def _parse_mp3_data(self, view: Subview) -> CD:
        cd_path = self.cds_path / view.key

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
        for folder_name in folders_view:
            folder_view = folders_view[folder_name]
            track_paths: list[Path] = []

            # Parse query or queries
            if "query" in folder_view:
                query: str = folder_view["query"].get(str) # type: ignore
                query_tracks = self._get_tracks_from_query(query)
                track_paths.extend(query_tracks)
            if "queries" in folder_view:
                queries: list[str] = folder_view["queries"].get(list) # type: ignore
                for query in queries:
                    query_tracks = self._get_tracks_from_query(query)
                    track_paths.extend(query_tracks)
            
            # Parse playlist or playlists
            if "playlist" in folder_view:
                playlist_path: str = folder_view["playlist"].get(str) # type: ignore
                playlist_tracks = self._get_tracks_from_playlist(Path(playlist_path))
                track_paths.extend(playlist_tracks)
            if "playlists" in folder_view:
                playlists: list[str] = folder_view["playlists"].get(list) # type: ignore
                for playlist_path in playlists:
                    playlist_tracks = self._get_tracks_from_playlist(Path(playlist_path))
                    track_paths.extend(playlist_tracks)

            # Convert found track paths into MP3Tracks
            mp3_tracks = [MP3Track(track_path, bitrate) for track_path in track_paths]

            # Create folder and add it to the new CD
            folder = MP3Folder(
                cd_path / str(folder_name),
                mp3_tracks,
            )
            cd_folders.append(folder)
        return MP3CD(cd_path, cd_folders, self.executor)

    def _parse_audio_data(self, view: Subview) -> CD:
        cd_path = self.cds_path / view.key

        # Determine population mode
        population_mode = AudioPopulateMode.COPY
        if "audio_population_mode" in self.config:
            pop_mode_str: str = self.config["audio_population_mode"].get(str) # type: ignore
            population_mode = AudioPopulateMode.from_str(pop_mode_str)
        if "population_mode" in view:
            pop_mode_str: str = view["population_mode"].get(str) # type: ignore
            population_mode = AudioPopulateMode.from_str(pop_mode_str)
        if self.opts.population_mode is not None:
            pop_mode_str: str = self.opts.population_mode
            population_mode = AudioPopulateMode.from_str(pop_mode_str)
        if population_mode is None:
            raise ValueError(f"Invalid population_mode for CD {view.key}")

        # Parse tracks
        tracks_data: list[OrderedDict[str, str]] = view["tracks"].get(list) # type: ignore
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

        # Convert found track paths into AudioTracks
        tracks = [AudioTrack(track_path, cd_path, population_mode) for track_path in track_paths]
        return AudioCD(cd_path, tracks, self.executor)

    def _get_tracks_from_query(self, query: str) -> list[Path]:
        parsed_query, _ = parse_query_string(query, Item)
        items = self.lib.items(parsed_query)
        return [item.filepath for item in items]

    def _get_tracks_from_playlist(self, playlist_path: Path) -> list[Path]:
        if not playlist_path.is_file() and not playlist_path.is_symlink():
            raise ValueError(f"Provided playlist path `{playlist_path}` is not a file!")

        if playlist_path.suffix == ".m3u":
            return self._get_tracks_from_m3u_playlist(playlist_path)
        raise ValueError(f"Provided playlist file `{playlist_path}` is unsupported!")

    def _get_tracks_from_m3u_playlist(self, playlist_path: Path) -> list[Path]:
        tracks = parsem3u(str(playlist_path))
        paths: list[Path] = []
        for track in tracks:
            track_path = Path(track.path)
            if track_path.is_absolute():
                resolved_path = track_path.resolve()
            else:
                resolved_path = (playlist_path.parent / track_path).resolve()
            if not resolved_path.exists():
                sys.stderr.write(f"Playlist at `{playlist_path}` references missing track `{resolved_path}`")
                continue
            paths.append(resolved_path)
        return paths
