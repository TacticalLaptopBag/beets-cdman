from pathlib import Path
import re
from typing import Optional

from .cd_folder import CDFolder
from .cd_type import CDType
from .util import get_all_files, get_directory_audio_length, get_directory_size, get_song_length


MAX_SIZE_MP3 = 700_000_000
MAX_SIZE_AUDIO = 4_800

CDDefinition = dict[str, list[dict[str, str]]]


class CD:
    def __init__(self, path: Path, cd_type: CDType):
        self.path = path
        self.folders: list[CDFolder] = []
        self.type = cd_type

    def __str__(self) -> str:
        folders = ""
        for i, folder in enumerate(self.folders):
            folders += str(folder)
            if i != len(self.folders) - 1:
                folders += ", "
        return f"{self.path}: [{folders}]"

    def find_folder_path(self, dirname: str) -> Optional[Path]:
        """
        Extracts the path of the folder from the given dirname,
        and then returns the current dirname of that folder.
        Example: "05 Lemaitre" would return "07 Lemaitre" if Lemaitre was moved to position 7.
        It could return None if Lemaitre is not in this CD.
        """
        # First we need to extract the actual name from the given directory name
        # Currently dirname is expected to be in the example format of "09 Folder"
        name_regex = r"^\d+\s+(.*$)"
        name_match = re.match(name_regex, dirname)
        if name_match is None:
            # dirname isn't in the expected format
            return None

        # Ignore the numbers, the capture group should be everything after
        # the folder's position
        folder_name = name_match.group(1)
        if type(folder_name) != str:
            # Something went wrong, maybe nothing was captured?
            return None

        # We now have the name of the folder,
        # let's see if it's even in this CD
        folder_idx = self.find_folder(folder_name)
        if folder_idx == -1:
            # Folder is not in CD
            return None
        folder = self.folders[folder_idx]
        
        # Folder is in CD, retrieve the path and return it
        return folder.get_path(folder_idx, self.path, len(self.folders))

    def has_folder(self, dirname: str) -> bool:
        return self.find_folder(dirname) != -1

    def find_folder(self, dirname: str) -> int:
        """
        Gets the index of the folder provided
        """
        for i, folder in enumerate(self.folders):
            if folder.dirname == dirname:
                return i
        return -1

    def get_size(self) -> int | float:
        """
        Returns size of CD. If `type` is MP3, returns size in bytes as an int.
        If `type` is AUDIO, returns size in seconds as a float.
        """
        match self.type:
            case CDType.AUDIO:
                return get_directory_audio_length(self.path)
            case CDType.MP3:
                return get_directory_size(self.path)

    def get_splits(self) -> list[Path]:
        files = get_all_files(self.path)
        splits: list[Path] = []
        sum = 0
        
        if self.type == CDType.MP3:
            for file in files:
                file_size = 0
                max_size: int
                if self.type == CDType.MP3:
                    file_size = file.stat().st_size
                    max_size = MAX_SIZE_MP3
                else:
                    file_size = get_song_length(file)
                    max_size = MAX_SIZE_AUDIO
                    
                sum += file_size
                if sum >= max_size:
                    splits.append(file)
                    sum = file_size
        
        return splits