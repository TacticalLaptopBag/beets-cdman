from pathlib import Path
import shutil
from pytest import fixture

from beetsplug.cd.audio.audio_cd import AudioCD
from beetsplug.cd.audio.audio_populate_mode import AudioPopulateMode
from beetsplug.cd.audio.audio_track import AudioTrack
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.stats import Stats

from tests import common


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


@fixture
def dup_cd(executor) -> AudioCD:
    return AudioCD(
        cd_path / "cd_dup",
        [
            AudioTrack(
                music_path / "01 Jul.m4a",
                cd_path / "cd_dup",
                AudioPopulateMode.COPY,
            ),
            AudioTrack(
                music_path / "01 Jul.m4a",
                cd_path / "cd_dup",
                AudioPopulateMode.COPY,
            ),
        ],
        executor,
    )


def test_max_size(cds):
    with cds[0]._executor:
        assert cds[0].max_size == 4800
        assert cds[1].max_size == 4800


def test_numberize(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            for track in cd._tracks:
                assert track.dst_path is not None


def test_populate(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            cd.populate()

    for cd in cds:
        for i, track in enumerate(cd._tracks):
            assert (cd.path / f"0{i+1} {track.name}{track.src_path.suffix}").exists()


def test_get_tracks(cds):
    with cds[0]._executor:
        for cd in cds:
            tracks = cd.get_tracks()
            for i, track in enumerate(tracks):
                assert cd._tracks[i] == track


def test_cleanup(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            cd.populate()
        cds[0]._executor.wait()
        cd = cds[0]
        Stats.reset()

        # Case 1: Song no longer exists in CD
        track1_path = cd._tracks[0].dst_path
        extra_path = track1_path.with_stem("04 Extra Song")
        shutil.copy2(track1_path, extra_path)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_removed == 1
        assert not extra_path.exists()
        Stats.reset()

        # Case 2: Song has changed position
        track2_path = cd._tracks[1].dst_path
        track3_path = cd._tracks[2].dst_path
        track2_renamed = track2_path.with_stem("03 Stars In Her Skies")
        track3_renamed = track3_path.with_stem("02 Chasing Daylight")
        track2_path.rename(track2_renamed)
        track3_path.rename(track3_renamed)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_moved == 2
        assert track2_path.exists()
        assert track3_path.exists()
        assert not track2_renamed.exists()
        assert not track3_renamed.exists()
        Stats.reset()

        # Bonus case: All cases combined
        shutil.copy2(track1_path, extra_path)
        track2_path.rename(track2_renamed)
        track3_path.rename(track3_renamed)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_removed == 1
        assert Stats.tracks_moved == 2
        assert not extra_path.exists()
        assert track2_path.exists()
        assert track3_path.exists()
        assert not track2_renamed.exists()
        assert not track3_renamed.exists()


def test_cleanup_with_duplicates(dup_cd):
    with dup_cd._executor:
        dup_cd.numberize()
        dup_cd.populate()
        dup_cd._executor.wait()
        Stats.reset()

        dup_cd.cleanup()
        assert Stats.tracks_moved == 0
        assert Stats.tracks_removed == 0


def test_calculate_splits(cds):
    with cds[0]._executor:
        cds[0].numberize()
        cds[0].populate()
        cds[1].numberize()
        cds[1].populate()

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
    