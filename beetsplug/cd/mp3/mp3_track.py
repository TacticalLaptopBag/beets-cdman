from pathlib import Path
import subprocess
import sys
from typing import override

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.cd.track import CDTrack
from beetsplug.util import ffmpeg


class MP3Track(CDTrack):
    def __init__(self, src_path: Path, bitrate: int, dst_directory: Path = Path()):
        # dst_directory will be overwritten by MP3Folder,
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

        # First check if track already exists
        if self.is_similar(self.dst_path):
            # Track already exists, is it the same bitrate?
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

        # Populate the track
        Stats.populating_track()
        if Config.verbose:
            print(f"Converting {self._src_path} to {self._dst_path} ...")
        if Config.dry:
            Stats.populate_track()
            return None
        
        # Convert to MP3 using ffmpeg
        # ffmpeg -i "$source_file" -hide_banner -loglevel error -acodec libmp3lame -ar 44100 -b:a ${bitrate}k -vn "$output_file"
        result = ffmpeg(self._src_path, self._dst_path, [
            "-acodec", "libmp3lame",
            "-ar", "44100",
            "-b:a", f"{self._bitrate}k",
            "-vn",
        ])

        # Check that the conversion actually went through
        if result.returncode != 0:
            Stats.fail_track()
        else:
            Stats.populate_track()

        return None

    @override
    def __len__(self):
        return self.get_size()
