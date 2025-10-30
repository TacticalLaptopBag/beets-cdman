from threading import Condition, Lock


class Stats:
    lock = Lock()
    changed_cond = Condition()
    _tracks_removed = 0
    _tracks_populated = 0
    _tracks_moved = 0
    _tracks_failed = 0
    _tracks_skipped = 0
    _folders_removed = 0
    _folders_moved = 0
    
    @classmethod
    def track_removed(cls):
        with cls.lock:
            cls._tracks_removed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_moved(cls):
        with cls.lock:
            cls._tracks_moved += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_populated(cls):
        with cls.lock:
            cls._tracks_populated += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_failed(cls):
        with cls.lock:
            cls._tracks_failed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def track_skipped(cls):
        with cls.lock:
            cls._tracks_skipped += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def folder_removed(cls):
        with cls.lock:
            cls._folders_removed += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()

    @classmethod
    def folder_moved(cls):
        with cls.lock:
            cls._folders_moved += 1
        with cls.changed_cond:
            cls.changed_cond.notify_all()