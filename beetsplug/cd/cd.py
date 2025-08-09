import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, final
from beets.library import Library, parse_query_string, Item

from ..util import get_all_files, item_to_track_listing
from ..dimensional_thread_pool_executor import DimensionalThreadPoolExecutor


MAX_SIZE_AUDIO = 4_800


class CD(ABC):
    def __init__(self, lib: Library, path: Path, dry: bool):
        self.lib = lib
        self.path = path
        self.dry = dry

    @property
    @abstractmethod
    def size_warning(self) -> str:
        pass

    @abstractmethod
    def get_size(self) -> int | float:
        pass

    def is_exceeding_size(self) -> bool:
        size = self.get_size()
        return size > self._get_max_size()

    def get_splits(self) -> list[Path]:
        files = get_all_files(self.path)
        splits: list[Path] = []
        sum = 0
        
        for file in files:
            file_size = 0
            file_size = self._get_track_size(file)
            max_size = self._get_max_size()
                
            sum += file_size
            if sum >= max_size:
                splits.append(file)
                sum = file_size
        
        return splits

    @abstractmethod
    def _get_track_size(self, file: Path) -> int | float:
        pass

    @abstractmethod
    def _get_max_size(self) -> int | float:
        pass

    @abstractmethod
    def _get_queries(self) -> list[str]:
        pass

    def get_used_tracks(self) -> set[str]:
        used_tracks = set[str]()
        for query_str in self._get_queries():
            query, _ = parse_query_string(query_str, Item)
            items = self.lib.items(query)
            for item in items:
                track = item_to_track_listing(item)
                used_tracks.add(track)
        return used_tracks

    @abstractmethod
    def cleanup(self, executor: DimensionalThreadPoolExecutor):
        pass

    @abstractmethod
    def convert(self, executor: DimensionalThreadPoolExecutor):
        pass

    def find_item_path(self, item_name: str, items: list[str]) -> Optional[Path]:
        name_regex = r"^\d+\s+(.*$)"
        name_match = re.match(name_regex, item_name)
        if name_match is None:
            # item_name isn't in the expected format
            return None
    