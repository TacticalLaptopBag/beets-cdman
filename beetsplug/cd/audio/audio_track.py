import math
import os
from pathlib import Path
import shutil
from typing import override

from beetsplug.stats import Stats
from beetsplug.config import Config
from beetsplug.cd.track import CDTrack
from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.util import ffmpeg


class AudioTrack(CDTrack):
    def __init__(
        self,
        src_path: Path,
        dst_directory: Path,
        populate_mode: AudioPopulateMode,
    ):
        super().__init__(src_path, dst_directory)
        self._populate_mode = populate_mode

    @override
    def _get_dst_extension(self) -> str:
        return self.src_path.suffix

    @override
    def populate(self):
        if self._dst_path is None:
            raise RuntimeError("set_dst_path must be run before populate!")

        # First check if track already exists
        if self.is_similar(self._dst_path):
            # Track already exists, is it the correct mode?
            is_hard_link = self._dst_path.stat().st_nlink > 1
            skip = (self._populate_mode == AudioPopulateMode.SOFT_LINK and self._dst_path.is_symlink())
            skip = skip or (self._populate_mode == AudioPopulateMode.HARD_LINK and is_hard_link)
            skip = skip or (self._populate_mode == AudioPopulateMode.COPY and self._dst_path.is_file() and not is_hard_link and self._dst_path.stat().st_size == self._src_path.stat().st_size)
            skip = skip or (self._populate_mode == AudioPopulateMode.CONVERT and self._dst_path.is_file() and not is_hard_link and self._dst_path.stat().st_size != self._src_path.stat().st_size)
            if skip:
                # Track is in the same mode, we can safely skip this
                Stats.skip_track()
                if Config.verbose:
                    print(f"Skipped {self._dst_path}")
                return

            # Track is not in the same mode, delete it so we can rewrite in the correct mode
            if not Config.dry:
                os.remove(self._dst_path)
            if Config.verbose:
                print(f"Removed {self._dst_path} -- populate mode has changed.")
            Stats.delete_track()

        # Ensure CD directory is created
        self.dst_directory.mkdir(parents=True, exist_ok=True)

        # Populate the track
        verbose_format = f"{{}} {self._src_path} to {self._dst_path}"
        Stats.populating_track()
        try:
            match self._populate_mode:
                case AudioPopulateMode.SOFT_LINK:
                    if Config.verbose:
                        print(verbose_format.format("Soft link"))
                    if not Config.dry:
                        os.symlink(self._src_path, self._dst_path)
                case AudioPopulateMode.HARD_LINK:
                    if Config.verbose:
                        print(verbose_format.format("Hard link"))
                    if not Config.dry:
                        os.link(self._src_path, self._dst_path)
                case AudioPopulateMode.COPY:
                    if Config.verbose:
                        print(verbose_format.format("Copy"))
                    if not Config.dry:
                        shutil.copy2(self._src_path, self._dst_path)
                case AudioPopulateMode.CONVERT:
                    if Config.verbose:
                        print(verbose_format.format("Converting"))
                    if not Config.dry:
                        result = ffmpeg(
                            self._src_path,
                            self._dst_path.with_suffix(".flac"),
                            ["-vn"]
                        )
                        result.check_returncode()
                case _:
                    Stats.fail_track()
                    raise ValueError("Invalid populate_mode")
            Stats.populate_track()
        except:
            Stats.fail_track()

    @override
    def __len__(self):
        # Audio CDs are measured in duration, so track size is also measured in duration
        return math.ceil(self.get_duration(self.dst_path))

