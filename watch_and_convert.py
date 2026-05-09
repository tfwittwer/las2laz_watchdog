"""
Watch a directory for new LAS files and convert each to LAZ as soon as it is
fully written.

Usage:
    python watch_and_convert.py

Requires:  pip install watchdog laspy lazrs-python numpy
"""

import logging
import os
import queue
import re
import threading
import time

import laspy
import numpy as np
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

WATCH_DIR = r"C:\Projectname\Export\LAS"
STABILITY_SECONDS = 2.0   # file size must be unchanged for this long before converting
POLL_INTERVAL = 0.5        # how often to re-check file size during stability wait

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def process(path: str) -> None:
    las = laspy.read(path)
    match = re.search(r"_Track(\d+)_", path, re.IGNORECASE)
    if match:
        las.point_source_id = np.full(
            len(las.point_source_id), int(match.group(1)), dtype=np.uint16
        )
    laz_path = path.replace(".las", ".laz")
    las.write(laz_path)
    if os.path.exists(laz_path):
        os.remove(path)


def wait_until_written(path: str) -> bool:
    """Block until the file size has been stable for STABILITY_SECONDS.

    Returns False if the file disappears while waiting.
    """
    last_size = -1
    stable_since: float | None = None
    while True:
        try:
            size = os.path.getsize(path)
        except FileNotFoundError:
            return False
        if size != last_size:
            last_size = size
            stable_since = None
        else:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= STABILITY_SECONDS:
                return True
        time.sleep(POLL_INTERVAL)


class LasHandler(FileSystemEventHandler):
    def __init__(self, work_queue: queue.Queue) -> None:
        self._queue = work_queue
        self._seen: set[str] = set()

    def _enqueue(self, path: str) -> None:
        if path.lower().endswith(".las") and path not in self._seen:
            self._seen.add(path)
            self._queue.put(path)

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)


def worker(work_queue: queue.Queue) -> None:
    while True:
        path = work_queue.get()
        if path is None:
            break
        name = os.path.basename(path)
        log.info("Detected  %s — waiting for write to finish…", name)
        if not wait_until_written(path):
            log.warning("File vanished before conversion: %s", name)
            work_queue.task_done()
            continue
        log.info("Converting %s", name)
        try:
            process(path)
            log.info("Done       %s → %s", name, name.replace(".las", ".laz"))
        except Exception as exc:
            log.error("Failed to convert %s: %s", name, exc)
        work_queue.task_done()


def main() -> None:
    log.info("Watching %s", WATCH_DIR)

    work_queue: queue.Queue = queue.Queue()
    thread = threading.Thread(target=worker, args=(work_queue,), daemon=True)
    thread.start()

    handler = LasHandler(work_queue)
    observer = Observer()
    observer.schedule(handler, WATCH_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping…")
        observer.stop()
        work_queue.put(None)  # signal worker to exit

    observer.join()
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
