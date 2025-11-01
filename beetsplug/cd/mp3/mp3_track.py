from pathlib import Path
import subprocess
import sys
from typing import override

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.cd.track import CDTrack


class MP3Track(CDTrack):
    def __init__(self, src_path: Path, bitrate: int, dst_directory: Path = Path()):
        # dst_directory will be overwritten by CDFolder,
        # but we should still expose dst_directory for tests.
        super().__init__(src_path, dst_directory)
        self._bitrate = bitrate

    @override
    def _get_dst_extension(self) -> str:
        return ".mp3"

    @override
    def populate(self):
        if self._dst_path is None:
            raise RuntimeError("set_dst_path must be run before populate!")

        if self.is_similar(self.dst_path):
            stream = self._dst_stream
            if stream is not None and "bit_rate" in stream:
                dst_bitrate = int(stream["bit_rate"])
                if dst_bitrate == self._bitrate * 1_000:
                    # Track already exists and has matching bitrate, skip
                    if Config.verbose:
                        print(f"Skipped {self._dst_path}")
                    Stats.skip_track()
                    return
        self._dst_path.parent.mkdir(parents=True, exist_ok=True)

        Stats.populating_track()
        # ffmpeg -i "$flac_file" -hide_banner -loglevel error -acodec libmp3lame -ar 44100 -b:a 128k -vn "$output_file"
        if Config.verbose:
            print(f"Converting {self._src_path} to {self._dst_path} ...")
        if Config.dry:
            Stats.populate_track()
            return None
        
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", str(self._src_path),
                "-hide_banner",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-b:a", f"{self._bitrate}k",
                "-vn", str(self._dst_path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            if Config.verbose:
                sys.stderr.write(f"Error converting `{self._src_path}`! Look in `{self.dst_directory}` for ffmpeg logs.\n")

            stdout_log_path = self._dst_path.with_suffix(".stdout.log")
            stderr_log_path = self._dst_path.with_suffix(".stderr.log")
            with stdout_log_path.open("wb") as stdout_log:
                stdout_log.write(result.stdout)
            with stderr_log_path.open("wb") as stderr_log:
                stderr_log.write(result.stderr)
            Stats.fail_track()
        else:
            Stats.populate_track()

        return None

    @override
    def __len__(self):
        return self.get_size()
