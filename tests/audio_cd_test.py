from pathlib import Path
from pytest import fixture

from beetsplug.cd.audio.audio_cd import AudioCD
from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.cd.audio.audio_track import AudioTrack
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor

from . import common


music_path = common.music_path
cd_path = Path(__file__).parent / "audio_cds"


@fixture
def executor():
    return DimensionalThreadPoolExecutor(6)


@fixture
def cds(executor) -> list[AudioCD]:
    return [
        AudioCD(
            cd_path / "cd_1",
            [
                AudioTrack(
                    music_path / "01 Jul.m4a", # 207.641338
                    cd_path / "cd_1",
                    AudioPopulateMode.HARD_LINK,
                ),
                AudioTrack(
                    music_path / "3 Stars In Her Skies.mp3", # 277.263673
                    cd_path / "cd_1",
                    AudioPopulateMode.SOFT_LINK,
                ),
                AudioTrack(
                    music_path / "Chasing Daylight.opus", # 273.864458
                    cd_path / "cd_1",
                    AudioPopulateMode.COPY,
                ),
            ],
            executor,
        ),
        AudioCD(
            cd_path / "cd_2",
            [
                AudioTrack(
                    music_path / "002 Snowfall.mp3", # 248.450612
                    cd_path / "cd_2",
                    AudioPopulateMode.HARD_LINK,
                ),
                AudioTrack(
                    music_path / "A Kind Of Hope.ogg", # 342.600544
                    cd_path / "cd_2",
                    AudioPopulateMode.SOFT_LINK,
                ),
            ],
            executor,
        ),
    ]


def test_max_size(cds):
    assert cds[0].max_size == 4800
    assert cds[1].max_size == 4800
    cds[0]._executor.shutdown()


def test_numberize(cds):
    for cd in cds:
        cd.numberize()
        for track in cd._tracks:
            assert track.dst_path is not None
    cds[0]._executor.shutdown()


def test_populate(cds):
    for cd in cds:
        cd.numberize()
        cd.populate()
    cds[0]._executor.shutdown()

    for cd in cds:
        for i, track in enumerate(cd._tracks):
            assert (cd.path / f"0{i+1} {track.name}{track.src_path.suffix}").exists()


def test_get_tracks(cds):
    for cd in cds:
        tracks = cd.get_tracks()
        for i, track in enumerate(tracks):
            assert cd._tracks[i] == track
    cds[0]._executor.shutdown()


def test_cleanup(cds):
    # TODO: Write this
    cds[0]._executor.shutdown()
    assert False


def test_calculate_splits(cds):
    cds[0].numberize()
    cds[0].populate()
    cds[1].numberize()
    cds[1].populate()
    cds[0]._executor.shutdown()

    cd = cds[0]

    cd._test_size = 208 + 278
    splits = cd.calculate_splits()
    assert len(splits) == 2
    assert splits[0].start == cd._tracks[0]
    assert splits[0].end == cd._tracks[1]
    assert splits[1].start == cd._tracks[2]
    assert splits[1].end == cd._tracks[2]

    cd._test_size = -1
    splits = cd.calculate_splits()
    assert len(splits) == 1
    assert splits[0].start == cd._tracks[0]
    assert splits[0].end == cd._tracks[2]

    cd._test_size = 208
    splits = cd.calculate_splits()
    assert len(splits) == 3
    assert splits[0].start == cd._tracks[0]
    assert splits[0].end == cd._tracks[0]
    assert splits[1].start == cd._tracks[1]
    assert splits[1].end == cd._tracks[1]
    assert splits[2].start == cd._tracks[2]
    assert splits[2].end == cd._tracks[2]

    cd = cds[1]

    cd._test_size = 249 + 343
    splits = cd.calculate_splits()
    assert len(splits) == 1

    cd._test_size = 249
    splits = cd.calculate_splits()
    assert len(splits) == 2
    assert splits[0].start == cd._tracks[0]
    assert splits[0].end == cd._tracks[0]
    assert splits[1].start == cd._tracks[1]
    assert splits[1].end == cd._tracks[1]
