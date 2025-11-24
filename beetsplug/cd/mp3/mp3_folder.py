from pathlib import Path
from typing import Optional

from beetsplug.cd.mp3.mp3_track import MP3Track


class MP3Folder:
    """
    Representation of a folder in an MP3 CD.
    """

    def __init__(self, path: Path, tracks: list[MP3Track]):
        self._path = path
        self._name = path.name
        self._tracks = tracks
        self._number: Optional[str] = None

        if self.is_root:
            self._path = self._path.parent

    @property
    def is_root(self):
        """
        Determines if this folder is actually for tracks going directly into the CD folder
        """
        return self._name == "__root__"

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        """
        The name of the folder, without the prefixed numbering
        """
        return self._name

    @property
    def tracks(self):
        return self._tracks
    
    @property
    def number(self):
        if self._number is None:
            raise RuntimeError("Attempt to access number before it has been set")
        return self._number

    def numberize(self, folder_number: int, folder_count: int):
        """
        Adds numbers to the beginning of the folder so that
        alphebetically sorting these folders will put them in the correct order.
        """
        if self._number is not None:
            raise RuntimeError(f"Folder at {self._path} is already numberized!")
        
        if not self.is_root:
            digit_length = max(2, len(str(folder_count)))
            self._number = str(folder_number).zfill(digit_length)
            self._path = self._path.parent / f"{self._number} {self._path.name}"
        else:
            self._number = ""

        track_count = len(self._tracks)
        for i, track in enumerate(self._tracks):
            track.dst_directory = self._path
            track.set_dst_path(i+1, track_count)
        return None

    
