"""Resolve and run the Go engine binary.

Resolution order (no assumption that `go` is on PATH):

  1. THREADS_BINARY — path to a compiled threads.exe
  2. threads.exe in the package's default location (../.. of this file)
  3. THREADS_GO_BINARY — a go executable (e.g. C:\\Program Files\\Go\\bin\\go.exe),
     used as `go run .\\cmd\\th ...`
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .exceptions import ThreadsBinaryNotFound, ThreadsError, ThreadsTimeout


def _default_binary() -> str | None:
    here = Path(__file__).resolve().parent  # python/threads_scraper
    root = here.parent.parent  # repo root
    candidate = root / "threads.exe"
    if candidate.is_file():
        return str(candidate)
    return None


def _go_binary() -> str | None:
    return os.environ.get("THREADS_GO_BINARY") or shutil.which("go")


def resolve_command() -> tuple[Sequence[str], str]:
    """Return (argv_prefix, description). Raises ThreadsBinaryNotFound."""
    binary = os.environ.get("THREADS_BINARY") or _default_binary()
    if binary:
        if not os.path.isfile(binary):
            raise ThreadsBinaryNotFound(f"THREADS_BINARY points to a missing file: {binary}")
        return ([binary], binary)

    go = _go_binary()
    if go:
        return ([go, "run", ".\\cmd\\th"], f"{go} run .\\cmd\\th")

    raise ThreadsBinaryNotFound(
        "no Go engine found: set THREADS_BINARY (compiled threads.exe) or "
        "THREADS_GO_BINARY (path to go.exe)"
    )


def run(argv: Sequence[str], timeout: float = 120) -> str:
    """Run the engine and return decoded stdout. Raises on error/timeout."""
    prefix, desc = resolve_command()
    cmd = [*prefix, *argv]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ThreadsTimeout(f"engine timed out after {timeout}s ({desc})") from exc
    except OSError as exc:
        raise ThreadsError(f"failed to launch engine ({desc}): {exc}") from exc

    if proc.returncode != 0:
        raise ThreadsError(
            f"engine command failed: {' '.join(cmd)}",
            exit_code=proc.returncode,
            stderr=(proc.stderr or "").strip(),
        )
    return proc.stdout or ""
