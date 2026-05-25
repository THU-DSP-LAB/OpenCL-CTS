from __future__ import annotations

from pathlib import Path
from types import TracebackType


class Reporter:
    def __init__(self, master_log_path: Path, *, append: bool = False) -> None:
        self._master_log_path = master_log_path
        self._append = append
        self._file = None

    def __enter__(self) -> "Reporter":
        self._master_log_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if self._append else "w"
        self._file = self._master_log_path.open(mode, encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._file is not None:
            self._file.close()

    def info(self, message: str = "") -> None:
        print(message)
        if self._file is None:
            return
        self._file.write(message + "\n")
        self._file.flush()
