from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Any, Callable, Optional


class _Task:
    def __init__(self, fn: Callable, args: tuple[Any], kwargs: dict[str, Any]):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn(*self.args, **self.kwargs)


# Source: https://stackoverflow.com/a/79059059
class DimensionalThreadPoolExecutor:
    def __init__(
        self,
        max_workers: int,
        thread_name_prefix: str = "",
        initializer: Optional[Callable] = None,
        initargs: tuple = (),
    ):
        """
        A wrapper around ThreadPoolExecutor that supports jobs submitting jobs.
        
        The current implementation of ThreadPoolExecutor will simply not wait
        for jobs submitted from jobs to complete before shutting down.
        This class implements a task queue that must be fully emptied before shutting down.
        """
        self._executor = ThreadPoolExecutor(
            max_workers,
            thread_name_prefix=thread_name_prefix,
            initializer=initializer,
            initargs=initargs
        )
        self._max_workers = max_workers
        self._tasks = Queue[Optional[_Task]]()

        # Occupy each worker with a task loop
        for _ in range(self._max_workers):
            self._executor.submit(self._task_loop)

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def submit(self, fn: Callable, /, *args, **kwargs):
        self._tasks.put_nowait(_Task(fn, args, kwargs))

    def shutdown(self):
        # Wait for all tasks to complete, including any that get submitted after this shutdown call
        self._tasks.join()

        # Signal task loops that they're done
        for _ in range(self._max_workers):
            self._tasks.put(None)

        # Cleanup executor
        self._executor.shutdown()

    def _task_loop(self):
        while True:
            task = self._tasks.get()
            if task is None:
                # Shutdown was called and all tasks complete, we can rest now
                break

            task.run()

            # Signal to the Queue that a task was completed
            self._tasks.task_done()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
