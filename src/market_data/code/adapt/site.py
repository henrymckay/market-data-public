"""The site data's file writer: Parquet and JSON under one folder."""

import dataclasses
import json
import pathlib

import polars

from market_data.code import port


@dataclasses.dataclass(frozen=True, slots=True)
class Writer:
    """Writes site files under a folder, each replaced whole and atomically."""

    folder: pathlib.Path

    def _target(self, name: str) -> pathlib.Path:
        target = self.folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_json(self, name: str, document: object) -> port.Written:
        """Write a JSON document under the name."""
        target = self._target(name)
        scratch = target.with_suffix(".tmp")
        scratch.write_text(json.dumps(document, separators=(",", ":")))
        scratch.replace(target)
        return port.Written(bytes=target.stat().st_size, path=name, rows=1)

    def write_parquet(self, name: str, frame: polars.DataFrame) -> port.Written:
        """Write a frame as snappy Parquet under the name."""
        target = self._target(name)
        scratch = target.with_suffix(".tmp")
        frame.write_parquet(scratch, compression="snappy")
        scratch.replace(target)
        return port.Written(bytes=target.stat().st_size, path=name, rows=frame.height)
