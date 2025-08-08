from abc import ABC, abstractmethod
from pathlib import Path
from beets.library import Library

from ..dimensional_thread_pool_executor import DimensionalThreadPoolExecutor


MAX_SIZE_AUDIO = 4_800


class CD(ABC):
    def __init__(self, path: Path):
        self.path = path

    @property
    @abstractmethod
    def size_warning(self) -> str:
        pass

    @abstractmethod
    def get_size(self) -> int | float:
        pass

    @abstractmethod
    def is_exceeding_size(self) -> bool:
        pass

    @abstractmethod
    def get_splits(self) -> list[Path]:
        pass

    @abstractmethod
    def get_used_tracks(self, lib: Library) -> set[str]:
        pass

    @abstractmethod
    def cleanup(self, executor: DimensionalThreadPoolExecutor):
        pass

    @abstractmethod
    def convert(self, lib: Library, executor: DimensionalThreadPoolExecutor):
        pass
    