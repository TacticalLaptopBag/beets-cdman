from pathlib import Path
from pytest import fixture

from beetsplug.cd.mp3.mp3_cd import MP3CD
from beetsplug.cd.mp3.mp3_folder import MP3Folder
from beetsplug.cd.mp3.mp3_track import MP3Track
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor

from . import common


music_path = common.music_path
cd_path = Path(__file__).parent / "mp3_cds"


@fixture
def executor():
    return DimensionalThreadPoolExecutor(6)


@fixture
def cds(executor) -> list[MP3CD]:
    return [
        MP3CD(
            cd_path / "cd_1",
            [
                MP3Folder(
                    cd_path / "cd_1" / "Songs that start with S",
                    [
                        MP3Track(
                            music_path / "3 Stars In Her Skies.mp3",
                            128,
                        ),
                        MP3Track(
                            music_path / "002 Snowfall.mp3",
                            128,
                        ),
                    ],
                ),
                MP3Folder(
                    cd_path / "cd_1" / "Jul and Horizons",
                    [
                        MP3Track(
                            music_path / "Horizons.flac",
                            128,
                        ),
                        MP3Track(
                            music_path / "01 Jul.m4a",
                            128,
                        ),
                    ],
                ),
            ],
            executor,
        ),
        MP3CD(
            cd_path / "cd_2",
            [
                MP3Folder(
                    cd_path / "cd_2" / "Others",
                    [
                        MP3Track(
                            music_path / "A Kind Of Hope.ogg",
                            128,
                        ),
                        MP3Track(
                            music_path / "Chasing Daylight.opus",
                            128,
                        ),
                    ],
                ),
            ],
            executor,
        ),
    ]


def test_max_size(cds):
    with cds[0]._executor:
        assert cds[0].max_size == 700_000_000
        assert cds[1].max_size == 700_000_000


def test_numberize(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            for i, folder in enumerate(cd._folders):
                assert folder.path.name == f"0{i+1} {folder.name}"
                for track in folder._tracks:
                    assert track.dst_path is not None
                    assert track.dst_directory == folder.path


def test_populate(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            cd.populate()

    for cd in cds:
        for folder in cd._folders:
            for i, track in enumerate(folder._tracks):
                assert (folder.path / f"0{i+1} {track.name}.mp3").exists()


def test_get_tracks(cds):
    with cds[0]._executor:
        for cd in cds:
            tracks = cd.get_tracks()
            track_idx = 0
            for folder in cd._folders:
                for track in folder._tracks:
                    assert tracks[track_idx] == track
                    track_idx += 1


def test_cleanup(cds):
    # TODO: Write this
    cds[0]._executor.shutdown()
    assert False


def test_calculate_splits(cds):
    with cds[0]._executor:
        cds[0].numberize()
        cds[0].populate()
    
    cd = cds[0]
    tracks = cd.get_tracks()
    
    # Split right at folder
    cd._test_size = 4437541 + 3976559
    splits = cd.calculate_splits()
    assert len(splits) == 2
    assert splits[0].start == tracks[0]
    assert splits[0].end == tracks[1]
    assert splits[1].start == tracks[2]
    assert splits[1].end == tracks[3]

    # Split in between folders
    cd._test_size = 4695280
    splits = cd.calculate_splits()
    assert len(splits) == 4
    assert splits[0].start == tracks[0]
    assert splits[0].end == tracks[0]
    assert splits[1].start == tracks[1]
    assert splits[1].end == tracks[1]
    assert splits[2].start == tracks[2]
    assert splits[2].end == tracks[2]
    assert splits[3].start == tracks[3]
    assert splits[3].end == tracks[3]
