"""Sample peak GPU memory while one inference runs (research R11).

Supports MPS (Apple Silicon) and CUDA (NVIDIA) devices.  The device is
selected at construction time; the default is ``"mps"`` to preserve the
existing behaviour for the local long-context probe.
"""

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


def _mps_synchronize() -> None:
    if torch.backends.mps.is_available():
        torch.mps.synchronize()


def _cuda_synchronize() -> None:
    torch.cuda.synchronize()


def _mps_driver_allocated() -> int:
    return torch.mps.driver_allocated_memory()


def _cuda_max_memory_allocated() -> int:
    return torch.cuda.max_memory_allocated()


def _cuda_reset_peak_stats() -> None:
    torch.cuda.reset_peak_memory_stats()


class MemorySampler:
    """Context manager that polls driver memory on a thread during a block.

    On MPS, ``peak_bytes`` is the process RSS when the block starts plus the
    highest ``torch.mps.driver_allocated_memory`` sampled during it.  On CUDA,
    CUDA peak stats are reset at block entry (so a later block cannot inherit
    an earlier block's peak) and ``peak_bytes`` is the CUDA maximum allocated
    bytes alone; host RSS is kept as telemetry because the CUDA budget is
    device memory.

    Parameters
    ----------
    device : str, optional
        ``"mps"`` (default) or ``"cuda"``.  Selects the synchronize and
        driver-read functions when ``synchronize`` and ``read_driver`` are
        not supplied explicitly.
    read_driver : Callable[[], int] | None, optional
        Driver-allocated bytes; defaults to the device-appropriate function.
    read_rss : Callable[[], int] | None, optional
        Process RSS in bytes; defaults to ``ps -o rss= -p <pid>``.
    synchronize : Callable[[], None] | None, optional
        Device synchronize function; defaults to the device-appropriate one.
    reset_peak : Callable[[], None] | None, optional
        Resets the driver's peak-stat counter; run after synchronize and
        before the first reading.  Defaults to
        ``torch.cuda.reset_peak_memory_stats`` on CUDA and a no-op on MPS.
    interval : float, optional
        Seconds between samples.
    """

    def __init__(
        self,
        device: str = "mps",
        read_driver: Callable[[], int] | None = None,
        read_rss: Callable[[], int] | None = None,
        synchronize: Callable[[], None] | None = None,
        reset_peak: Callable[[], None] | None = None,
        interval: float = 0.02,
    ) -> None:
        self._device = device
        if read_driver is not None:
            self._read_driver = read_driver
        elif device == "cuda":
            self._read_driver = _cuda_max_memory_allocated
        else:
            self._read_driver = _mps_driver_allocated
        self._read_rss = read_rss or _rss_bytes
        if synchronize is not None:
            self._synchronize = synchronize
        elif device == "cuda":
            self._synchronize = _cuda_synchronize
        else:
            self._synchronize = _mps_synchronize
        if reset_peak is not None:
            self._reset_peak = reset_peak
        elif device == "cuda":
            self._reset_peak = _cuda_reset_peak_stats
        else:
            self._reset_peak = None
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.rss_start_bytes = 0
        self.driver_peak_bytes = 0

    @property
    def peak_bytes(self) -> int:
        """The device-memory peak: RSS plus driver on MPS, driver alone on CUDA."""
        if self._device == "cuda":
            return self.driver_peak_bytes
        return self.rss_start_bytes + self.driver_peak_bytes

    @property
    def running(self) -> bool:
        """Whether the sampling thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self) -> MemorySampler:
        """Synchronize, reset peak stats, record the starting RSS, and sample."""
        self._synchronize()
        if self._reset_peak is not None:
            self._reset_peak()
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
            self._synchronize()
        finally:
            self._stop.set()
            if self._thread is not None:
                self._thread.join()
        self.driver_peak_bytes = max(self.driver_peak_bytes, self._read_driver())

    def _sample(self) -> None:
        while not self._stop.wait(self._interval):
            self.driver_peak_bytes = max(self.driver_peak_bytes, self._read_driver())
