from pathlib import Path
from pytest import fixture, raises

from beetsplug.cd.mp3.mp3_folder import MP3Folder
from beetsplug.cd.mp3.mp3_track import MP3Track

from tests import common


music_path = common.music_path
folder_path = Path(__file__).parent / "mp3_folders"


@fixture
def folders():
    return [
        MP3Folder(
            folder_path / "The First Two Odd Songs",
            [
                MP3Track(
                    music_path / "01 Jul.m4a",
                    128,
                ),
                MP3Track(
                    music_path / "3 Stars In Her Skies.mp3",
                    128,
                ),
            ],
        ),
        MP3Folder(
            folder_path / "The First Two Even Songs",
            [
                MP3Track(
                    music_path / "002 Snowfall.mp3",
                    128,
                ),
                MP3Track(
                    music_path / "A Kind Of Hope.ogg",
                    128,
                ),
            ],
        ),
    ]


def test_path(folders):
    assert folders[0].path == folder_path / "The First Two Odd Songs"
    assert folders[1].path == folder_path / "The First Two Even Songs"


def test_name(folders):
    assert folders[0].name == "The First Two Odd Songs"
    assert folders[1].name == "The First Two Even Songs"
    folders[0].numberize(1, 2)
    folders[1].numberize(2, 2)
    assert folders[0].name == "The First Two Odd Songs"
    assert folders[1].name == "The First Two Even Songs"


def test_numberize(folders):
    folder_count = len(folders)
    for i, folder in enumerate(folders):
        folder.numberize(i+1, folder_count)
        assert folder.path.name == f"0{i+1} {folder.name}"
        for j, track in enumerate(folder.tracks):
            assert track.dst_directory == folder.path
            assert track.dst_path.parent == folder.path
            assert track.dst_path.name == f"0{j+1} {track.name}.mp3"
        
        with raises(RuntimeError):
            folder.numberize(i+1, folder_count)
