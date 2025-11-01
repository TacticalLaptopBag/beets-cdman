from threading import Condition, Lock
from typing import override


class Stats:
    lock = Lock()
    changed_cond = Condition()
    tracks_populating = 0
    tracks_populated = 0
    tracks_skipped = 0
    tracks_deleted = 0
    tracks_moved = 0
    tracks_failed = 0
    folders_deleted = 0
    folders_moved = 0
    cds = ""
    is_done = False
    is_calculating = False

    @classmethod
    def found_cd(cls, cd_name: str, cd_type: str):
        with cls.lock:
            if len(cls.cds) > 0:
                cls.cds += ", "
            cls.cds += f"{cd_name} ({cd_type})"
        cls._notify()

    @classmethod
    def populating_track(cls):
        with cls.lock:
            cls.tracks_populating += 1
        cls._notify()
    
    @classmethod
    def populate_track(cls):
        with cls.lock:
            cls.tracks_populated += 1
            cls.tracks_populating -= 1
        cls._notify()

    @classmethod
    def skip_track(cls):
        with cls.lock:
            cls.tracks_skipped += 1
        cls._notify()

    @classmethod
    def delete_track(cls):
        with cls.lock:
            cls.tracks_deleted += 1
        cls._notify()

    @classmethod
    def move_track(cls):
        with cls.lock:
            cls.tracks_moved += 1
        cls._notify()

    @classmethod
    def fail_track(cls):
        with cls.lock:
            cls.tracks_failed += 1
            cls.tracks_populating -= 1
        cls._notify()

    @classmethod
    def delete_folder(cls):
        with cls.lock:
            cls.folders_deleted += 1
        cls._notify()

    @classmethod
    def move_folder(cls):
        with cls.lock:
            cls.folders_moved += 1
        cls._notify()

    @classmethod
    def set_done(cls):
        with cls.lock:
            cls.is_done = True
        cls._notify()

    @classmethod
    def set_calculating(cls):
        with cls.lock:
            cls.is_calculating = True
        cls._notify()

    @classmethod
    def reset(cls):
        with cls.lock:
            cls.tracks_populated = 0
            cls.tracks_skipped = 0
            cls.tracks_deleted = 0
            cls.tracks_moved = 0
            cls.tracks_failed = 0
            cls.folders_deleted = 0
            cls.folders_moved = 0
            cls.is_done = False
            cls.is_calculating = False
        cls._notify()

    @classmethod
    def _notify(cls):
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @override
    def __str__(self) -> str:
        return f"Stats(\n\ttracks_removed={self.tracks_deleted},\n\ttracks_populated={self.tracks_populated},\n\ttracks_moved={self.tracks_moved},\n\ttracks_failed={self.tracks_failed},\n\ttracks_skipped={self.tracks_skipped},\n\tfolders_removed={self.folders_deleted},\n\tfolders_moved={self.folders_moved}\n)"