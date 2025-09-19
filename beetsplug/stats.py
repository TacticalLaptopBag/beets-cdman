from threading import Condition, Lock


class Stats:
    def __init__(self):
        self.skip_count = 0
        self.convert_count = 0
        self.failed_convert_count = 0
        self.removed_count = 0
        self.folders_moved_count = 0

        self.lock = Lock()
        self.changed_cond = Condition()
        self.done = False

    def notify(self):
        with self.changed_cond:
            self.changed_cond.notify_all()
