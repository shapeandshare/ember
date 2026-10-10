"""Sample peak MPS memory while one inference runs (research R11)."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from types import TracebackType

import torch


def _rss_bytes() -> int:
    out = subprocess.check_output(  # noqa: S603 - fixed argv, this process's pid
        ["ps", "-o", "rss=", "-p", str(os.getpid())],  # noqa: S607 - system ps
        text=True,
    )
    return int(out.strip()) * 1024


def _synchronize() -> None:
    if torch.backends.mps.is_available():
        torch.mps.synchronize()


class MemorySampler:
    """Context manager that polls driver memory on a thread during a block.

    ``peak_bytes`` is the process RSS when the block starts plus the highest
    driver-allocated value sampled during it.

    Parameters
    ----------
    read_driver : Callable[[], int] | None, optional
        Driver-allocated bytes; defaults to ``torch.mps.driver_allocated_memory``.
    read_rss : Callable[[], int] | None, optional
        Process RSS in bytes; defaults to ``ps -o rss= -p <pid>``.
    interval : float, optional
        Seconds between samples.
    """

    def __init__(
        self,
        read_driver: Callable[[], int] | None = None,
        read_rss: Callable[[], int] | None = None,
        interval: float = 0.02,
    ) -> None:
        self._read_driver = read_driver or torch.mps.driver_allocated_memory
        self._read_rss = read_rss or _rss_bytes
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.rss_start_bytes = 0
        self.driver_peak_bytes = 0

    @property
    def peak_bytes(self) -> int:
        """RSS at the start plus the driver peak."""
        return self.rss_start_bytes + self.driver_peak_bytes

    @property
    def running(self) -> bool:
        """Whether the sampling thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self) -> MemorySampler:
        """Synchronize, record the starting RSS, and start sampling."""
        _synchronize()
        self.rss_start_bytes = self._read_rss()
        self.driver_peak_bytes = self._read_driver()
        self._stop.clear()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Synchronize, stop sampling, and take a last reading; never swallow."""
        try:
            _synchronize()
        finally:
            self._stop.set()
            if self._thread is not None:
                self._thread.join()
        self.driver_peak_bytes = max(self.driver_peak_bytes, self._read_driver())

    def _sample(self) -> None:
        while not self._stop.wait(self._interval):
            self.driver_peak_bytes = max(self.driver_peak_bytes, self._read_driver())
