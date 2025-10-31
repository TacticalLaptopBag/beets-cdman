import math
from pathlib import Path
import shutil
import ffmpeg
from pytest import fixture

from beetsplug.cd.mp3.mp3_track import MP3Track
from beetsplug.stats import Stats
from . import common_track_test


file_path = Path(__file__)
music_path = common_track_test.music_path
track_path = file_path.parent / "mp3_tracks"


@fixture
def tracks() -> list[MP3Track]:
    return [
        MP3Track(
            music_path / "01 Jul.m4a",
            track_path,
            128,
        ),
        MP3Track(
            music_path / "002 Snowfall.mp3",
            track_path,
            192,
        ),
        MP3Track(
            music_path / "3 Stars In Her Skies.mp3",
            track_path,
            256,
        ),
        MP3Track(
            music_path / "A Kind Of Hope.ogg",
            track_path,
            128,
        ),
        MP3Track(
            music_path / "Chasing Daylight.opus",
            track_path,
            192,
        ),
        MP3Track(
            music_path / "Horizons.flac",
            track_path,
            256,
        ),
    ]


@fixture
def numbered_tracks(tracks):
    return common_track_test.number_tracks(tracks)


@fixture
def populated_tracks(numbered_tracks):
    return common_track_test.populate_tracks(numbered_tracks)


def test_populate(numbered_tracks, capsys):
    shutil.rmtree(track_path, ignore_errors=True)

    for i, track in enumerate(numbered_tracks):
        track.populate()
        err_log = capsys.readouterr().err
        assert "Error converting" not in err_log
        assert Stats.tracks_populated == i+1
        assert math.ceil(track.get_duration(track.src_path)) == math.ceil(track.get_duration(track.dst_path))

        probe = ffmpeg.probe(str(track.dst_path))
        stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        assert stream is not None
        assert stream["sample_rate"] == "44100"
        assert int(stream["bit_rate"]) == track._bitrate * 1_000

        track.populate()
        assert Stats.tracks_skipped == i+1
    Stats.reset()


def test_len(populated_tracks):
    for track in populated_tracks:
        assert track.get_size() == len(track)
