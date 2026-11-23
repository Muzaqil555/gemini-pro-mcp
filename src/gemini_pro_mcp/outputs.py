"""Reserve a distinct output file even when several MCP clients share a folder."""

from collections.abc import Iterator
from contextlib import contextmanager
from itertools import count
from pathlib import Path


@contextmanager
def reserve_output(requested: Path) -> Iterator[Path]:
    requested.parent.mkdir(parents=True, exist_ok=True)
    for number in count(1):
        path = (
            requested
            if number == 1
            else requested.with_name(f"{requested.stem}-{number}{requested.suffix}")
        )
        try:
            path.touch(exist_ok=False)
        except FileExistsError:
            continue
        break
    try:
        yield path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
