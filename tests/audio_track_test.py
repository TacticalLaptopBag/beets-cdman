import math
from pathlib import Path
import shutil
import ffmpeg
from pytest import fixture

from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.cd.audio.audio_track import AudioTrack
from beetsplug.stats import Stats

from tests import common_track_test


file_path = Path(__file__)
music_path = common_track_test.music_path
track_path = file_path.parent / "audio_tracks"


@fixture
def tracks() -> list[AudioTrack]:
    return [
        AudioTrack(
            music_path / "01 Jul.m4a",
            track_path,
            AudioPopulateMode.COPY,
        ),
        AudioTrack(
            music_path / "002 Snowfall.mp3",
            track_path,
            AudioPopulateMode.HARD_LINK,
        ),
        AudioTrack(
            music_path / "3 Stars In Her Skies.mp3",
            track_path,
            AudioPopulateMode.SOFT_LINK,
        ),
        AudioTrack(
            music_path / "A Kind Of Hope.ogg",
            track_path,
            AudioPopulateMode.COPY,
        ),
        AudioTrack(
            music_path / "Chasing Daylight.opus",
            track_path,
            AudioPopulateMode.HARD_LINK,
        ),
        AudioTrack(
            music_path / "Horizons.flac",
            track_path,
            AudioPopulateMode.SOFT_LINK,
        ),
    ]


@fixture
def numbered_tracks(tracks):
    return common_track_test.number_tracks(tracks)


@fixture
def populated_tracks(numbered_tracks):
    return common_track_test.populate_tracks(numbered_tracks)


def test_populate(numbered_tracks):
    shutil.rmtree(track_path, ignore_errors=True)
    Stats.reset()

    for i, track in enumerate(numbered_tracks):
        track.populate()
        assert Stats.tracks_populated == i+1
        assert math.ceil(track.get_duration(track.src_path)) == math.ceil(track.get_duration(track.dst_path))

        probe = ffmpeg.probe(str(track.dst_path))
        stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        assert stream is not None

        check_populate_mode(track)

        track.populate()
        assert Stats.tracks_skipped == i+1


def check_populate_mode(track: AudioTrack):
    match track._populate_mode:
        case AudioPopulateMode.SOFT_LINK:
            assert track.dst_path.is_symlink()
        case AudioPopulateMode.HARD_LINK:
            assert track.dst_path.stat().st_nlink > 1
        case AudioPopulateMode.COPY:
            assert track.dst_path.is_file()
        case _:
            assert False


def test_len(populated_tracks):
    for track in populated_tracks:
        assert math.ceil(track.get_duration(track.dst_path)) == len(track)
