"""Exception types for the threads_scraper integration layer."""

from __future__ import annotations


class ThreadsScraperError(Exception):
    """Base class for all integration-layer errors."""


class ThreadsBinaryNotFound(ThreadsScraperError):
    """No Go binary (compiled or `go run`) could be resolved."""


class ThreadsTimeout(ThreadsScraperError):
    """The Go engine did not finish within the timeout."""


class ThreadsError(ThreadsScraperError):
    """The Go engine exited non-zero or produced malformed output.

    exit_code mirrors the documented CLI exit codes:
      2 usage, 3 not found, 4 login wall, 5 rate limited, 6 network error.
    """

    def __init__(self, message: str, exit_code: int | None = None, stderr: str = "") -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        base = super().__str__()
        if self.exit_code is not None:
            base = f"{base} (exit {self.exit_code})"
        return base
