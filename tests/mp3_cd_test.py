from pathlib import Path
import shutil
from pytest import fixture

from beetsplug.cd.mp3.mp3_cd import MP3CD
from beetsplug.cd.mp3.mp3_folder import MP3Folder
from beetsplug.cd.mp3.mp3_track import MP3Track
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor
from beetsplug.stats import Stats

from tests import common


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
                MP3Folder(
                    cd_path / "cd_2" / "__root__",
                    [
                        MP3Track(
                            music_path / "A Kind Of Hope.ogg",
                            128,
                        ),
                        MP3Track(
                            music_path / "Horizons.flac",
                            128,
                        )
                    ]
                )
            ],
            executor,
        ),
    ]


@fixture
def dup_cd(executor) -> MP3CD:
    return MP3CD(
        cd_path / "cd_dup",
        [
            MP3Folder(
                cd_path / "cd_dup" / "duplicate",
                [
                    MP3Track(
                        music_path / "01 Jul.m4a",
                        128,
                    ),
                    MP3Track(
                        music_path / "01 Jul.m4a",
                        128,
                    ),
                ],
            ),
            MP3Folder(
                cd_path / "cd_dup" / "duplicate",
                [
                    MP3Track(
                        music_path / "01 Jul.m4a",
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
    )


def test_max_size(cds):
    with cds[0]._executor:
        assert cds[0].max_size == 735_397_888
        assert cds[1].max_size == 735_397_888


def test_numberize(cds):
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            for i, folder in enumerate(cd._folders):
                if folder.is_root:
                    assert folder.name == "__root__"
                    assert folder.path == cd.path
                else:
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
    with cds[0]._executor:
        for cd in cds:
            cd.numberize()
            cd.populate()
        cds[0]._executor.wait()
        cd = cds[0]
        Stats.reset()

        # Case 1: Song no longer exists in folder
        track1_path = cd._folders[0].tracks[0].dst_path
        extra_track_path = track1_path.with_stem("03 Extra Song")
        shutil.copy2(track1_path, extra_track_path)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_deleted == 1
        assert track1_path.exists()
        assert not extra_track_path.exists()
        Stats.reset()
        
        # Case 2: Song has changed position in folder
        track2_path = cd._folders[0].tracks[1].dst_path
        track1_renamed = track1_path.with_stem("02 Stars In Her Skies")
        track2_renamed = track2_path.with_stem("01 Snowfall")
        track1_path.rename(track1_renamed)
        track2_path.rename(track2_renamed)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_moved == 2
        assert track1_path.exists()
        assert track2_path.exists()
        assert not track1_renamed.exists()
        assert not track2_renamed.exists()
        Stats.reset()

        # Case 3: Folder no longer exists in CD
        folder1_path = cd._folders[0].path
        extra_folder_path = folder1_path.with_name("03 Extra Folder")
        shutil.copytree(folder1_path, extra_folder_path)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.folders_deleted == 1
        assert folder1_path.exists()
        assert not extra_folder_path.exists()
        
        # Case 4: Folder has changed position in CD
        folder2_path = cd._folders[1].path
        folder1_renamed = folder1_path.with_name("02 Songs that start with S")
        folder2_renamed = folder2_path.with_name("01 Jul and Horizons")
        folder1_path.rename(folder1_renamed)
        folder2_path.rename(folder2_renamed)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.folders_moved == 2
        assert folder1_path.exists()
        assert folder2_path.exists()
        assert not folder1_renamed.exists()
        assert not folder2_renamed.exists()
        Stats.reset()
        
        # Bonus Case: All cases combined
        shutil.copy2(track1_path, extra_track_path)
        shutil.copytree(folder1_path, extra_folder_path)
        track1_path.rename(track1_renamed)
        track2_path.rename(track2_renamed)
        folder1_path.rename(folder1_renamed)
        folder2_path.rename(folder2_renamed)
        cd.cleanup()
        cd._executor.wait()
        assert Stats.tracks_deleted == 1
        assert Stats.tracks_moved == 2
        assert Stats.folders_deleted == 1
        assert Stats.folders_moved == 2
        assert folder1_path.exists()
        assert folder2_path.exists()
        assert not folder1_renamed.exists()
        assert not folder2_renamed.exists()
        assert not extra_folder_path.exists()
        assert track1_path.exists()
        assert track2_path.exists()
        assert not track1_renamed.exists()
        assert not track2_renamed.exists()


def test_cleanup_with_duplicates(dup_cd):
    with dup_cd._executor:
        dup_cd.numberize()
        dup_cd.populate()
        dup_cd._executor.wait()
        Stats.reset()

        dup_cd.cleanup()
        assert Stats.tracks_moved == 0
        assert Stats.tracks_deleted == 0
        assert Stats.folders_moved == 0
        assert Stats.folders_deleted == 0
        for folder in dup_cd._folders:
            assert folder.path.exists()


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
