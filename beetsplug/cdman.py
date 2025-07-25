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


class CDManPlugin(BeetsPlugin):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self.bitrate = self.config["bitrate"].get()
        self.config.add({
            "bitrate": 128,
            "cds": [],
            "threads": 8,
        })

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
        
        # TODO: Need to go through main CD folder and see if any existing folders aren't in the list anymore
        # Possibly rename folders?
        with ThreadPoolExecutor(max_workers=self.config["threads"].get()) as executor:
            for cd in cds:
                for i, folder in enumerate(cd.folders):
                    query, _ = parse_query_string(folder.query, Item)
                    items = lib.items(query)
                    folder_path = folder.get_path(i, cd.path, len(cd.folders))
                    folder_path.mkdir(parents=True, exist_ok=True)
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
        # ffmpeg -i "$flac_file" -hide_banner -loglevel error -acodec libmp3lame -ar 44100 -b:a 128k -vn "$output_file"
        subprocess.run(
            [
                "ffmpeg",
                "-i", str(file),
                "-hide_banner",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-b:a", f"{self.bitrate}k",
                "-vn", str(dest_file)
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return None

    def _load_cds(self) -> list[CD]:
        cds_path = Path(self.config["cds_path"].get())
        conf_cds = self.config["cds"].get()
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
