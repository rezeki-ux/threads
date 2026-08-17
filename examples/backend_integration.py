"""Example: calling the th binary from a Python backend.

This is an integration example, not a runtime wrapper. The Go binary stays the
scraper engine; Python orchestrates it via subprocess and reads JSON from stdout.

Contract (guaranteed by the th binary):
  - stdout: only the requested output format (JSON here)
  - stderr: progress and error text
  - exit code: 0 success, 2 usage, 3 not found, 4 login wall, 5 rate limited,
               6 network error

No credentials are passed on the command line; session/token flow through the
THREADS_SESSION / THREADS_CSRF / THREADS_TOKEN environment variables if needed.
"""

from __future__ import annotations

import json
import subprocess
import sys

BINARY = r"threads.exe"


def search(query: str, limit: int = 10) -> list[dict]:
    """Run `th search` and return parsed JSON records. Raises on failure."""
    proc = subprocess.run(
        [BINARY, "search", query, "-n", str(limit), "-o", "json", "--no-cache"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"th search exited {proc.returncode}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "AI"
    try:
        rows = search(query, limit=10)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    # Hand the rows to a database / downstream pipeline.
    for row in rows:
        print(row["id"], row["username"], row["permalink"])
