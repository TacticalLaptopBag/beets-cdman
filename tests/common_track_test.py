from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
from pytest import fixture, raises

from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.cd.audio.audio_track import AudioTrack
from beetsplug.cd.mp3.mp3_track import MP3Track
from beetsplug.cd.track import CDTrack

from tests import common


file_path = Path(__file__)
music_path = common.music_path
track_path = file_path.parent / "common_tracks"


@fixture
def tracks() -> list[CDTrack]:
    return [
        MP3Track(
            music_path / "01 Jul.m4a",
            128,
            track_path,
        ),
        AudioTrack(
            music_path / "002 Snowfall.mp3",
            track_path,
            AudioPopulateMode.COPY,
        ),
        MP3Track(
            music_path / "3 Stars In Her Skies.mp3",
            256,
            track_path,
        ),
        AudioTrack(
            music_path / "A Kind Of Hope.ogg",
            track_path,
            AudioPopulateMode.SOFT_LINK,
        ),
        MP3Track(
            music_path / "Chasing Daylight.opus",
            192,
            track_path,
        ),
        AudioTrack(
            music_path / "Horizons.flac",
            track_path,
            AudioPopulateMode.HARD_LINK,
        ),
    ]


def number_tracks(tracks: Sequence[CDTrack]):
    track_count = len(tracks)
    for i, track in enumerate(tracks):
        track.set_dst_path(i+1, track_count)
    return tracks


def populate_tracks(tracks: Sequence[CDTrack]) -> Sequence[CDTrack]:
    executor = ThreadPoolExecutor(len(tracks))
    for track in tracks:
        executor.submit(track.populate)
    executor.shutdown()
    return tracks


@fixture
def numbered_tracks(tracks) -> Sequence[CDTrack]:
    return number_tracks(tracks)


@fixture
def populated_tracks(numbered_tracks) -> Sequence[CDTrack]:
    return populate_tracks(numbered_tracks)


def test_unnumbered_name(tracks):
    assert tracks[0].name == "Jul"
    assert tracks[1].name == "Snowfall"
    assert tracks[2].name == "Stars In Her Skies"
    assert tracks[3].name == "A Kind Of Hope"
    assert tracks[4].name == "Chasing Daylight"
    assert tracks[5].name == "Horizons"


def test_set_dst_path(tracks):
    tracks_count = len(tracks)
    for i, track in enumerate(tracks):
        track.set_dst_path(i+1, tracks_count)
        assert track._dst_path is not None
        assert track.dst_path.name == f"0{i+1} {track.name}{track._get_dst_extension()}"


def test_is_similar(populated_tracks):
    for track in populated_tracks:
        other_tracks = list(filter(lambda t: t.src_path != track.src_path, populated_tracks))
        for other_track in other_tracks:
            assert not track.is_similar(other_track.dst_path)
        assert track.is_similar(track.dst_path)


def test_get_size(populated_tracks):
    assert populated_tracks[0].get_size() == 3323918
    assert populated_tracks[1].get_size() == 9991773
    assert populated_tracks[2].get_size() == 8874178
    assert populated_tracks[3].get_size() == 6063570
    assert populated_tracks[4].get_size() == 6574123
    assert populated_tracks[5].get_size() == 25453398


def test_get_duration(tracks):
    assert math.ceil(tracks[0].get_duration(tracks[0].src_path)) == 208
    assert math.ceil(tracks[1].get_duration(tracks[1].src_path)) == 249
    assert math.ceil(tracks[2].get_duration(tracks[2].src_path)) == 278
    assert math.ceil(tracks[3].get_duration(tracks[3].src_path)) == 343
    assert math.ceil(tracks[4].get_duration(tracks[4].src_path)) == 274
    assert math.ceil(tracks[5].get_duration(tracks[5].src_path)) == 294


def test_numbered_guards(tracks):
    track = tracks[0]
    with raises(RuntimeError):
        track.dst_path
    with raises(RuntimeError):
        track.get_size()
    with raises(RuntimeError):
        track.populate()