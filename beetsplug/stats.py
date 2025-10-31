from threading import Condition, Lock
from typing import override


class Stats:
    lock = Lock()
    changed_cond = Condition()
    tracks_removed = 0
    tracks_populated = 0
    tracks_moved = 0
    tracks_failed = 0
    tracks_skipped = 0
    folders_removed = 0
    folders_moved = 0

    
    @classmethod
    def track_removed(cls):
        with cls.lock:
            cls.tracks_removed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_moved(cls):
        with cls.lock:
            cls.tracks_moved += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_populated(cls):
        with cls.lock:
            cls.tracks_populated += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_failed(cls):
        with cls.lock:
            cls.tracks_failed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_skipped(cls):
        with cls.lock:
            cls.tracks_skipped += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def folder_removed(cls):
        with cls.lock:
            cls.folders_removed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def folder_moved(cls):
        with cls.lock:
            cls.folders_moved += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def reset(cls):
        with cls.lock:
            cls.tracks_removed = 0
            cls.tracks_populated = 0
            cls.tracks_moved = 0
            cls.tracks_failed = 0
            cls.tracks_skipped = 0
            cls.folders_removed = 0
            cls.folders_moved = 0
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @override
    def __str__(self) -> str:
        return f"Stats(\n\ttracks_removed={self.tracks_removed},\n\ttracks_populated={self.tracks_populated},\n\ttracks_moved={self.tracks_moved},\n\ttracks_failed={self.tracks_failed},\n\ttracks_skipped={self.tracks_skipped},\n\tfolders_removed={self.folders_removed},\n\tfolders_moved={self.folders_moved}\n)"